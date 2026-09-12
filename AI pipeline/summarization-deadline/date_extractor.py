"""Deterministic date extraction with page-level spans.

Extracts date entities from page-annotated text using pattern matching
(numeric + written, English + Indic months). The LLM is NEVER allowed to
originate a date — it may only resolve spans that look date-like but failed
pattern normalisation, and results are post-validated against the source
text before being accepted.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from document_preprocessing.date_utils import (
    MONTH_KEYS_SORTED,
    dd_mm_yyyy_to_iso,
    lookup_month,
    normalise_date_dd_mm_yyyy,
    normalise_date_iso,
)

from sentence_indexer import (
    Sentence,
    index_pages,
    word_context,
)

_MONTH_ALT = "|".join(
    re.escape(name) for name in MONTH_KEYS_SORTED
)

_NUMERIC_PATTERNS = [
    # DD/MM/YYYY, DD-MM-YYYY
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"),
    # DD.MM.YYYY
    re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b"),
    # ISO YYYY-MM-DD
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]

_WRITTEN_DAY_FIRST = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALT})(?:\s*,)?\s+(\d{{2,4}})\b",
    re.IGNORECASE,
)

_WRITTEN_MONTH_FIRST = re.compile(
    rf"\b({_MONTH_ALT})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(\d{{2,4}})\b",
    re.IGNORECASE,
)

# Candidate spans that "look" date-like but failed normalisation (misspelled
# month, novel romanisation, OCR garble). Fed to the LLM fallback only.
_DATE_LIKE_DAY_FIRST = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?[\s.-]+(\w+)\s+(\d{2,4})\b",
    re.IGNORECASE,
)
_DATE_LIKE_MONTH_FIRST = re.compile(
    r"\b(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(\d{2,4})\b",
    re.IGNORECASE,
)

EVENT_DEFAULT = "Important date"


def _iso_to_ddmmyyyy(year: str, month: str, day: str) -> str | None:
    return normalise_date_dd_mm_yyyy(f"{day}/{month}/{year}")


def _normalize_parts(parts: tuple[str, ...], iso: bool = False) -> str | None:
    if iso:
        year, month, day = parts
        return _iso_to_ddmmyyyy(year, month, day)

    if len(parts) == 3:
        first, second, third = parts
        if len(first) == 4 and len(second) == 2 and len(third) == 2:
            # Treat as ISO-style YYYY-MM-DD even without '-' separators.
            return _iso_to_ddmmyyyy(first, second, third)  # may fail; fall through
        return normalise_date_dd_mm_yyyy(f"{first}/{second}/{third}")
    return None


def extract_dates(
    pages: Iterable[dict[str, Any]],
    llm_client: Any = None,
    max_llm_candidates: int = 20,
) -> list[dict[str, Any]]:
    """Extract rich date entities from page-annotated text.

    Parameters
    ----------
    pages : iterable of {"page": int, "text": str}
        Page-annotated source text.
    llm_client : optional
        Groq-style client for resolving spans that fail pattern matching.
        When omitted, unparseable spans are dropped (deterministic only).
    max_llm_candidates : int
        Upper bound on spans sent to the LLM fallback per call.

    Returns
    -------
    list of dicts with keys
    raw, date (dd/mm/yyyy), type, page, sentence, context_before,
    context_after, source ("pattern" | "llm").
    """
    page_list = [dict(p) for p in pages]
    sentences = index_pages(page_list)
    page_by_no = {
        page.get("page"): page.get("text") or ""
        for page in page_list
    }

    entities: list[dict[str, Any]] = []
    seen_spans: set[tuple[int | None, int, int]] = set()
    llm_candidates: list[dict[str, Any]] = []

    for page in page_list:
        page_no = page.get("page")
        text = page.get("text") or ""
        if not text:
            continue

        matches: list[tuple[int, int, str, str]] = []

        for index, pattern in enumerate(_NUMERIC_PATTERNS):
            for m in pattern.finditer(text):
                start, end = m.span()
                if (page_no, start, end) in seen_spans:
                    continue
                iso = index == len(_NUMERIC_PATTERNS) - 1
                normalized = _normalize_parts(
                    m.groups(),
                    iso=iso,
                )
                if normalized:
                    matches.append((start, end, m.group(0), normalized))
                    seen_spans.add((page_no, start, end))

        for pattern in (_WRITTEN_DAY_FIRST, _WRITTEN_MONTH_FIRST):
            for m in pattern.finditer(text):
                start, end = m.span()
                if (page_no, start, end) in seen_spans:
                    continue
                groups = m.groups()
                if pattern is _WRITTEN_DAY_FIRST:
                    day, month_token, year = groups
                    month = lookup_month(month_token)
                    normalized = (
                        normalise_date_dd_mm_yyyy(f"{day}/{month}/{year}")
                        if month
                        else None
                    )
                else:
                    month_token, day, year = groups
                    month = lookup_month(month_token)
                    normalized = (
                        normalise_date_dd_mm_yyyy(f"{day}/{month}/{year}")
                        if month
                        else None
                    )
                if normalized:
                    matches.append((start, end, m.group(0), normalized))
                    seen_spans.add((page_no, start, end))

        # Date-like but unparseable candidates → bounded LLM fallback.
        if llm_client is not None and len(llm_candidates) < max_llm_candidates:
            for pattern in (_DATE_LIKE_DAY_FIRST, _DATE_LIKE_MONTH_FIRST):
                for m in pattern.finditer(text):
                    start, end = m.span()
                    if (page_no, start, end) in seen_spans:
                        continue
                    if len(llm_candidates) >= max_llm_candidates:
                        break
                    llm_candidates.append(
                        {
                            "page": page_no,
                            "start": start,
                            "end": end,
                            "snippet": text[start:end].strip(),
                        }
                    )
                    seen_spans.add((page_no, start, end))

        for start, end, raw, normalized in matches:
            entities.append(
                _build_entity(
                    page_no=page_no,
                    page_text=text,
                    sentences=sentences,
                    start=start,
                    end=end,
                    raw=raw,
                    source="pattern",
                    date=normalized,
                )
            )

    if llm_candidates and llm_client is not None:
        resolved = _resolve_candidates_llm(
            llm_candidates,
            llm_client,
        )
        for cand, normalized in resolved:
            if not normalized:
                continue
            entities.append(
                _build_entity(
                    page_no=cand["page"],
                    page_text=page_by_no.get(cand["page"], ""),
                    sentences=sentences,
                    start=cand["start"],
                    end=cand["end"],
                    raw=cand["snippet"],
                    source="llm",
                    date=normalized,
                )
            )

    return _dedupe_same_date_same_sentence(entities)


def _build_entity(
    page_no: int | None,
    page_text: str,
    sentences: list[Sentence],
    start: int,
    end: int,
    raw: str,
    source: str,
    date: str | None,
) -> dict[str, Any]:
    sentence = None
    for sent in sentences:
        if sent.page != page_no:
            continue
        if sent.start <= start <= sent.end:
            sentence = sent
            break

    sentence_text = sentence.text if sentence else ""
    context = word_context(page_text, start, end, words=18)
    iso_date = dd_mm_yyyy_to_iso(date) if date else None

    return {
        "raw": raw.strip(),
        "normalized": iso_date,
        "display_date": date,
        "date": date,
        "type": "DATE",
        "page": page_no,
        "sentence": sentence_text,
        "source_sentence": sentence_text,
        "context_before": context["before"],
        "context_after": context["after"],
        "source": source,
        "extraction_method": source,
        "confidence": 1.0 if source == "pattern" else 0.85,
        "event_type": None,
        "event_label": None,
    }


def _dedupe_same_date_same_sentence(
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicates for the same (page, sentence, raw) span pair."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for ent in entities:
        key = (
            str(ent["page"]),
            (ent.get("sentence") or "").strip(),
            (ent.get("date") or ent.get("raw") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(ent)
    return unique


def _resolve_candidates_llm(
    candidates: list[dict[str, Any]],
    llm_client: Any,
) -> list[tuple[dict[str, Any], str | None]]:
    """Ask the LLM to identify which candidates are real dates and normalise.

    CONTRACT: the model is categorically forbidden from inventing dates. Its
    output is accepted only when every numeric component of the normalised
    date appears in the source snippet.
    """
    if not candidates:
        return []

    payload = "\n".join(
        f"[{idx}] {cand['snippet']}"
        for idx, cand in enumerate(candidates)
    )

    try:
        completion = llm_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a date verification tool. You will be given "
                        "text snippets in brackets `[N] ...` that may or may not "
                        "contain a date. For each real, complete date you find, "
                        "return exactly one JSON object with keys `index` (the N), "
                        "`normalized` (dd/mm/yyyy). "
                        "You may ONLY use a date exactly as written in the snippet. "
                        "If a snippet has no complete date, omit it. "
                        "NEVER invent, change, or guess a date. "
                        "Return a JSON array."
                    ),
                },
                {
                    "role": "user",
                    "content": payload,
                },
            ],
            temperature=0,
            max_completion_tokens=800,
            top_p=1,
            stream=False,
        )
        content = completion.choices[0].message.content or "[]"
    except Exception:
        return []

    result: list[tuple[dict[str, Any], str | None]] = []
    items = _extract_json_array(content)
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(candidates)):
            continue
        normalized = item.get("normalized")
        if not isinstance(normalized, str):
            continue
        canonical = normalise_date_dd_mm_yyyy(normalized)
        if not canonical:
            continue
        snippet = candidates[idx]["snippet"]
        if not _date_parts_in_snippet(canonical, snippet):
            continue
        # Accept only spans the extraction step did not already resolve.
        result.append((candidates[idx], canonical))

    return result


def _extract_json_array(content: str) -> list:
    import json

    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, flags=re.DOTALL)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []


def _date_parts_in_snippet(canonical: str, snippet: str) -> bool:
    """Verify every *verifiable* component of a normalised date appears in the snippet.

    Day and year must always appear as digit tokens (anti-invention guard).
    The month is checked against the digit tokens only when the snippet does
    not name the month in words — a written month cannot be verified
    numerically, so its spelling is the ground truth the LLM must map.
    """
    day, month, year = canonical.split("/")
    tokens = re.findall(r"\d+", snippet)
    if (
        str(int(day)) not in tokens
        or str(int(year)) not in tokens
    ):
        return False

    # Unicode letter (any script) present → the month is written in words.
    if re.search(r"[^\W\d_]", snippet, flags=re.UNICODE):
        return True

    return str(int(month)) in tokens