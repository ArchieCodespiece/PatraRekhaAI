import json
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from date_extractor import extract_dates


class _FakeChoice:
    def __init__(self, content):
        self.index = 0
        self.finish_reason = "stop"
        self.message = _FakeMessage(content)


class _FakeMessage:
    def __init__(self, content):
        self.content = content
        self.role = "assistant"
        self.reasoning_content = None


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        self._owner._calls += 1
        payload = [
            {"index": idx, "normalized": date}
            for idx, date in self._owner._payloads.items()
        ]
        return _FakeCompletion(json.dumps(payload))


class _FakeChat:
    def __init__(self, owner):
        self.completions = _FakeCompletions(owner)


class _FakeLLM:
    """Minimal Groq-style client stand-in for the LLM fallback path."""

    def __init__(self, payloads_by_index):
        self._payloads = payloads_by_index
        self._calls = 0
        self.chat = _FakeChat(self)


def _page(number, text):
    return {"page": number, "text": text}


def _dates(entities):
    return [e["date"] for e in entities]


class DateExtractorNumericTests(unittest.TestCase):
    def test_numeric_dd_mm_yyyy(self):
        entities = extract_dates(
            [_page(1, "The agreement starts 15/01/2026 and ends on 31/12/2026.")]
        )
        self.assertEqual(
            sorted(_dates(entities)),
            ["15/01/2026", "31/12/2026"],
        )

    def test_day_first_with_suffix_and_month_name(self):
        entities = extract_dates(
            [_page(1, "Submission is due by 31st March 2026, no later.")]
        )
        self.assertIn("31/03/2026", _dates(entities))
        self.assertTrue(all(e["source"] == "pattern" for e in entities))

    def test_month_first_english(self):
        entities = extract_dates(
            [_page(1, "Hearing is fixed for March 15, 2026 in court.")]
        )
        self.assertIn("15/03/2026", _dates(entities))

    def test_iso_and_dashed_variants(self):
        entities = extract_dates(
            [_page(1, "Filed 2026-01-15. Signed 15-01-2026.")]
        )
        matching = [e for e in entities if e["date"] == "15/01/2026"]
        self.assertEqual(len(matching), 2)

    def test_false_positives_are_rejected(self):
        entities = extract_dates(
            [_page(1, "Version 3.0 was deployed on 12/2024 for budget 2024-25.")]
        )
        self.assertEqual(entities, [])

    def test_page_and_sentence_attribution(self):
        entities = extract_dates(
            [
                _page(1, "Some intro text that says nothing about dates yet."),
                _page(2, "The registry opens on 05/06/2026 for all applicants."),
            ]
        )
        entity = [e for e in entities if e["date"] == "05/06/2026"]
        self.assertEqual(len(entity), 1)
        self.assertEqual(entity[0]["page"], 2)
        self.assertIn("05/06/2026", entity[0]["sentence"])
        self.assertTrue(entity[0]["context_before"])
        self.assertTrue(entity[0]["context_after"])

    def test_deduplication_same_sentence_same_date(self):
        entities = extract_dates(
            [_page(1, "Pay on 15/01/2026 and again on 15/01/2026.")]
        )
        matching = [e for e in entities if e["date"] == "15/01/2026"]
        self.assertEqual(len(matching), 1)


class DateExtractorIndicTests(unittest.TestCase):
    def test_hindi_month(self):
        entities = extract_dates(
            [_page(1, "अंतिम तिथि 15 जनवरी 2026 है।")]
        )
        self.assertIn("15/01/2026", _dates(entities))

    def test_bengali_month(self):
        entities = extract_dates(
            [_page(1, "জমা দেওয়ার শেষ তারিখ 15 মার্চ 2026.")]
        )
        self.assertIn("15/03/2026", _dates(entities))

    def test_tamil_month(self):
        entities = extract_dates(
            [_page(1, "இறுதி தேதி 15 ஜனவரி 2026.")]
        )
        self.assertIn("15/01/2026", _dates(entities))

    def test_urdu_written_month(self):
        entities = extract_dates(
            [_page(1, "آخری تاریخ 15 جنوری 2026 ہے۔")]
        )
        self.assertIn("15/01/2026", _dates(entities))

    def test_romanized_month(self):
        entities = extract_dates(
            [_page(1, "The last date is 15 January 2026.")]
        )
        self.assertIn("15/01/2026", _dates(entities))


class DateExtractorLLMFallbackTests(unittest.TestCase):
    def test_llm_fills_written_month_candidate(self):
        fake = _FakeLLM({0: "15/01/2026"})
        entities = extract_dates(
            [_page(1, "Deadline is 15 Januari 2026 (extended).")],
            llm_client=fake,
        )
        entity = [e for e in entities if e["date"] == "15/01/2026"]
        self.assertEqual(len(entity), 1)
        self.assertEqual(entity[0]["source"], "llm")
        self.assertGreaterEqual(fake._calls, 1)

    def test_llm_accepts_only_numeric_month_when_snippet_is_numeric(self):
        fake = _FakeLLM({0: "15/02/2026"})
        entities = extract_dates(
            [_page(1, "Court order 15 45 2026 executed.")],
            llm_client=fake,
        )
        self.assertEqual(
            [e for e in entities if e["source"] == "llm"],
            [],
        )

    def test_llm_invented_day_is_rejected(self):
        fake = _FakeLLM({0: "16/01/2026"})
        entities = extract_dates(
            [_page(1, "Deadline is 15 Januari 2026 (extended).")],
            llm_client=fake,
        )
        llm_entities = [e for e in entities if e["source"] == "llm"]
        self.assertEqual(llm_entities, [])

    def test_no_llm_client_skips_fallback(self):
        entities = extract_dates(
            [_page(1, "Deadline is 15 Januari 2026 (extended).")],
            llm_client=None,
        )
        self.assertEqual(entities, [])


if __name__ == "__main__":
    unittest.main()