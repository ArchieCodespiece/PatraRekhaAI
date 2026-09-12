"""
SSE orchestrator: turns a routed intent into a stream of chat/SSE events.

Consumed by ``api.chat``/chat_stream for the compare and export paths and
kept fully independent of the existing single-shot chat path.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .compare import run_compare
from .export import (
    build_comparison_export,
    build_report_export,
    generate_report,
)
from .intent import IntentResult
from .llm import stream_text
from .models import citations_from_evidence
from .retrieval import resolve_document_name
from .state import WorkflowState

FILE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


# ============================================================================
# Document-name resolution
# ============================================================================

def _clean_stem(value: str) -> str:
    from pathlib import Path

    return Path(value).stem.strip()


def _resolve_pairs(
    selected_documents: List[str],
    owner_email: Optional[str],
) -> List[Tuple[str, str]]:
    """
    Pair each user-facing document name with the Pinecone name that the
    upload pipeline stored it under (``{file_id}-{filename_stem}``).
    """

    from api.documents import resolve_pinecone_document_names

    resolved_names = resolve_pinecone_document_names(
        selected_documents,
        owner_email=owner_email,
    )

    pairs: List[Tuple[str, str]] = []
    used: set = set()

    for display_name in selected_documents:
        if not display_name or not display_name.strip():
            continue

        display = display_name.strip()
        display_stem = _clean_stem(display)

        matched = None

        for candidate in resolved_names:
            if candidate in used:
                continue

            candidate_stem = _clean_stem(candidate)

            if (
                candidate_stem == display_stem
                or candidate_stem.endswith(f"-{display_stem}")
                or candidate_stem.startswith(f"{display_stem}-")
            ):
                matched = candidate
                break

        if matched is None:
            matched = display

        used.add(matched)
        pairs.append((display, matched))

    return pairs


# ============================================================================
# State builder
# ============================================================================

def build_state(
    *,
    user_id: str,
    owner_email: str,
    effective_email: Optional[str],
    query: str,
    conversation_id: str,
    selected_documents: List[str],
    namespace: Optional[str] = None,
    target_format: Optional[str] = None,
    think_mode: bool = False,
) -> WorkflowState:
    doc_pairs = _resolve_pairs(
        selected_documents,
        effective_email,
    )

    return WorkflowState(
        user_id=user_id,
        owner_email=owner_email,
        effective_email=effective_email,
        query=query,
        conversation_id=conversation_id,
        selected_documents=[
            display for display, _ in doc_pairs
        ],
        doc_pairs=doc_pairs,
        namespace=namespace,
        target_format=target_format,
        think_mode=think_mode,
    )


# ============================================================================
# Citation helpers
# ============================================================================

def _file_id_by_document(
    state: WorkflowState,
) -> Dict[str, str]:
    mapping = {}

    for display, pinecone in state.doc_pairs:
        match = FILE_ID_PATTERN.match(pinecone)

        if match:
            mapping[display] = match.group(0)

    return mapping


def _resolve_effective_doc_pairs(
    state: WorkflowState,
    embedder: Any,
) -> None:
    """
    Rewrite ``state.doc_pairs`` so every pinecone name is one that actually
    exists in the index. Stored document_name values are inconsistent (some
    ``{file_id}-{stem}``, some bare ``{stem}``, some with/without extension),
    so resolve each requested name before coverage/context retrieval runs.
    """

    state.doc_pairs = [
        (
            display,
            resolve_document_name(
                pinecone,
                embedder,
                namespace=state.namespace,
            ),
        )
        for display, pinecone in state.doc_pairs
    ]


def _sources_from_citations(citations: List[dict]) -> List[str]:
    sources: List[str] = []

    for citation in citations:
        name = citation.get("document_name")

        if name and name not in sources:
            sources.append(name)

    return sources


# ============================================================================
# Workflow event generators (SSE dicts)
# ============================================================================

def run_workflow_events(
    state: WorkflowState,
    intent: IntentResult,
) -> Iterator[Dict[str, Any]]:
    if intent.target_format:
        state.target_format = intent.target_format

    if intent.intent == "compare":
        yield from _compare_workflow_events(state)
    else:
        yield from _report_workflow_events(state)


def _done_event(
    state: WorkflowState,
    citations: List[dict],
    coverage: dict,
    export: Optional[dict] = None,
    export_error: Optional[str] = None,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "conversation_id": state.conversation_id,
        "sources": _sources_from_citations(citations),
        "citations": citations,
        "coverage": coverage,
    }

    if export:
        event["export_url"] = export.get("url")
        event["export_filename"] = export.get("filename")
        event["result_url"] = export.get("result_url")
        event["export_format"] = export.get("fmt")

    if export_error:
        event["export_error"] = export_error

    return event


def _compare_workflow_events(
    state: WorkflowState,
) -> Iterator[Dict[str, Any]]:
    from embedding.embedder import GeminiEmbedder

    embedder = GeminiEmbedder()

    _resolve_effective_doc_pairs(state, embedder)

    complete_dist = None

    for item in run_compare(state, embedder):
        if item.kind == "progress":
            yield {
                "type": "progress",
                "message": item.message,
            }
        elif item.kind == "complete":
            complete_dist = item

    if complete_dist is None or complete_dist.result is None:
        raise RuntimeError(
            "Comparison workflow completed without a result."
        )

    result = complete_dist.result
    coverage = complete_dist.coverage or {}

    export: Optional[dict] = None
    export_error: Optional[str] = None

    if state.target_format:
        try:
            for item in build_comparison_export(state, result):
                if item.kind == "progress":
                    yield {
                        "type": "progress",
                        "message": item.message,
                    }
                else:
                    export = item.payload
        except Exception as exc:
            export_error = f"Could not generate export: {exc}"
            yield {
                "type": "progress",
                "message": export_error,
            }

    yield from _stream_answer(complete_dist.chat_answer)

    citations = citations_from_evidence(
        result.collect_evidence(),
        _file_id_by_document(state),
    )

    yield _done_event(
        state,
        citations=citations,
        coverage=coverage,
        export=export,
        export_error=export_error,
    )


def _report_workflow_events(
    state: WorkflowState,
) -> Iterator[Dict[str, Any]]:
    from embedding.embedder import GeminiEmbedder

    embedder = GeminiEmbedder()

    _resolve_effective_doc_pairs(state, embedder)

    ready = None

    for item in generate_report(state, embedder):
        if item.kind == "progress":
            yield {
                "type": "progress",
                "message": item.message,
            }
        elif item.kind == "report_ready":
            ready = item.payload

    if ready is None or ready.get("report") is None:
        raise RuntimeError(
            "Report workflow completed without a result."
        )

    report = ready["report"]
    chat_answer = ready["chat_answer"]
    coverage = ready.get("coverage") or {}

    export: Optional[dict] = None
    export_error: Optional[str] = None

    try:
        for item in build_report_export(state, report):
            if item.kind == "progress":
                yield {
                    "type": "progress",
                    "message": item.message,
                }
            else:
                export = item.payload
    except Exception as exc:
        export_error = f"Could not generate export: {exc}"
        yield {
            "type": "progress",
            "message": export_error,
        }

    yield from _stream_answer(chat_answer)

    yield _done_event(
        state,
        citations=[],
        coverage=coverage,
        export=export,
        export_error=export_error,
    )


def _stream_answer(answer: str) -> Iterator[Dict[str, Any]]:
    for token in stream_text(answer):
        yield {
            "type": "token",
            "token": token,
        }