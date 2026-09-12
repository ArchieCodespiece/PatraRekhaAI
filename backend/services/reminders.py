"""Deadline reminder calculation and scheduler logic.

Supports:
- 2 days before
- 1 day before
- Same day
- Weekly digest
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from document_preprocessing.date_utils import normalise_date_iso


REMINDER_TYPES = ("2_days_before", "1_day_before", "same_day", "weekly_digest")


def calculate_reminder_dates(deadline_date: date) -> dict[str, date]:
    """Calculate the exact trigger dates for standard deadline reminders."""
    return {
        "2_days_before": deadline_date - timedelta(days=2),
        "1_day_before": deadline_date - timedelta(days=1),
        "same_day": deadline_date,
    }


def is_reminder_due(
    scheduled_for: date,
    current_date: date | None = None,
) -> bool:
    """Check if a reminder scheduled date is due (today or earlier)."""
    current_date = current_date or date.today()
    return scheduled_for <= current_date


def generate_reminders_for_deadline(
    deadline_iso: str,
    event_label: str,
    document_id: str,
    document_name: str,
    recipient_email: str,
) -> list[dict[str, Any]]:
    """Generate the set of scheduled reminders for a given deadline."""
    iso = normalise_date_iso(deadline_iso)
    if not iso:
        return []

    try:
        dt = date.fromisoformat(iso)
    except ValueError:
        return []

    schedule = calculate_reminder_dates(dt)
    reminders = []

    for r_type, sched_date in schedule.items():
        reminders.append({
            "reminder_id": f"rem_{document_id}_{r_type}_{sched_date.isoformat()}",
            "document_id": document_id,
            "document_name": document_name,
            "event": event_label,
            "deadline": iso,
            "recipient_email": recipient_email,
            "reminder_type": r_type,
            "scheduled_for": sched_date.isoformat(),
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return reminders


def find_due_reminders(
    reminders: list[dict[str, Any]],
    current_date: date | None = None,
) -> list[dict[str, Any]]:
    """Filter reminders that are pending and due for dispatch."""
    current_date = current_date or date.today()
    due = []
    for r in reminders:
        if r.get("status") != "PENDING":
            continue
        sched = r.get("scheduled_for")
        if not sched:
            continue
        try:
            sched_dt = date.fromisoformat(sched)
            if is_reminder_due(sched_dt, current_date=current_date):
                due.append(r)
        except ValueError:
            continue
    return due
