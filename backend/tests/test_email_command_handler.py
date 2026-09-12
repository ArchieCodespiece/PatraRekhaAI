import unittest
from datetime import date, datetime, timezone
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.email_command_handler import (
    build_what_changed_reply,
    build_thread_summary_reply,
    handle_email_command,
    resolve_family_documents,
)


def _make_doc(file_id, heading, filename, dates=None, timeline=None,
              summarization=None, thread_id="thread-1", created_at=None):
    return {
        "file_id": file_id,
        "file_heading": heading,
        "filename": filename,
        "dates_json": dates or [],
        "timeline_json": timeline or [],
        "summarization": summarization,
        "thread_id": thread_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


_OLDER = _make_doc(
    "aaa11111-0000-0000-0000-000000000001",
    "Tender Notice - Construction Work",
    "notice.pdf",
    dates=[{"iso_date": "2026-03-31", "event": "Submission Deadline"}],
    timeline=[{"iso_date": "2026-03-31", "event_type": "DEADLINE", "event": "Submission Deadline"}],
    summarization="Original tender notice. Deadline on 31 March 2026.",
    created_at="2026-03-01T00:00:00Z",
)

_NEWER = _make_doc(
    "aaa11111-0000-0000-0000-000000000002",
    "Tender Notice - Construction Work (Amendment)",
    "amendment.pdf",
    dates=[{"iso_date": "2026-04-15", "event": "Submission Deadline"}],
    timeline=[{"iso_date": "2026-04-15", "event_type": "DEADLINE", "event": "Submission Deadline"}],
    summarization="Amendment extending the submission deadline to 15 April 2026.",
    created_at="2026-03-15T00:00:00Z",
)


class EmailCommandHandlerTests(unittest.TestCase):
    def test_resolve_family_prefers_thread(self):
        unrelated = _make_doc(
            "aaa11111-0000-0000-0000-000000000003",
            "Other Doc",
            "other.pdf",
            thread_id="thread-999",
        )
        docs = [_OLDER, _NEWER, unrelated]
        family = resolve_family_documents(docs, thread_id="thread-1")
        self.assertEqual(len(family), 2)
        self.assertEqual(family[0]["file_id"], _NEWER["file_id"])

    def test_what_changed_with_two_family_docs(self):
        title, body = build_what_changed_reply([_NEWER, _OLDER])
        self.assertIn("change", body.lower())
        self.assertIn("2026-03-31", body)
        self.assertIn("2026-04-15", body)
        self.assertIn("Tender Notice", title)

    def test_what_changed_single_doc_reports_no_prior_version(self):
        title, body = build_what_changed_reply([_NEWER])
        self.assertIn("No prior version", body)

    def test_thread_summary_reply(self):
        title, body = build_thread_summary_reply([_NEWER, _OLDER])
        self.assertIn("Amendment", body)
        self.assertEqual(body.count("\n\n"), 2)

    def test_handle_unknown_command_is_not_handled(self):
        result = handle_email_command(
            "No command here, just some plain text about anything.",
            owner_email="owner@example.com",
            sender="sender@example.com",
            hydrate_documents=lambda: [_NEWER, _OLDER],
            dispatch=lambda r, s, b: {"delivered": True},
        )
        self.assertFalse(result["handled"])

    def test_handle_what_changed_dispatches_reply(self):
        sent = []

        def dispatch(recipient, subject, body):
            sent.append((recipient, subject, body))
            return {"delivered": True}

        result = handle_email_command(
            "what changed?",
            owner_email="owner@example.com",
            sender="sender@example.com",
            thread_id="thread-1",
            hydrate_documents=lambda: [_NEWER, _OLDER],
            dispatch=dispatch,
        )
        self.assertTrue(result["handled"])
        self.assertEqual(result["command"], "WHAT_CHANGED")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][0], "sender@example.com")
        self.assertIn("2026-03-31", sent[0][2])

    def test_handle_set_reminder_reply_inserts_deadline(self):
        result = handle_email_command(
            "remind me 2 days before.",
            owner_email="owner@example.com",
            sender="sender@example.com",
            thread_id="thread-1",
            hydrate_documents=lambda: [_NEWER, _OLDER],
            dispatch=lambda r, s, b: {"delivered": True},
        )
        self.assertTrue(result["handled"])
        self.assertEqual(result["command"], "SET_REMINDER")
        self.assertIn("2026/04/15", result["reply"])

    def test_handle_move_deadline_asks_for_confirmation(self):
        result = handle_email_command(
            "move the deadline to 30 April 2026.",
            owner_email="owner@example.com",
            sender="sender@example.com",
            thread_id="thread-1",
            hydrate_documents=lambda: [_NEWER, _OLDER],
            dispatch=lambda r, s, b: {"delivered": True},
        )
        self.assertTrue(result["handled"])
        self.assertEqual(result["command"], "MOVE_DEADLINE")
        self.assertIn("CONFIRM", result["reply"])
        self.assertIn("2026-04-30", result["reply"])

    def test_handle_move_deadline_confirmed_no_confirm_text(self):
        result = handle_email_command(
            "move the deadline to 30 April 2026.",
            owner_email="owner@example.com",
            sender="sender@example.com",
            thread_id="thread-1",
            confirmed=True,
            hydrate_documents=lambda: [_NEWER, _OLDER],
            dispatch=lambda r, s, b: {"delivered": True},
        )
        self.assertTrue(result["handled"])
        self.assertNotIn("Reply 'CONFIRM'", result["reply"])


if __name__ == "__main__":
    unittest.main()