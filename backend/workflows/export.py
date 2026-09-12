"""
Export workflows: compare-export and direct report generation.

All exports are deterministic renderers fed by a canonical result:
the LLM builds the structured model once, and XLSX/PDF renderers are
pure data->file transforms.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from .config import DEFAULT_EXPORT_FORMAT, WORKFLOW_MAX_CONTEXT_CHARS
from .llm import chat_json_with_retry
from .models import ComparisonResult, ReportDocument
from .retrieval import DocumentCoverage, fetch_document_coverage
from .state import WorkflowState
from .store import upload_export_file

from .renderers.xlsx_renderer import comparison_to_xlsx, report_to_xlsx
from .renderers.pdf_renderer import comparison_to_pdf, report_to_pdf


@dataclass
class ExportArtifact:
    filename: str
    url: str
    content_type: str


@dataclass
class ReportJobResult:
    report: Optional[ReportDocument] = None
    chat_answer: str = ""
    coverage: dict = field(default_factory=dict)


REPORT_EXTRACTOR_SYSTEM = (
    "You extract a structured report from the provided document context. "
    "Return ONLY JSON matching exactly this schema:\n"
    '{"title": "report title", "sections": [{"heading": "Heading", '
    '"content": "a concise paragraph summarising this section (may be '
    'empty if a table is provided)", "table": {"headers": [col1, col2], '
    '"rows": [[r1c1, r1c2], [r2c1, r2c2]]} | null}]}\n\n'
    "Rules:\n"
    "- Base every fact only on the provided context; never invent.\n"
    "- Keep content factual and concise.\n"
    "- A table is optional: use it for tabular/structured data "
    "(amounts, dates, parties, responsibilities).\n"
    "- At most 12 sections.\n"
    "Return valid JSON only, no markdown fences."
)


def _normalize_format(value: Optional[str]) -> str:
    fmt = (value or DEFAULT_EXPORT_FORMAT).lower().lstrip(".")

    if fmt in ("csv", "xls"):
        return "xlsx"

    if fmt in ("docx", "txt"):
        return "pdf"

    return "xlsx" if fmt != "pdf" else "pdf"


def _safe_stem(
    texts: List[str],
    fallback: str = "export",
) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", os.pathsep.join(texts)).strip("-")

    return (cleaned or fallback)[:60]


def _content_type(fmt: str) -> str:
    if fmt == "pdf":
        return "application/pdf"

    return (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    )


@dataclass(init=False)
class _ProgressEvent:
    def __init__(self, kind: str, message: str = "", **payload):
        self.kind = kind
        self.message = message
        self.payload = payload


def _progress(message: str, **payload):
    return _ProgressEvent("progress", message=message, **payload)


def _report_ready(report: ReportDocument, chat_answer: str, coverage: dict):
    return _ProgressEvent(
        "report_ready",
        **{
            "report": report,
            "chat_answer": chat_answer,
            "coverage": coverage,
        },
    )


# ============================================================================
# Direct report extraction (no comparison)
# ============================================================================

def generate_report(
    state: WorkflowState,
    embedder: Any,
) -> Iterator[_ProgressEvent]:
    """
    Extract a ReportDocument from the selected documents and prepare a
    chat-visible markdown summary.
    """

    yield _progress(
        f"Reading {', '.join(state.display_names())} to build a report"
    )

    coverage_by_doc: Dict[str, DocumentCoverage] = {}
    section_blocks: List[str] = []

    for display, pinecone in state.doc_pairs:
        coverage = fetch_document_coverage(
            document_name=pinecone,
            embedder=embedder,
            namespace=state.namespace,
        )
        coverage_by_doc[pinecone] = coverage

        section_map = coverage.section_map()

        if not section_map:
            section_blocks.append(
                f"[Document: {display}]\n"
                + "\n".join(record.text for record in coverage.records[:30])
            )
            continue

        for section_name, records in section_map.items():
            text = "\n".join(record.text for record in records)
            section_blocks.append(
                f"[Document: {display} | Section: {section_name}]\n{text}"
            )

        yield _progress(
            f"Extracted {len(coverage.records)} passages from {display}"
        )

    prompt_context = "\n\n".join(section_blocks)
    prompt_context = prompt_context[:WORKFLOW_MAX_CONTEXT_CHARS]

    yield _progress("Structuring the report")

    try:
        payload = chat_json_with_retry(
            REPORT_EXTRACTOR_SYSTEM,
            (
                "User request: " + state.query + "\n\n"
                "Document context:\n" + prompt_context
            ),
            [
                "Ensure 'title' and 'sections' are present; each section "
                "has heading (string), content (string), table (object or "
                "null) with headers and rows arrays.",
            ],
            attempts=3,
        )

        report = ReportDocument.model_validate(payload)

    except Exception:
        # Build a minimal deterministic report from what we have.
        report = _fallback_report(state, coverage_by_doc)

    chat_answer = render_report_chat_answer(report, state)

    coverage_state = {
        "exhaustive": all(
            coverage_by_doc[pinecone].complete
            for _, pinecone in state.doc_pairs
        ),
        "documents": {
            display: len(
                coverage_by_doc[pinecone].records
            )
            for display, pinecone in state.doc_pairs
            if coverage_by_doc.get(pinecone)
        },
    }

    yield _report_ready(report, chat_answer, coverage_state)


def _fallback_report(
    state: WorkflowState,
    coverage_by_doc: Dict[str, DocumentCoverage],
) -> ReportDocument:
    sections = []

    for display, pinecone in state.doc_pairs:
        coverage = coverage_by_doc.get(pinecone)
        if not coverage:
            continue

        section_map = coverage.section_map()

        if not section_map:
            sections.append(
                {
                    "heading": display,
                    "content": "\n".join(
                        record.text[:400]
                        for record in coverage.records[:10]
                    ),
                    "table": None,
                }
            )
            continue

        for section_name, records in section_map.items():
            content = " ".join(record.text for record in records)
            sections.append(
                {
                    "heading": f"{display} · {section_name}",
                    "content": content[:2000],
                    "table": None,
                }
            )

    return ReportDocument(
        title=(
            f"Report – {', '.join(state.display_names())}"
        ),
        sections=sections[:12],
    )


def render_report_chat_answer(
    report: ReportDocument,
    state: WorkflowState,
) -> str:
    lines: List[str] = [f"### {report.title}", ""]

    for section in report.sections:
        lines.append(f"## {section.heading}")
        lines.append("")

        if section.content:
            lines.append(section.content)
            lines.append("")

        if section.table and section.table.headers:
            lines.append(
                "| "
                + " | ".join(section.table.headers)
                + " |"
            )
            lines.append(
                "|" + "|".join(["---"] * len(section.table.headers)) + "|"
            )

            for row in section.table.rows:
                lines.append(
                    "| "
                    + " | ".join(str(cell or "") for cell in row)
                    + " |"
                )
            lines.append("")

    lines.append("")
    return "\n".join(lines)


# ============================================================================
# Compare-export
# ============================================================================

def build_comparison_export(
    state: WorkflowState,
    result: ComparisonResult,
) -> Iterator[_ProgressEvent]:
    """
    Render a completed comparison into the requested export format and
    upload it, persisting the canonical JSON alongside.
    """

    fmt = _normalize_format(state.target_format)

    names = state.display_names()
    doc_a = names[0] if names else "Document A"
    doc_b = names[-1] if len(names) > 1 else "Document B"

    yield _progress(f"Rendering {fmt.upper()} export")

    if fmt == "pdf":
        binary = comparison_to_pdf(result, doc_a, doc_b)
    else:
        binary = comparison_to_xlsx(result, doc_a, doc_b)

    stem = _safe_stem([doc_a, "vs", doc_b], fallback="comparison")
    filename = f"{stem}.{fmt}"

    yield _progress(f"Uploading {filename}")

    url = upload_export_file(
        user_id=state.user_id,
        conversation_id=state.conversation_id,
        filename=filename,
        content=binary,
        content_type=_content_type(fmt),
    )

    canonical_json = result.model_dump_json(indent=2).encode("utf-8")
    result_filename = f"{stem}.comparison.json"

    result_url = upload_export_file(
        user_id=state.user_id,
        conversation_id=state.conversation_id,
        filename=result_filename,
        content=canonical_json,
        content_type="application/json",
    )

    yield _ProgressEvent(
        "export_ready",
        message="Export ready",
        filename=filename,
        url=url,
        result_url=result_url,
        fmt=fmt,
    )


def build_report_export(
    state: WorkflowState,
    report: ReportDocument,
) -> Iterator[_ProgressEvent]:
    """Render a ReportDocument to the requested export format + upload."""

    fmt = _normalize_format(state.target_format)

    yield _progress(f"Rendering {fmt.upper()} export")

    if fmt == "pdf":
        binary = report_to_pdf(report)
    else:
        binary = report_to_xlsx(report)

    stem = _safe_stem([report.title], fallback="report")
    filename = f"{stem}.{fmt}"

    yield _progress(f"Uploading {filename}")

    url = upload_export_file(
        user_id=state.user_id,
        conversation_id=state.conversation_id,
        filename=filename,
        content=binary,
        content_type=_content_type(fmt),
    )

    canonical_json = report.model_dump_json(indent=2).encode("utf-8")
    result_filename = f"{stem}.report.json"

    result_url = upload_export_file(
        user_id=state.user_id,
        conversation_id=state.conversation_id,
        filename=result_filename,
        content=canonical_json,
        content_type="application/json",
    )

    yield _ProgressEvent(
        "export_ready",
        message="Export ready",
        filename=filename,
        url=url,
        result_url=result_url,
        fmt=fmt,
    )