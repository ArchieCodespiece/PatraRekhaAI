"""Hybrid document classification for the intake gatekeeper.

Approach (cheap-to-expensive):

1. Deterministic signals on metadata / filename / email provenance.
2. Regex signals on extracted text (existing text-extraction utilities),
   plus sensitive markers recorded as metadata signals.
3. Optional LLM classification (GROQ, gated) only when the deterministic
   result is ambiguous.

Sensitive markers (PAN / IFSC / account numbers, ...) NEVER decide the
outcome — they only add audit signals.  The workspace policy decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from gatekeeper import categories as category_data


_MATCH_CAP = 3


@dataclass(frozen=True)
class ClassificationResult:
    category: str = "other"
    confidence: float = 0.0
    signals: list[dict] = field(default_factory=list)
    reason: str = "No signals detected"
    method: str = "deterministic"


# ============================================================================
# Signal scoring
# ============================================================================

_COMPILED_SIGNAL_PATTERNS = category_data.compile_all_signal_patterns()
_COMPILED_FILENAME_HINTS = category_data.compile_filename_hints()


_SIGNAL_WEIGHTS = {
    signal.category: signal.weight
    for signal in category_data.SIGNAL_PATTERNS
}


def _signal_score(category: str, text: str) -> float:
    patterns = _COMPILED_SIGNAL_PATTERNS.get(category, [])
    if not patterns:
        return 0.0
    weight = _SIGNAL_WEIGHTS.get(category, 1.0)
    count = sum(
        min(_MATCH_CAP, len(pattern.findall(text)))
        for pattern in patterns
    )
    return weight * count


def _filename_score(category: str, filename: str) -> float:
    patterns = _COMPILED_FILENAME_HINTS.get(category, [])
    if not patterns:
        return 0.0
    count = sum(
        min(1, len(pattern.findall(filename)))
        for pattern in patterns
    )
    return 2.0 * count


# ============================================================================
# Sensitive marker detection (audit metadata only)
# ============================================================================

_SENSITIVE_LABELS = (
    "pan",
    "ifsc",
    "gstin",
    "account_number",
    "aadhaar",
)


def detect_sensitive_markers(text: str) -> list[str]:
    """Return marker labels matched in the text.  Advisory only."""
    found = []
    for label, pattern in zip(
        _SENSITIVE_LABELS,
        category_data.SENSITIVE_MARKERS,
    ):
        if pattern.search(text):
            found.append(label)
    return found


# ============================================================================
# Provenance / email-intent hints
# ============================================================================

_INTENT_TO_CATEGORY = {
    "NOTICE": "legal_notice",
}

_SUBJECT_HINT_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "legal_notice",
        re.compile(r"\bnotice\b|\bcircular\b", re.IGNORECASE),
    ),
    (
        "invoice",
        re.compile(r"\binvoice\b|\bbill\b", re.IGNORECASE),
    ),
    (
        "contract",
        re.compile(r"\bcontract\b|\bagreement\b|\bnda\b", re.IGNORECASE),
    ),
    (
        "resume",
        re.compile(r"\b(resume|cv|application|hiring)\b", re.IGNORECASE),
    ),
    (
        "purchase_order",
        re.compile(r"\bpurchase order\b|\bpo\b", re.IGNORECASE),
    ),
]


def _provenance_hints(document: Mapping) -> list[dict]:
    """Return weakly-weighted hints derived from email provenance."""
    signals: list[dict] = []
    provenance = document.get("provenance") or document.get("email_context") or {}

    intent = (provenance.get("email_intent") or "").strip().upper()
    if intent in _INTENT_TO_CATEGORY:
        signals.append(
            {
                "type": "provenance",
                "category": _INTENT_TO_CATEGORY[intent],
                "detail": intent,
            }
        )

    subject = str(provenance.get("subject") or "")
    for category, pattern in _SUBJECT_HINT_PATTERNS:
        if pattern.search(subject):
            signals.append(
                {
                    "type": "subject",
                    "category": category,
                    "detail": subject[:80],
                }
            )
            break

    return signals


# ============================================================================
# Classifier
# ============================================================================

def classify(
    document: Mapping,
    text: str | None = None,
    llm_enabled: bool = False,
    include_sensitive: bool = True,
) -> ClassificationResult:
    """
    Classify a document into one of the predefined categories.

    ``document`` may carry:
        filename, file_type, provenance{subject, sender, email_intent}
    ``text`` is already-extracted document text when available.
    """

    filename = str(document.get("filename") or document.get("name") or "")
    subject = str(
        (document.get("provenance") or {}).get("subject")
        or document.get("subject")
        or ""
    )

    searchable = f"{filename}\n{subject}"
    if text:
        searchable = f"{searchable}\n{text}"

    signals: list[dict] = []

    provenance_hints = _provenance_hints(document)

    scores: dict[str, float] = {
        category: 0.0
        for category in category_data.DEFAULT_CATEGORIES
    }

    # Each provenance hint nudges its category by a small fixed amount.
    for hint in provenance_hints:
        category = hint.get("category")
        if category in scores:
            scores[category] += 0.4
        signals.append(
            {
                "type": "provenance",
                "category": category,
                "detail": hint.get("detail"),
            }
        )

    # Filename hints (strong).
    if filename:
        for category in scores:
            score = _filename_score(category, filename)
            if score > 0:
                scores[category] += score
                signals.append(
                    {
                        "type": "filename",
                        "category": category,
                    }
                )

    # Text signals (dominant when present).
    if text:
        for category in scores:
            score = _signal_score(category, text)
            if score > 0:
                scores[category] += score
                signals.append(
                    {
                        "type": "keyword",
                        "category": category,
                        "count": min(
                            _MATCH_CAP,
                            _match_count(category, text),
                        ),
                    }
                )

    best = _rank_scores(scores)

    # Sensitive markers (advisory only — never a decision).
    sensitive: list[str] = []
    if include_sensitive and text:
        sensitive = detect_sensitive_markers(text)
        for marker in sensitive:
            signals.append({"type": "sensitive", "category": marker})

    if best and best[0][1] <= 0:
        category = "other"
        confidence = 0.0
        reason = "No signals detected"
    else:
        category = best[0][0]
        confidence = _confidence_from_scores(scores)
        reason = _build_reason(category, scores, sensitive)

    result = ClassificationResult(
        category=category,
        confidence=confidence,
        signals=signals,
        reason=reason,
        method="deterministic",
    )

    # ------------------------------------------------------------------
    # Optional LLM refinement, only when deterministic result is weak.
    # ------------------------------------------------------------------
    if (
        llm_enabled
        and text
        and confidence < 0.55
    ):
        llm_result = _try_llm(document, text)
        if llm_result is not None:
            return llm_result

    return result


def _match_count(category: str, text: str) -> int:
    patterns = _COMPILED_SIGNAL_PATTERNS.get(category, [])
    return sum(
        min(_MATCH_CAP, len(pattern.findall(text)))
        for pattern in patterns
    )


def _rank_scores(scores: Mapping[str, float]) -> list[tuple[str, float]]:
    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [(category, score) for category, score in ranked]


def _confidence_from_scores(scores: Mapping[str, float]) -> float:
    ranked = [score for _, score in _rank_scores(scores)]
    top = ranked[0] if ranked else 0.0
    second = ranked[1] if len(ranked) > 1 else 0.0

    if top <= 0:
        return 0.0

    if top - second >= 4.0:
        return 0.97

    if top - second >= 2.0:
        return 0.8

    if top - second >= 0.5:
        return 0.6

    return 0.4


def _build_reason(
    category: str,
    scores: Mapping[str, float],
    sensitive: list[str],
) -> str:
    parts = []
    top_score = scores.get(category, 0.0)
    if top_score > 0:
        parts.append(
            f"Matched {category} signals ({top_score:.1f})"
        )
    else:
        parts.append("No strong category signals")

    if sensitive:
        parts.append(
            "contains sensitive marker(s): " + ", ".join(sorted(sensitive))
        )

    return "; ".join(parts)


def _try_llm(document: Mapping, text: str) -> ClassificationResult | None:
    try:
        from gatekeeper.llm import llm_classify

        return llm_classify(document, text)
    except Exception:
        return None


def searchable_text_for(raw_text: str) -> str:
    """Normalize extracted text for signal scanning."""
    return re.sub(r"\s+", " ", (raw_text or "")).strip()