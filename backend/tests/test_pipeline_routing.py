import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

import pipeline


def _page(number, text):
    return {"page": number, "text": text}


class _FakeLangResult:
    language = "en"
    languages = ["en"]
    script = "Latn"
    scripts = ["Latn"]
    confidence = 0.95
    romanized = False
    code_switched = False


class ExtractivePipelineTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(pipeline, "_llm_client", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Ensure deterministic, LLM-free execution regardless of env.
        self._old_flag = pipeline.EXTRACTIVE_METADATA
        self._old_classify = pipeline.DATE_CLASSIFY_LLM
        pipeline.DATE_CLASSIFY_LLM = False
        pipeline.EXTRACTIVE_METADATA = True

    def tearDown(self):
        pipeline.DATE_CLASSIFY_LLM = self._old_classify
        pipeline.EXTRACTIVE_METADATA = self._old_flag

    def test_small_document_routing(self):
        pages = [
            _page(1, "Government Scholarship Notice 2026\n\nThe deadline for "
                      "submission is 31 March 2026. Applications open on 15/01/2026."),
            _page(2, "Candidates must submit before 30 April 2026 to be "
                      "considered for the merit award."),
        ]
        result = pipeline._extractive_pipeline(pages, _FakeLangResult())

        self.assertEqual(result["_pipeline_method"], "extractive_small")
        self.assertEqual(result["file_heading"], "Government Scholarship Notice 2026")

        timeline_dates = {item["date"] for item in result["timeline_json"]}
        self.assertEqual(
            timeline_dates,
            {"31/03/2026", "15/01/2026", "30/04/2026"},
        )

        dates = result["_dates_json"]
        deadline = [e for e in dates if e["date"] == "31/03/2026"]
        self.assertEqual(len(deadline), 1)
        self.assertEqual(deadline[0]["event_type"], "DEADLINE")
        self.assertIn(deadline[0]["page"], {1, 2})

        self.assertTrue(result["summarization"])
        self.assertIsInstance(result["_key_points"], list)
        self.assertTrue(result["_source_sentences"])
        self.assertIn(result["_source_sentences"][0]["page"], {1, 2})
        self.assertNotIn("_dates_json", result["timeline_json"])

    def test_large_document_routing(self):
        pages = [_page(n + 1, f"{n}: Contemplating the details of the "
                              f"admission policy clause number {n} ending "
                              "15/01/2026.")
                 for n in range(120)]
        result = pipeline._extractive_pipeline(pages, _FakeLangResult())
        self.assertEqual(result["_pipeline_method"], "extractive_large")
        self.assertTrue(result["timeline_json"])

    def test_empty_pages(self):
        result = pipeline._extractive_pipeline([], _FakeLangResult())
        self.assertEqual(result["file_heading"], "Untitled Document")
        self.assertEqual(result["timeline_json"], [])
        self.assertIn("No readable text", result["summarization"])


class LegacyPipelineTests(unittest.TestCase):
    def test_legacy_requires_api_key(self):
        with patch.object(pipeline.os, "getenv", return_value=None):
            with self.assertRaises(ValueError):
                pipeline.extract_metadata_with_llm("Some document text")

    def test_legacy_empty_text(self):
        result = pipeline.extract_metadata_with_llm("")
        self.assertEqual(result["file_heading"], "Untitled Document")
        self.assertEqual(result["timeline_json"], [])
        self.assertNotIn("_pipeline_method", result)


class LanguageNameTests(unittest.TestCase):
    def test_named_languages(self):
        self.assertEqual(pipeline._language_name("hi"), "Hindi")
        self.assertEqual(pipeline._language_name("bn"), "Bengali")
        self.assertEqual(pipeline._language_name("ta"), "Tamil")
        self.assertEqual(pipeline._language_name("ur"), "Urdu")

    def test_unknown_falls_back_to_english(self):
        self.assertEqual(pipeline._language_name(None), "English")
        self.assertEqual(pipeline._language_name("zz"), "English")


if __name__ == "__main__":
    unittest.main()