import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from action_extractor import extract_actions_deterministic, extract_actions


class ActionExtractorTests(unittest.TestCase):
    def test_extract_deterministic_obligation_with_deadline_grounding(self):
        sentences = [
            {"page": 1, "text": "The applicant must submit Form 7 and audited financial statement before 31/03/2026."},
            {"page": 1, "text": "The project overview describes cloud infrastructure in modern enterprises."},
            {"page": 2, "text": "Contractor shall furnish bank guarantee within 15 days of contract award."},
        ]
        verified_dates = [
            {"date": "31/03/2026", "normalized": "2026-03-31", "raw": "31/03/2026", "page": 1}
        ]

        actions = extract_actions_deterministic(sentences, verified_dates)
        self.assertEqual(len(actions), 2)

        # First action
        act1 = actions[0]
        self.assertIn("must submit Form 7", act1["action"])
        self.assertEqual(act1["responsible_party"], "Applicant")
        self.assertEqual(act1["deadline"], "2026-03-31")
        self.assertIn("form 7", [d.lower() for d in act1["required_documents"]])
        self.assertEqual(act1["page"], 1)

        # Second action
        act2 = actions[1]
        self.assertIn("shall furnish bank guarantee", act2["action"])
        self.assertEqual(act2["responsible_party"], "Contractor")
        self.assertIn("guarantee", [d.lower() for d in act2["required_documents"]])

    def test_actions_without_dates_do_not_invent_deadlines(self):
        sentences = [
            {"page": 3, "text": "The vendor shall upload the compliance affidavit via the online portal."}
        ]
        actions = extract_actions_deterministic(sentences, verified_dates=[])
        self.assertEqual(len(actions), 1)
        self.assertIsNone(actions[0]["deadline"])
        self.assertIn("Submission portal", actions[0]["location_or_method"])


if __name__ == "__main__":
    unittest.main()
