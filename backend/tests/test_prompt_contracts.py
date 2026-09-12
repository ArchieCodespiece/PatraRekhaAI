import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

import prompts


def _entity(date="15/01/2026"):
    return {
        "raw": "15/01/2026",
        "date": date,
        "type": "DATE",
        "page": 1,
        "sentence": "Submit the form before 15/01/2026.",
        "context_before": "Submit the form before",
        "context_after": ".",
        "source": "pattern",
        "event_type": None,
        "event_label": None,
    }


class PromptContractTests(unittest.TestCase):
    def test_summary_polish_messages_shape(self):
        messages = prompts.build_summary_polish_messages(
            ["Sentence one.", "Sentence two."],
            "Hindi",
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Hindi", messages[0]["content"])
        self.assertIn("Sentence one.", messages[1]["content"])
        self.assertIn("ONLY the supplied sentences", messages[0]["content"])

    def test_date_classify_messages_shape(self):
        messages = prompts.build_date_classify_messages(
            [_entity()],
            "Tamil",
        )
        self.assertEqual(len(messages), 2)
        self.assertIn("15/01/2026", messages[1]["content"])
        self.assertIn("Tamil", messages[0]["content"])

    def test_normalize_summary_response_drops_blanks(self):
        result = prompts.normalize_summary_response(
            {
                "summary": "  A short summary.  ",
                "key_points": [" One ", "", "  Two "],
                "topics": [" Finance ", None, "  "],
            }
        )
        self.assertEqual(result["summary"], "A short summary.")
        self.assertEqual(result["key_points"], ["One", "Two"])
        self.assertEqual(result["topics"], ["Finance"])

    def test_normalize_summary_response_empty_data(self):
        result = prompts.normalize_summary_response({})
        self.assertEqual(
            result,
            {"summary": "", "key_points": [], "topics": []},
        )

    def test_classification_ignores_invented_indexes(self):
        entities = [_entity()]
        result = prompts.normalize_date_classification(
            {
                "dates": [
                    {"index": 0, "event_type": "DEADLINE", "event_label": "Bid"}, 
                    {"index": 99, "event_type": "SUBMISSION", "event_label": "Fake"},
                ]
            },
            entities,
        )
        classified = result["dates"]
        self.assertEqual(classified[0]["event_type"], "DEADLINE")
        self.assertEqual(list(classified.keys()), [0])

    def test_classification_rejects_unknown_event_type(self):
        entities = [_entity()]
        result = prompts.normalize_date_classification(
            {"dates": [{"index": 0, "event_type": "WILD GUESS", "event_label": "X"}]},
            entities,
        )
        self.assertEqual(result["dates"][0]["event_type"], "OTHER")

    def test_classification_requires_existing_date(self):
        entities = [_entity()]
        result = prompts.normalize_date_classification(
            {"dates": [{"index": 0, "event_type": "DEADLINE", "event_label": "X"}]},
            entities,
        )
        self.assertEqual(result["dates"][0]["event_label"], "X")

    def test_classification_ignores_non_list(self):
        result = prompts.normalize_date_classification(
            {"dates": "not-a-list"},
            [_entity()],
        )
        self.assertEqual(result, {})

    def test_parse_json_object_recovery(self):
        self.assertEqual(
            prompts.parse_json_object('{"summary": "ok"}'),
            {"summary": "ok"},
        )
        self.assertEqual(
            prompts.parse_json_object('prefix {"summary": "ok"} suffix'),
            {"summary": "ok"},
        )
        with self.assertRaises(Exception):
            prompts.parse_json_object("no json here")


if __name__ == "__main__":
    unittest.main()