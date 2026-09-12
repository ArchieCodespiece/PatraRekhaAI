import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.email_cleaner import (
    strip_html_tags,
    clean_email_body,
    classify_email_intent,
    build_email_provenance,
)


class EmailCleanerTests(unittest.TestCase):
    def test_strip_html_tags(self):
        raw_html = "<p>Dear Vendor,<br/>Please submit documents before tomorrow.</p><style>body {color: red;}</style>"
        cleaned = strip_html_tags(raw_html)
        self.assertNotIn("<p>", cleaned)
        self.assertNotIn("<style>", cleaned)
        self.assertIn("Dear Vendor", cleaned)
        self.assertIn("Please submit documents", cleaned)

    def test_clean_email_body_strips_signatures_and_replies(self):
        raw_text = (
            "Please review the attached contract for project alpha.\n\n"
            "Thanks & Regards,\n"
            "John Doe\n"
            "Senior Executive\n\n"
            "On Mon, Jan 12, 2026 at 10:00 AM, Jane wrote:\n"
            "> Previous message text here."
        )
        cleaned = clean_email_body(raw_text)
        self.assertIn("Please review the attached contract for project alpha.", cleaned)
        self.assertNotIn("Previous message text here", cleaned)
        self.assertNotIn("Senior Executive", cleaned)

    def test_classify_email_intent(self):
        self.assertEqual(classify_email_intent("Corrigendum #1 for Tender 2026", "Revision of submission schedule"), "AMENDMENT")
        self.assertEqual(classify_email_intent("Extension of deadline for RFP", "The date has been extended"), "DEADLINE_CHANGE")
        self.assertEqual(classify_email_intent("Urgent Reminder", "Please respond today"), "REMINDER")
        self.assertEqual(classify_email_intent("Shortlist Result Announced", "Candidate merit list attached"), "RESULT")
        self.assertEqual(classify_email_intent("General Announcement", "Office will be closed on Friday"), "INFORMATIONAL")

    def test_build_email_provenance(self):
        attachment_prov = build_email_provenance(
            source_type="attachment",
            email_id="msg_12345",
            thread_id="thread_999",
            filename="Tender.pdf",
            page=4,
        )
        self.assertEqual(attachment_prov["source_type"], "attachment")
        self.assertEqual(attachment_prov["filename"], "Tender.pdf")
        self.assertEqual(attachment_prov["page"], 4)

        body_prov = build_email_provenance(
            source_type="email",
            email_id="msg_12345",
            thread_id="thread_999",
            sender="tender@gov.in",
            subject="Tender Update",
            timestamp="2026-03-15T10:00:00Z",
        )
        self.assertEqual(body_prov["source_type"], "email")
        self.assertEqual(body_prov["sender"], "tender@gov.in")
        self.assertEqual(body_prov["subject"], "Tender Update")


if __name__ == "__main__":
    unittest.main()
