"""Reminder scheduler for Gmail-connected users.

Scans all active Gmail connections, loads each user's documents,
computes deadlines from their timeline/dates_json, generates
standard reminders (2 days before, 1 day before, same day),
and dispatches due reminders back via Gmail.

Run once per day (cron) or loop with ``--loop``.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timezone
from typing import Any, Callable

from services.email_sender import send_outbound_notification
from services.reminders import (
    generate_reminders_for_deadline,
    find_due_reminders,
)


# ============================================================================
# In-memory dedup (process lifetime only)
# ============================================================================

_DISPATCHED: set[str] = set()


def _was_dispatched(reminder_id: str) -> bool:
    return reminder_id in _DISPATCHED


def _mark_dispatched(reminder_id: str) -> None:
    _DISPATCHED.add(reminder_id)


# ============================================================================
# Deadline extraction
# ============================================================================

def extract_deadline_dates(
    document: dict[str, Any],
) -> list[tuple[str, str]]:
    """Return (iso_date, event_label) pairs from a document.

    Pulls from dates_json (hybrid) with timeline_json fallback,
    matching the pattern used by deadlines.py and calendar.py.
    """
    items = (
        document.get("dates_json")
        or document.get("timeline_json")
        or []
    )

    if isinstance(items, str):
        import json
        try:
            items = json.loads(items)
        except Exception:
            items = []

    if not isinstance(items, list):
        return []

    results = []

    for item in items:
        if not isinstance(item, dict):
            continue

        iso = (
            item.get("iso_date")
            or item.get("date")
            or ""
        ).strip()

        if not iso:
            continue

        label = (
            item.get("event")
            or item.get("event_type")
            or "Deadline"
        )

        event_type = (item.get("event_type") or "").upper()

        if event_type in ("HOLIDAY", "WEEKEND", "NON_WORKING_DAY"):
            continue

        results.append((iso, label))

    return results


# ============================================================================
# Hydrate documents (lazy import)
# ============================================================================

def _default_hydrate(owner_email: str) -> list[dict[str, Any]]:
    from services.email_command_handler import (
        default_hydrate_documents,
    )
    return default_hydrate_documents(owner_email)


# ============================================================================
# Collect reminders across all active users
# ============================================================================

def collect_due_reminders(
    hydrate_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    connections_fn: (
        Callable[[], list[dict[str, Any]]] | None
    ) = None,
    current_date: date | None = None,
) -> list[dict[str, Any]]:
    """Return all currently due reminders across all active Gmail users.

    Each reminder includes ``_owner_email`` and ``_access_token`` keys
    for the dispatch step (not part of the reminder schema).
    """
    if connections_fn is None:
        from db.gmail_connections import list_gmail_connections
        connections_fn = list_gmail_connections

    hydrate = hydrate_fn or _default_hydrate
    today = current_date or date.today()
    all_due: list[dict[str, Any]] = []

    connections = connections_fn() or []

    for conn in connections:
        owner_email = (conn.get("owner_email") or "").strip().lower()
        access_token = conn.get("access_token")

        if not owner_email:
            continue

        try:
            documents = hydrate(owner_email) or []
        except Exception as exc:
            print(f"[scheduler] Failed to load docs for {owner_email}: {exc}")
            continue

        for doc in documents:
            doc_id = str(doc.get("file_id") or "")
            doc_name = (
                doc.get("file_heading")
                or doc.get("filename")
                or "Untitled"
            )

            if not doc_id:
                continue

            deadline_dates = extract_deadline_dates(doc)

            for iso_date, event_label in deadline_dates:
                reminders = generate_reminders_for_deadline(
                    deadline_iso=iso_date,
                    event_label=event_label,
                    document_id=doc_id,
                    document_name=doc_name,
                    recipient_email=owner_email,
                )

                due = find_due_reminders(reminders, current_date=today)

                for r in due:
                    r["_owner_email"] = owner_email
                    r["_access_token"] = access_token
                    all_due.append(r)

    return all_due


# ============================================================================
# Dispatch
# ============================================================================

def dispatch_due_reminders(
    reminders: list[dict[str, Any]],
    dispatch_fn: Callable[[str, str, str, str | None], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Send all due reminders that haven't been dispatched yet.

    Returns a list of dispatch results for audit logging.
    """
    if dispatch_fn is None:

        def _send(
            recipient: str,
            subject: str,
            body: str,
            access_token: str | None,
        ) -> dict[str, Any]:
            return send_outbound_notification(
                recipient,
                subject,
                body,
                access_token=access_token,
            )

        dispatch_fn = _send

    from services.email_sender import format_reminder_notification

    results = []

    for r in reminders:
        rid = r.get("reminder_id") or ""
        if _was_dispatched(rid):
            continue

        msg = format_reminder_notification(
            document_title=r.get("document_name") or "Document",
            event_label=r.get("event") or "Deadline",
            deadline_date=r.get("deadline") or "",
            reminder_type=r.get("reminder_type") or "reminder",
        )

        result = dispatch_fn(
            r.get("recipient_email") or r.get("_owner_email") or "",
            msg["subject"],
            msg["body"],
            r.get("_access_token"),
        )

        _mark_dispatched(rid)
        results.append(
            {
                "reminder_id": rid,
                "recipient": r.get("recipient_email"),
                "delivery": result,
            }
        )

    return results


# ============================================================================
# Public entry points
# ============================================================================

def run_once(
    hydrate_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    dispatch_fn: Callable[[str, str, str, str | None], dict[str, Any]] | None = None,
    connections_fn: (
        Callable[[], list[dict[str, Any]]] | None
    ) = None,
    current_date: date | None = None,
) -> dict[str, Any]:
    """Collect and dispatch all due reminders in one pass.

    Returns a summary dict for audit / CLI output.
    """
    due = collect_due_reminders(
        hydrate_fn=hydrate_fn,
        connections_fn=connections_fn,
        current_date=current_date,
    )

    results = dispatch_due_reminders(due, dispatch_fn=dispatch_fn)

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "due_count": len(due),
        "sent_count": len(results),
        "results": results,
    }


# ============================================================================
# CLI
# ============================================================================

_DEFAULT_INTERVAL = 6 * 60 * 60  # 6 hours


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PatraRekhaAI reminder scheduler"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously (default: run once and exit)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=_DEFAULT_INTERVAL,
        help=(
            f"Seconds between scheduler cycles (default: {_DEFAULT_INTERVAL})"
        ),
    )
    args = parser.parse_args()

    print("[scheduler] Starting reminder scheduler...")

    if not args.loop:
        summary = run_once()
        print(
            f"[scheduler] Done — "
            f"{summary['due_count']} due, "
            f"{summary['sent_count']} sent"
        )
        return

    print(
        f"[scheduler] Loop mode — interval={args.interval}s"
    )

    while True:
        try:
            summary = run_once()
            print(
                f"[scheduler] Cycle complete — "
                f"{summary['due_count']} due, "
                f"{summary['sent_count']} sent"
            )
        except Exception as exc:
            print(f"[scheduler] Error in cycle: {exc}")

        time.sleep(args.interval)


if __name__ == "__main__":
    main()