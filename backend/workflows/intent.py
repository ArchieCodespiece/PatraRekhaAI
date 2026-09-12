"""
Deterministic-first intent routing for the chat endpoint.

Routing order:

1. Regex / keyword fast-path for obvious commands.
2. Tiny LLM classifier ONLY when the query is ambiguous
   (>= 2 documents selected AND comparative language present).

Everyday chat bypasses the LLM entirely, preserving latency and cost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .llm import chat_json


@dataclass
class IntentResult:
    intent: str  # "normal" | "compare" | "export"
    target_format: Optional[str]  # "xlsx" | "pdf" | None
    method: str  # "regex" | "llm" | "default"


STRONG_COMPARE_TOKENS = (
    "compare",
    "comparison",
    "comparative",
    "difference",
    "differences",
    "differ",
    "different",
    "versus",
    " vs ",
    "vs ",
    "\bvs\b",
    "antar",
    "fark",
    "faraq",
    "tulna",
    "differentiate",
)

SOFT_COMPARE_TOKENS = (
    "better",
    "worse",
    "notably",
    "differs",
    "unlike",
    "which one",
    "notice period",
    "termination clause",
)

EXPORT_FORMAT_TOKENS = [
    ("xlsx", "xlsx"),
    (".xlsx", "xlsx"),
    ("excel", "xlsx"),
    ("spreadsheet", "xlsx"),
    ("csv", "xlsx"),
    (".pdf", "pdf"),
    ("pdf", "pdf"),
]

EXPORT_VERBS = (
    "export",
    "make",
    "generate",
    "create",
    "download",
    "produce",
    "prepare",
    "convert",
    "bana",
    "banao",
    "banaiye",
    "banay",
    "naiy",
)

CLASSIFIER_SYSTEM = (
    "You route a user request about legal/business documents into one of "
    "three intents. Respond ONLY with JSON.\n"
    '{"intent": "compare" | "export" | "normal", '
    '"target_format": "xlsx" | "pdf" | null, '
    '"reason": "short rationale"}\n\n'
    "- compare: the user asks to compare/differ/contrast two or more "
    "selected documents, or asks how clauses/terms differ between them.\n"
    "- export: the user asks to generate a downloadable file (PDF or "
    "spreadsheet/xlsx) from the selected documents.\n"
    "- normal: anything else.\n"
    "If the request is a comparison AND asks for a file, set intent to "
    "'compare' and target_format to the requested format."
)

_CLASSIFIER_CACHE: dict = {}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def detect_export_format(query: str) -> Optional[str]:
    normalized = " " + _normalize(query) + " "

    for token, fmt in EXPORT_FORMAT_TOKENS:
        if token in normalized:
            return fmt

    return None


def has_export_verb(query: str) -> bool:
    normalized = _normalize(query)

    return any(token in normalized for token in EXPORT_VERBS)


def has_strong_compare(query: str) -> bool:
    normalized = _normalize(query)

    for token in STRONG_COMPARE_TOKENS:
        pattern = re.compile(r"\b" + re.escape(token.strip()) + r"\b")
        if pattern.search(normalized):
            return True

    return False


def has_soft_compare(query: str) -> bool:
    normalized = _normalize(query)

    return any(token in normalized for token in SOFT_COMPARE_TOKENS)


def route_intent(
    query: str,
    selected_documents: List[str],
) -> IntentResult:
    """
    Route a chat query to normal / compare / export.

    Parameters
    ----------
    query : str
        The user's chat message.
    selected_documents : List[str]
        Document display names currently selected in the chat panel.
    """

    cleaned = [name for name in selected_documents if name and name.strip()]
    document_count = len(cleaned)

    target_format = detect_export_format(query)
    export_verb = has_export_verb(query)
    strong_compare = has_strong_compare(query)
    soft_compare = has_soft_compare(query)

    # A comparison needs at least two selected documents.
    can_compare = document_count >= 2

    # RegEx fast-path: an explicit comparison command.
    if strong_compare and can_compare:
        return IntentResult(
            intent="compare",
            target_format=target_format,
            method="regex",
        )

    # RegEx fast-path: an explicit export command.
    if target_format and (export_verb or target_format in ("xlsx", "csv")):
        return IntentResult(
            intent="export",
            target_format=target_format,
            method="regex",
        )

    if export_verb and re.search(
        r"\b(report|output|table|sheet|document|summary)\b",
        _normalize(query),
    ):
        return IntentResult(
            intent="export",
            target_format=target_format,
            method="regex",
        )

    # LLM fallback only for genuinely ambiguous comparative requests.
    if can_compare and (soft_compare or strong_compare):
        classified = _classify_with_llm(query, cleaned)

        if classified is not None:
            return classified

    return IntentResult(
        intent="normal",
        target_format=None,
        method="default",
    )


def _classify_with_llm(
    query: str,
    selected_documents: List[str],
) -> Optional[IntentResult]:
    """
    Ask a tiny classifier to pick an intent when heuristics are ambiguous.

    Safe no-op on failure: routing degrades to normal chat.
    """

    cache_key = query.lower().strip()

    if cache_key in _CLASSIFIER_CACHE:
        return _CLASSIFIER_CACHE[cache_key]

    summary = ", ".join(selected_documents[:5])

    try:
        payload = chat_json(
            CLASSIFIER_SYSTEM,
            (
                "Selected documents: " + summary + "\n\n"
                "User request: " + query
            ),
            temperature=0.0,
        )

        intent = str(payload.get("intent") or "normal").lower()
        target_format = str(
            payload.get("target_format") or ""
        ).lower()

        if intent not in ("normal", "compare", "export"):
            intent = "normal"

        if target_format not in ("xlsx", "pdf", "none", "null", ""):
            target_format = None

        if intent == "normal":
            result = IntentResult("normal", None, "llm")
        elif intent == "export":
            result = IntentResult(
                "export",
                target_format if target_format else None,
                "llm",
            )
        else:
            result = IntentResult(
                "compare",
                target_format if target_format else None,
                "llm",
            )

        _CLASSIFIER_CACHE[cache_key] = result

        return result

    except Exception:
        return None