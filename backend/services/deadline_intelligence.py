"""Normalized deadline intelligence, conflict detection, and priority scoring.

Provides:
- Normalized deadline objects with priority and status calculation
- Conflict detection across competing dates in related documents
- Status categorization: UPCOMING, DUE_SOON, OVERDUE, SUPERSEDED, CONFLICT
- Risk/priority tiers: CRITICAL (< 48h), HIGH (< 7d), MEDIUM (< 30d), LOW
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from document_preprocessing.date_utils import normalise_date_iso, iso_to_dd_mm_yyyy


def calculate_deadline_priority(deadline_date: date, today: date | None = None) -> str:
    """Calculate priority tier based on proximity:
    
    CRITICAL: < 48 hours (<= 2 days)
    HIGH: < 7 days
    MEDIUM: < 30 days
    LOW: >= 30 days
    """
    today = today or date.today()
    days_diff = (deadline_date - today).days

    if days_diff < 0:
        return "CRITICAL"  # Overdue is critical attention
    if days_diff <= 2:
        return "CRITICAL"
    if days_diff <= 7:
        return "HIGH"
    if days_diff <= 30:
        return "MEDIUM"
    return "LOW"


def calculate_deadline_status(
    deadline_date: date,
    is_superseded: bool = False,
    is_conflict: bool = False,
    completed: bool = False,
    today: date | None = None,
) -> str:
    """Determine normalized deadline status."""
    if completed:
        return "COMPLETED"
    if is_superseded:
        return "SUPERSEDED"
    if is_conflict:
        return "CONFLICT"

    today = today or date.today()
    days_diff = (deadline_date - today).days

    if days_diff < 0:
        return "OVERDUE"
    if days_diff <= 3:
        return "DUE_SOON"
    return "UPCOMING"


def build_deadline_model(
    raw_date: str,
    event_label: str,
    document_id: str,
    document_name: str,
    page: int | None = None,
    responsible_party: str | None = None,
    source_sentence: str | None = None,
    confidence: float = 1.0,
    status: str | None = None,
    superseded_by: str | None = None,
    today: date | None = None,
) -> dict[str, Any] | None:
    """Construct a fully normalized deadline intelligence entity."""
    iso_date = normalise_date_iso(raw_date)
    if not iso_date:
        return None

    try:
        dt = date.fromisoformat(iso_date)
    except ValueError:
        return None

    today = today or date.today()
    is_superseded = status == "SUPERSEDED" or bool(superseded_by)
    calc_status = status or calculate_deadline_status(dt, is_superseded=is_superseded, today=today)
    priority = calculate_deadline_priority(dt, today=today)

    return {
        "deadline": iso_date,
        "display_date": iso_to_dd_mm_yyyy(iso_date),
        "event": event_label.strip() or "Important date",
        "responsible_party": responsible_party or "Applicant / Bidder",
        "document_id": document_id,
        "document_name": document_name,
        "page": page,
        "source_sentence": source_sentence,
        "status": calc_status,
        "priority": priority,
        "superseded_by": superseded_by,
        "confidence": confidence,
    }


def detect_deadline_conflicts(
    deadlines: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect competing dates for the same event type across related documents.
    
    Returns a list of conflict records showing competing sources and dates.
    """
    # Group active (non-superseded, non-completed) deadlines by event/category
    grouped: dict[str, list[dict[str, Any]]] = {}

    for d in deadlines:
        if d.get("status") in ("SUPERSEDED", "COMPLETED"):
            continue

        event_key = (d.get("event") or "").lower().strip()
        # Normalize simple variants like "submission deadline" vs "deadline for submission"
        if any(w in event_key for w in ("submit", "submission", "bid")):
            group_name = "submission_deadline"
        elif any(w in event_key for w in ("payment", "fee", "deposit")):
            group_name = "payment_deadline"
        elif any(w in event_key for w in ("meeting", "conference", "pre-bid")):
            group_name = "meeting_date"
        else:
            group_name = event_key[:30]

        grouped.setdefault(group_name, []).append(d)

    conflicts = []
    for group_name, items in grouped.items():
        if len(items) <= 1:
            continue

        # Check distinct dates
        distinct_dates = {item["deadline"] for item in items if item.get("deadline")}
        if len(distinct_dates) > 1:
            # Different documents or sections claim conflicting deadlines!
            conflicts.append({
                "conflict_type": "DEADLINE_CONFLICT",
                "event_group": group_name,
                "competing_dates": sorted(list(distinct_dates)),
                "sources": [
                    {
                        "document_id": item.get("document_id"),
                        "document_name": item.get("document_name"),
                        "page": item.get("page"),
                        "deadline": item.get("deadline"),
                        "source_sentence": item.get("source_sentence"),
                    }
                    for item in items
                ],
                "description": (
                    f"Conflicting deadlines detected for {group_name}: "
                    f"{', '.join(sorted(list(distinct_dates)))} across {len(items)} sources."
                ),
            })

    return conflicts
