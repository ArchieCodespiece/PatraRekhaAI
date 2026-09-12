import unittest
from datetime import date
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.reminder_scheduler import (
    collect_due_reminders,
    dispatch_due_reminders,
    extract_deadline_dates,
    run_once,
)


def _make_doc(file_id, deadline_iso="2026-03-31", event="Submission",
              event_type="DEADLINE"):
    return {
        "file_id": file_id,
        "file_heading": f"Doc {file_id}",
        "filename": f"doc-{file_id}.pdf",
        "dates_json": [
            {"iso_date": deadline_iso, "event": event, "event_type": event_type}
        ],
    }


def _make_conn(owner_email="owner@example.com", access_token=None):
    return {
        "owner_email": owner_email,
        "access_token": access_token or "token-123",
    }


class ReminderSchedulerTests(unittest.TestCase):

    def test_extract_deadline_dates_filters_non_working_days(self):
        doc = {
            "dates_json": [
                {"iso_date": "2026-03-31", "event": "Submission", "event_type": "DEADLINE"},
                {"iso_date": "2026-04-01", "event": "Holiday", "event_type": "HOLIDAY"},
            ]
        }
        pairs = extract_deadline_dates(doc)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0], "2026-03-31")

    def test_extract_deadline_dates_string_json(self):
        import json
        doc = {
            "timeline_json": json.dumps([
                {"date": "2026-03-31", "event": "Closing", "event_type": "DEADLINE"}
            ])
        }
        pairs = extract_deadline_dates(doc)
        self.assertEqual(pairs[0], ("2026-03-31", "Closing"))

    def test_collect_due_reminders(self):
        def fake_conns():
            return [_make_conn("owner@example.com", "token-123")]

        def fake_hydrate(owner_email):
            return [_make_doc("doc_1", deadline_iso="2026-03-31")]

        due = collect_due_reminders(
            hydrate_fn=fake_hydrate,
            connections_fn=fake_conns,
            current_date=date(2026, 3, 29),
        )
        self.assertEqual(len(due), 1)
        r = due[0]
        self.assertEqual(r["reminder_type"], "2_days_before")
        self.assertEqual(r["recipient_email"], "owner@example.com")
        self.assertEqual(r["_access_token"], "token-123")

    def test_dispatch_due_reminders_and_dedup(self):
        sent = []

        def fake_dispatch(recipient, subject, body, access_token):
            sent.append((recipient, subject, body, access_token))
            return {"delivered": True}

        due = [
            {
                "reminder_id": "rem_doc_1_2_days_before_2026-03-29",
                "document_id": "doc_1",
                "document_name": "Doc doc_1",
                "event": "Submission",
                "deadline": "2026-03-31",
                "reminder_type": "2_days_before",
                "recipient_email": "owner@example.com",
                "scheduled_for": "2026-03-29",
                "status": "PENDING",
                "_owner_email": "owner@example.com",
                "_access_token": "token-123",
            }
        ]

        results = dispatch_due_reminders(due, dispatch_fn=fake_dispatch)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(sent), 1)

        # Second pass must not re-send the same reminder
        again = dispatch_due_reminders(due, dispatch_fn=fake_dispatch)
        self.assertEqual(len(again), 0)
        self.assertEqual(len(sent), 1)

    def test_run_once_summary(self):
        def fake_conns():
            return [_make_conn("owner@example.com")]

        def fake_hydrate(owner_email):
            return [_make_doc("doc_1", deadline_iso="2026-05-15")]

        sent = []

        def fake_dispatch(recipient, subject, body, access_token):
            sent.append((recipient, subject, body))
            return {"delivered": True}

        summary = run_once(
            hydrate_fn=fake_hydrate,
            dispatch_fn=fake_dispatch,
            connections_fn=fake_conns,
            current_date=date(2026, 5, 13),
        )
        self.assertEqual(summary["due_count"], 1)
        self.assertEqual(summary["sent_count"], 1)
        self.assertEqual(len(sent), 1)


if __name__ == "__main__":
    unittest.main()