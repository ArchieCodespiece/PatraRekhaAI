"""Strict prompt contracts for the LLM polishing stage.

The LLM only ever polishes/classifies already-grounded material. These
contracts make that explicit and are paired with post-validation in the
pipeline (dates must round-trip against the verified entity set).
"""

from __future__ import annotations

import json
import re

from typing import Any


def build_summary_polish_messages(
    sentences: list[str],
    language_name: str,
) -> list[dict[str, str]]:
    """Messages for summarising a set of verified source sentences.

    The model must rewrite ONLY the supplied sentences. Facts outside the
    sentences are forbidden.
    """
    numbered = "\n".join(
        f"- {seq}. {sent}" for seq, sent in enumerate(sentences, start=1)
    )
    system = (
        "You are a document summarization engine. "
        "You will be given numbered source sentences extracted verbatim from "
        "a document. Produce a concise, coherent summary, a list of key "
        "points, and a list of topics. "
        "Follow these rules strictly:\n"
        "1. Use ONLY the supplied sentences. Do not add facts, names, dates, "
        "or figures that are not present in them.\n"
        "2. Do not invent document headings or citations.\n"
        "3. Preserve names, numbers, organization names, and legal terms "
        "exactly as written.\n"
        f"4. Write the summary in {language_name} if the document's primary "
        "language is not English; otherwise English.\n"
        "Return only valid JSON with keys: summary (string), "
        "key_points (array of strings), topics (array of short strings)."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": numbered},
    ]


def build_date_classify_messages(
    entities: list[dict[str, Any]],
    language_name: str,
) -> list[dict[str, str]]:
    """Messages for classifying verified date entities.

    Dates are fixed ground truth. The model may attach an event_type and a
    short event label, but it may never add, modify, or drop dates.
    """
    payload = "\n".join(
        f"- index={idx} | date={ent.get('date')} | "
        f"context={ent.get('context_before')} "
        f"[DATE] {ent.get('context_after')}"
        for idx, ent in enumerate(entities)
    )
    system = (
        "You are a date classification engine. You will be given a list of "
        "verified dates extracted from a document, each with surrounding "
        "context.\n"
        "For every date, output one object with keys: index (same as input), "
        "event_type (one of: DEADLINE, SUBMISSION, START, END, MEETING, "
        "PAYMENT, AWARD, NOTIFICATION, VISIT, OTHER), event_label (a short "
        "2-8 word plain-language label, e.g. 'Deadline for bid submission').\n"
        "Rules:\n"
        "1. You may NOT invent, change, or add dates. Use the supplied dates "
        "and context exactly.\n"
        "2. If a date has no clear event context, use event_type OTHER and "
        "event_label from the context, or 'Important date'.\n"
        f"3. Write event_label in {language_name} unless English.\n"
        "Return only valid JSON with key 'dates' (array of the objects above)."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": payload},
    ]


def parse_json_object(content: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_summary_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(data.get("summary") or "").strip(),
        "key_points": [
            str(p).strip()
            for p in (data.get("key_points") or [])
            if p and str(p).strip()
        ],
        "topics": [
            str(t).strip()
            for t in (data.get("topics") or [])
            if t and str(t).strip()
        ],
    }


def normalize_date_classification(
    data: dict[str, Any],
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply model classifications only to verified entities.

    Post-validation: entries whose index/date is not in the supplied entity
    set are discarded and never merged in.
    """
    raw = data.get("dates") or []
    if not isinstance(raw, list):
        return {}

    by_index: dict[int, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(entities)):
            continue
        by_index[idx] = item

    classified: dict[int, dict[str, Any]] = {}
    for idx, ent in enumerate(entities):
        item = by_index.get(idx)
        if not item:
            continue
        event_type = str(item.get("event_type") or "OTHER").upper()
        if event_type not in {
            "DEADLINE", "SUBMISSION", "START", "END", "MEETING",
            "PAYMENT", "AWARD", "NOTIFICATION", "VISIT", "OTHER",
        }:
            event_type = "OTHER"
        event_label = str(item.get("event_label") or "Important date").strip()
        classified[idx] = {
            "event_type": event_type,
            "event_label": event_label,
        }

    return {"dates": classified}