import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
for _P in (str(_ROOT), str(_ROOT / "AI pipeline" / "summarization-deadline"), str(_ROOT / "document_preprocessing")):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from date_utils import (
    normalise_date_iso,
    normalise_date_dd_mm_yyyy,
    iso_to_dd_mm_yyyy,
    dd_mm_yyyy_to_iso,
)
from date_extractor import extract_dates


class DateNormalizationTests(unittest.TestCase):
    def test_canonical_iso_from_various_formats(self):
        # Numeric DD/MM/YYYY
        self.assertEqual(normalise_date_iso("15/01/2026"), "2026-01-15")
        # Numeric DD-MM-YYYY
        self.assertEqual(normalise_date_iso("15-01-2026"), "2026-01-15")
        # Numeric DD.MM.YYYY
        self.assertEqual(normalise_date_iso("15.01.2026"), "2026-01-15")
        # ISO YYYY-MM-DD
        self.assertEqual(normalise_date_iso("2026-01-15"), "2026-01-15")
        # Written day first
        self.assertEqual(normalise_date_iso("15 January 2026"), "2026-01-15")
        self.assertEqual(normalise_date_iso("15th Jan 2026"), "2026-01-15")
        # Written month first
        self.assertEqual(normalise_date_iso("January 15, 2026"), "2026-01-15")

    def test_bi_directional_conversions(self):
        self.assertEqual(iso_to_dd_mm_yyyy("2026-03-31"), "31/03/2026")
        self.assertEqual(dd_mm_yyyy_to_iso("31/03/2026"), "2026-03-31")
        self.assertEqual(normalise_date_dd_mm_yyyy("2026-03-31"), "31/03/2026")

    def test_indic_months_iso_normalisation(self):
        # Hindi Devanagari
        self.assertEqual(normalise_date_iso("15 जनवरी 2026"), "2026-01-15")
        # Bengali
        self.assertEqual(normalise_date_iso("15 মার্চ 2026"), "2026-03-15")
        # Marathi
        self.assertEqual(normalise_date_iso("15 ऑगस्ट 2026"), "2026-08-15")

    def test_malformed_and_invalid_dates_rejected(self):
        self.assertIsNone(normalise_date_iso("32/01/2026"))
        self.assertIsNone(normalise_date_iso("15/13/2026"))
        self.assertIsNone(normalise_date_iso("29/02/2025"))
        self.assertEqual(normalise_date_iso("29/02/2024"), "2024-02-29")
        self.assertIsNone(normalise_date_iso("not a date"))
        self.assertIsNone(normalise_date_iso(""))

    def test_extracted_entities_have_rich_context(self):
        pages = [{"page": 1, "text": "The agreement shall commence on 15 January 2026 and remain valid for a period of 24 months."}]
        entities = extract_dates(pages)
        self.assertEqual(len(entities), 1)
        ent = entities[0]
        self.assertEqual(ent["raw"], "15 January 2026")
        self.assertEqual(ent["normalized"], "2026-01-15")
        self.assertEqual(ent["display_date"], "15/01/2026")
        self.assertEqual(ent["date"], "15/01/2026")
        self.assertEqual(ent["page"], 1)
        self.assertIn("commence", ent["context_before"])
        self.assertIn("valid", ent["context_after"])
        self.assertIn("15 January 2026", ent["source_sentence"])
        self.assertEqual(ent["extraction_method"], "pattern")
        self.assertEqual(ent["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
