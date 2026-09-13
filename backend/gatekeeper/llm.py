"""Optional LLM document classification (GROQ, gated).

Only used when the deterministic classifier is ambiguous AND the
administrator explicitly enables it:

    INTAKE_GATEKEEPER_LLM_ENABLED=1
    GROQ_API_KEY=...

Follows the same HTTP/GROQ pattern already used by the
summarization-deadline pipeline.  Any failure degrades gracefully back to
the deterministic result — the LLM is advisory only.
"""

from __future__ import annotations

import json
import os
from typing import Mapping

from gatekeeper import categories as category_data
from gatekeeper.classifier import ClassificationResult


MODEL = os.getenv("INTAKE_LLM_MODEL", "openai/gpt-oss-20b")

_VALID_CATEGORIES = sorted(category_data.DEFAULT_CATEGORIES)


def llm_enabled() -> bool:
    return bool(
        os.getenv("INTAKE_GATEKEEPER_LLM_ENABLED", "")
        in {"1", "true", "True", "yes"}
        and os.getenv("GROQ_API_KEY")
    )


def _build_prompt(document: Mapping, text: str) -> str:
    filename = str(
        document.get("filename") or document.get("name") or ""
    )
    subject = str(
        (document.get("provenance") or {}).get("subject")
        or document.get("subject")
        or ""
    )

    return (
        "You are a document intake classifier. Classify the document into "
        f"exactly one of these JSON categories: {json.dumps(_VALID_CATEGORIES, ensure_ascii=False)}.\n\n"
        f"Filename: {filename}\n"
        f"Subject: {subject}\n\n"
        "Document text (truncated):\n"
        f"{text[:4000]}\n\n"
        "Reply with a single JSON object of the form:\n"
        '{"category": <one of the categories>, "confidence": <0.0-1.0>, '
        '"reason": "<short reason>"}\n'
        'Example: {"category": "invoice", "confidence": 0.95, '
        '"reason": "Vendor invoice"}\n\n'
        "IMPORTANT: Detecting an account number, PAN, IFSC or GSTIN does "
        "NOT make a document sensitive by itself — classify by what the "
        "document actually is (invoice, contract, bank statement, ...)."
    )


def llm_classify(document: Mapping, text: str) -> ClassificationResult | None:
    """Run GROQ classification.  Returns None on any failure/unsupported setup."""
    if not llm_enabled():
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise document classifier. "
                        "Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(document, text),
                },
            ],
            temperature=0,
            max_completion_tokens=200,
            top_p=1,
            stream=False,
        )

    except Exception:
        return None

    content = ""
    try:
        content = completion.choices[0].message.content or ""
    except Exception:
        return None

    payload = _parse_json_object(content)
    if not payload:
        return None

    category = str(payload.get("category") or "").strip().lower()
    if category not in _VALID_CATEGORIES:
        return None

    try:
        confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.5

    reason = str(payload.get("reason") or "").strip() or "LLM classification"

    return ClassificationResult(
        category=category,
        confidence=confidence,
        signals=[{"type": "llm", "category": category}],
        reason=reason,
        method="llm",
    )


def _parse_json_object(content: str) -> dict:
    content = (content or "").strip()

    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        start = content.index("{")
        end = content.rindex("}")
        return json.loads(content[start : end + 1])
    except (ValueError, json.JSONDecodeError):
        return {}