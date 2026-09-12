"""
First-class verification step for comparison rows.

Every claim in a :class:`ComparisonRow` must be supported by evidence from
BOTH documents. We use a cheap keyword-overlap pre-check and only invoke
the LLM when overlap is weak (semantic support, never literal terms).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import (
    COMPARE_VERIFY_BATCH_SIZE,
    VERIFY_MODEL,
    MIN_KEYWORD_OVERLAP,
)
from .llm import chat_json
from .models import ComparisonResult, ComparisonRow, Evidence
from .retrieval import overlap_ratio

VERIFIER_SYSTEM = (
    "You verify whether highlighted snippets from two documents support a "
    "comparison claim. Respond ONLY with JSON.\n"
    '{"document_a_supported": true/false, '
    '"document_b_supported": true/false, '
    '"difference_supported": true/false, '
    '"reason": "short explanation"}\n\n'
    "Use semantic support: the snippet must reasonably support the claim "
    "even if the exact keywords are absent. When in genuine doubt, prefer "
    "true for a snippet that is on-topic."
)

BATCHED_VERIFIER_SYSTEM = (
    "You verify multiple document-comparison claims. For every input row, "
    "decide whether the claim value from each document and the alleged "
    "difference are supported by the supplied snippets. Respond ONLY with "
    "JSON in this shape: "
    '{"results":[{"index":0,"document_a_supported":true,'
    '"document_b_supported":true,"difference_supported":true}]}'
    " Preserve every input index exactly once. Use semantic support; when "
    "in genuine doubt, prefer true for a snippet that is on-topic."
)


@dataclass
class VerificationReport:
    verified: List[ComparisonRow] = field(default_factory=list)
    re_retrieve: List[ComparisonRow] = field(default_factory=list)


def evidence_for_document(
    row: ComparisonRow,
    document: str,
) -> List[Evidence]:
    return [
        item
        for item in row.evidence
        if item.document == document
    ]


def _cheap_check(row: ComparisonRow, document: str) -> bool:
    """Keyword overlap between the claim value and its evidence text."""

    claim_value = (
        row.document_a if document == "A" else row.document_b
    )

    doc_name = _display_name(row, document)

    snippets = evidence_for_document(row, doc_name) if doc_name else []

    if not snippets:
        return False

    normalized_claim = str(claim_value or "").strip().lower()
    if normalized_claim in ("—", "-", "none", "no", "n/a", "nil", ""):
        return False

    for snippet in snippets:
        if overlap_ratio(claim_value, snippet.text) >= MIN_KEYWORD_OVERLAP:
            return True

    return False


def _display_name(row: ComparisonRow, role_doc: str) -> str:
    """
    Map a claim column (A/B) to the human-readable evidence document name.

    Falls back to scanning evidence documents for the first distinct name.
    """

    names = []

    for item in row.evidence:
        if item.document and item.document not in names:
            names.append(item.document)

    if not names:
        return ""

    if role_doc == "A":
        return names[0]

    if len(names) > 1:
        return names[1]

    return names[0]


def verify_row_with_llm(
    row: ComparisonRow,
) -> "LLMDepthResult":
    from .models import Evidence

    a_name = _display_name(row, "A")
    b_name = _display_name(row, "B")

    a_snippets = evidence_for_document(row, a_name) if a_name else []
    b_snippets = evidence_for_document(row, b_name) if b_name else []

    a_text = " / ".join(snippet.text for snippet in a_snippets[:2]) or "NO EVIDENCE"
    b_text = " / ".join(snippet.text for snippet in b_snippets[:2]) or "NO EVIDENCE"

    payload = chat_json(
        VERIFIER_SYSTEM,
        (
            "Claim topic: " + row.topic + "\n"
            "Document A claim: " + (row.document_a or "—") + "\n"
            "Document B claim: " + (row.document_b or "—") + "\n"
            "Alleged difference: " + str(row.difference) + "\n\n"
            "Document A snippets:\n" + a_text + "\n\n"
            "Document B snippets:\n" + b_text
        ),
        temperature=0.0,
        model=VERIFY_MODEL,
    )

    return LLMDepthResult(
        document_a_supported=bool(payload.get("document_a_supported")),
        document_b_supported=bool(payload.get("document_b_supported")),
        difference_supported=bool(payload.get("difference_supported")),
    )


@dataclass
class LLMDepthResult:
    document_a_supported: bool = False
    document_b_supported: bool = False
    difference_supported: bool = True


def _verification_prompt(row: ComparisonRow, index: int) -> Dict[str, Any]:
    a_name = _display_name(row, "A")
    b_name = _display_name(row, "B")
    a_snippets = evidence_for_document(row, a_name) if a_name else []
    b_snippets = evidence_for_document(row, b_name) if b_name else []

    return {
        "index": index,
        "topic": row.topic,
        "document_a_claim": row.document_a or "—",
        "document_b_claim": row.document_b or "—",
        "difference": row.difference,
        "document_a_snippets": [
            snippet.text[:1200] for snippet in a_snippets[:2]
        ],
        "document_b_snippets": [
            snippet.text[:1200] for snippet in b_snippets[:2]
        ],
    }


def _verify_batch_with_llm(
    batch: List[tuple[int, ComparisonRow]],
) -> Dict[int, LLMDepthResult]:
    payload = chat_json(
        BATCHED_VERIFIER_SYSTEM,
        "Claims to verify:\n" + str(
            [_verification_prompt(row, index) for index, row in batch]
        ),
        temperature=0.0,
        model=VERIFY_MODEL,
    )

    results: Dict[int, LLMDepthResult] = {}

    for raw in payload.get("results") or []:
        if not isinstance(raw, dict):
            continue

        try:
            index = int(raw["index"])
        except (KeyError, TypeError, ValueError):
            continue

        if index not in {item[0] for item in batch}:
            continue

        results[index] = LLMDepthResult(
            document_a_supported=bool(
                raw.get("document_a_supported")
            ),
            document_b_supported=bool(
                raw.get("document_b_supported")
            ),
            difference_supported=bool(
                raw.get("difference_supported", True)
            ),
        )

    return results


def verify_result(
    result: ComparisonResult,
    *,
    use_llm: bool = True,
) -> VerificationReport:
    """
    Run cheap checks on every row, falling back to the LLM where needed.

    Rows that are genuinely unsupported (regardless of LLM depth) are
    flagged for a targeted re-retrieval pass.
    """

    report = VerificationReport()
    needs_llm: List[tuple[int, ComparisonRow]] = []
    all_rows: List[ComparisonRow] = []
    next_index = 0

    for section in result.sections:
        for row in section.rows:
            all_rows.append(row)
            a_name = _display_name(row, "A")
            b_name = _display_name(row, "B")

            a_evidence = evidence_for_document(row, a_name) if a_name else []
            b_evidence = evidence_for_document(row, b_name) if b_name else []

            # Hard requirement: evidence on both sides.
            if not a_evidence or not b_evidence:
                row.unverified = True
                continue

            a_ok = _cheap_check(row, "A")
            b_ok = _cheap_check(row, "B")

            if a_ok and b_ok:
                row.unverified = False
            elif use_llm:
                needs_llm.append((next_index, row))
                next_index += 1
            else:
                row.unverified = True

    if not needs_llm:
        report.verified = [row for row in all_rows if not row.unverified]
        report.re_retrieve = [row for row in all_rows if row.unverified]
        return report

    depth_by_index: Dict[int, LLMDepthResult] = {}
    batches = [
        needs_llm[start:start + COMPARE_VERIFY_BATCH_SIZE]
        for start in range(0, len(needs_llm), COMPARE_VERIFY_BATCH_SIZE)
    ]

    with ThreadPoolExecutor(max_workers=min(2, len(batches))) as executor:
        futures = {
            executor.submit(_verify_batch_with_llm, batch): batch
            for batch in batches
        }

        for future in as_completed(futures):
            try:
                depth_by_index.update(future.result())
            except Exception:
                # Missing or failed batch results remain unsupported.
                continue

    for index, row in needs_llm:
        depth = depth_by_index.get(index)

        if depth and depth.document_a_supported and depth.document_b_supported:
            row.unverified = False
            report.verified.append(row)
        else:
            row.unverified = True

    report.verified = [row for row in all_rows if not row.unverified]
    report.re_retrieve = [row for row in all_rows if row.unverified]

    return report