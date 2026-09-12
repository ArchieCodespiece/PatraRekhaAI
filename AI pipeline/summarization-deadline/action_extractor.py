"""Action and obligation extraction with source grounding.

Extracts actionable requirements (mandatory tasks, obligations, filings)
from page-indexed document sentences. Actions are grounded in verbatim
source sentences, and any extracted deadlines must match deterministically
verified date entities.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

try:
    from document_preprocessing.date_utils import normalise_date_iso
except ImportError:
    from date_utils import normalise_date_iso


# Keywords indicating actionable obligations/requirements
OBLIGATION_PATTERNS = [
    re.compile(r"\b(?:shall|must|required to|needs? to|is obliged to)\s+([^\.\;\n]+)", re.IGNORECASE),
    re.compile(r"\b(?:submit|upload|furnish|deposit|provide|pay|deliver|forward)\s+([^\.\;\n]+)", re.IGNORECASE),
    re.compile(r"\b(?:responsible for|duty of|obligation to)\s+([^\.\;\n]+)", re.IGNORECASE),
]

_PARTY_PATTERNS = [
    re.compile(r"\b(bidder|applicant|contractor|vendor|supplier|authority|agency|employer|department|candidate|purchaser|party)\b", re.IGNORECASE),
]

_DOC_PATTERNS = [
    re.compile(r"\b(form\s*\d+[a-z]?|affidavit|certificate|statement|annexure\s*[a-z0-9]+|schedule\s*[a-z0-9]+|receipt|guarantee|dd|demand draft|pan|gstin?|itr)\b", re.IGNORECASE),
]


def extract_candidate_action_sentences(
    sentences: Iterable[dict[str, Any] | Any],
) -> list[dict[str, Any]]:
    """Filter sentences to those containing obligation or action markers."""
    candidates = []
    seen = set()

    for item in sentences:
        if isinstance(item, dict):
            page = item.get("page")
            text = (item.get("text") or item.get("sentence") or "").strip()
        else:
            page = getattr(item, "page", None)
            text = (getattr(item, "text", "") or getattr(item, "sentence", "")).strip()

        if not text or text in seen:
            continue

        is_actionable = any(p.search(text) for p in OBLIGATION_PATTERNS)
        if is_actionable:
            seen.add(text)
            candidates.append({"page": page, "text": text})

    return candidates


def _find_matching_date(sentence_text: str, verified_dates: list[dict[str, Any]]) -> str | None:
    """Find a verified date occurring in the given sentence text."""
    lower_sent = sentence_text.lower()
    for d in verified_dates:
        raw = (d.get("raw") or "").lower()
        if raw and raw in lower_sent:
            return d.get("normalized") or d.get("date")
        normalized = (d.get("normalized") or "").lower()
        if normalized and normalized in lower_sent:
            return d.get("normalized")
        date_str = (d.get("date") or "").lower()
        if date_str and date_str in lower_sent:
            return d.get("normalized") or d.get("date")
    return None


def extract_actions_deterministic(
    sentences: Iterable[dict[str, Any] | Any],
    verified_dates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Extract actions deterministically using regex pattern matching and grounding."""
    verified_dates = verified_dates or []
    candidates = extract_candidate_action_sentences(sentences)
    actions = []

    for item in candidates:
        text = item["text"]
        page = item["page"]

        # Determine responsible party
        party_match = None
        for p in _PARTY_PATTERNS:
            m = p.search(text)
            if m:
                party_match = m.group(0).capitalize()
                break
        responsible_party = party_match or "Applicant / Bidder"

        # Determine required documents
        required_docs = []
        for p in _DOC_PATTERNS:
            for m in p.finditer(text):
                doc_name = m.group(0).strip()
                if doc_name and doc_name not in required_docs:
                    required_docs.append(doc_name)

        # Ground deadline in verified dates
        deadline = _find_matching_date(text, verified_dates)

        # Extract primary action clause
        action_desc = text
        for p in OBLIGATION_PATTERNS:
            m = p.search(text)
            if m:
                matched_clause = m.group(0).strip()
                if len(matched_clause) > 10:
                    action_desc = matched_clause
                    break

        actions.append({
            "action": action_desc[:200].strip(),
            "responsible_party": responsible_party,
            "deadline": deadline,
            "required_documents": required_docs,
            "location_or_method": "Submission portal / specified address" if "portal" in text.lower() or "online" in text.lower() else None,
            "status": "PENDING",
            "page": page,
            "source_sentence": text,
        })

    return actions


def extract_actions(
    sentences: Iterable[dict[str, Any] | Any],
    verified_dates: list[dict[str, Any]] | None = None,
    llm_client: Any = None,
    language_name: str = "English",
) -> list[dict[str, Any]]:
    """Main action extraction pipeline: deterministic base + optional LLM structuring.
    
    Ensures strict grounding: Any extracted deadline must exist in `verified_dates`.
    """
    verified_dates = verified_dates or []
    deterministic_actions = extract_actions_deterministic(sentences, verified_dates)

    if not llm_client or not deterministic_actions:
        return deterministic_actions

    # If LLM client is available, refine and structure the top candidate sentences (max 12)
    top_candidates = deterministic_actions[:12]
    payload = "\n".join(
        f"[{idx}] Page {act['page']}: {act['source_sentence']}"
        for idx, act in enumerate(top_candidates)
    )

    allowed_dates = [
        d.get("normalized") for d in verified_dates if d.get("normalized")
    ]

    system_prompt = (
        "You are an action and obligation extraction engine. "
        "You will be given numbered sentences from a legal/administrative document. "
        "Extract structured actions/obligations. "
        "Strict rules:\n"
        "1. NEVER invent actions or obligations not stated in the sentences.\n"
        "2. Any deadline MUST come from the text and match one of these verified dates: "
        f"{json.dumps(allowed_dates)}. If no date from that list applies, set deadline to null.\n"
        "3. Identify responsible_party (e.g. Applicant, Bidder, Authority).\n"
        "4. Return valid JSON with key 'actions' containing an array of objects with keys: "
        "index (integer), action (string), responsible_party (string), deadline (string or null), "
        "required_documents (array of strings), location_or_method (string or null)."
    )

    try:
        completion = llm_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            temperature=0,
            max_completion_tokens=1000,
            stream=False,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or "{}"
        data = json.loads(content)
        items = data.get("actions") or []

        refined_actions = []
        for item in items:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if not isinstance(idx, int) or not (0 <= idx < len(top_candidates)):
                continue
            base = top_candidates[idx]
            raw_deadline = item.get("deadline")
            valid_deadline = None
            if raw_deadline and normalise_date_iso(raw_deadline) in allowed_dates:
                valid_deadline = normalise_date_iso(raw_deadline)
            elif base.get("deadline"):
                valid_deadline = base.get("deadline")

            refined_actions.append({
                "action": str(item.get("action") or base["action"]).strip(),
                "responsible_party": str(item.get("responsible_party") or base["responsible_party"]).strip(),
                "deadline": valid_deadline,
                "required_documents": item.get("required_documents") or base["required_documents"],
                "location_or_method": item.get("location_or_method") or base["location_or_method"],
                "status": "PENDING",
                "page": base["page"],
                "source_sentence": base["source_sentence"],
            })

        if refined_actions:
            return refined_actions
    except Exception:
        pass

    return deterministic_actions
