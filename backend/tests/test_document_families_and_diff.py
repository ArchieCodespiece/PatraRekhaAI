import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.document_families import (
    are_documents_in_same_family,
    build_document_family,
    compute_title_similarity,
    extract_document_identifiers,
)
from services.document_diff import (
    compare_documents,
    detect_deadline_supersessions,
)


class DocumentFamiliesAndDiffTests(unittest.TestCase):
    def test_extract_document_identifiers(self):
        text = "Notice Inviting Tender No: NIT/2026/04/ROAD-WORK for state highways."
        ids = extract_document_identifiers(text)
        self.assertIn("NIT/2026/04/ROAD-WORK", ids)

    def test_are_documents_in_same_family_by_identifier(self):
        doc_a = {
            "file_id": "1",
            "file_heading": "Tender Notice NIT/2026/04/ROAD-WORK",
            "filename": "Tender.pdf",
        }
        doc_b = {
            "file_id": "2",
            "file_heading": "Corrigendum 1 for NIT/2026/04/ROAD-WORK",
            "filename": "Corrigendum.pdf",
        }
        matched, reason = are_documents_in_same_family(doc_a, doc_b)
        self.assertTrue(matched)
        self.assertIn("identifier_match", reason)

    def test_build_document_family_lineage(self):
        docs = [
            {"file_id": "1", "file_heading": "Tender for Road Construction Ref-99", "created_at": "2026-03-01T00:00:00Z"},
            {"file_id": "2", "file_heading": "Corrigendum 1 Tender Road Construction Ref-99", "created_at": "2026-03-05T00:00:00Z"},
        ]
        families = build_document_family(docs)
        self.assertEqual(len(families), 1)
        fam = families[0]
        self.assertEqual(fam["member_count"], 2)
        self.assertEqual(fam["lineage"][0]["role"], "ORIGINAL")
        self.assertEqual(fam["lineage"][1]["role"], "CORRIGENDUM")
        self.assertEqual(fam["lineage"][1]["supersedes"], "1")

    def test_deadline_supersession_and_diff(self):
        older_timeline = [
            {"date": "20/03/2026", "iso_date": "2026-03-20", "event": "Submission deadline", "event_type": "DEADLINE", "page": 2}
        ]
        newer_timeline = [
            {"date": "31/03/2026", "iso_date": "2026-03-31", "event": "Submission deadline extended", "event_type": "DEADLINE", "page": 1}
        ]

        doc_older = {"file_id": "doc_1", "file_heading": "Original Tender", "timeline_json": older_timeline}
        doc_newer = {"file_id": "doc_2", "file_heading": "Tender Extension", "timeline_json": newer_timeline}

        diff = compare_documents(doc_older, doc_newer)
        self.assertEqual(diff["change_count"], 2) # deadline changed + heading changed
        
        # Check deadline change
        deadline_change = [c for c in diff["changes"] if c["topic"] == "deadline"][0]
        self.assertEqual(deadline_change["old"], "2026-03-20")
        self.assertEqual(deadline_change["new"], "2026-03-31")
        self.assertEqual(deadline_change["importance"], "high")

        # Check supersession marking
        superseded = diff["superseded_older_timeline"][0]
        self.assertEqual(superseded["status"], "SUPERSEDED")
        self.assertEqual(superseded["superseded_by"], "doc_2")


if __name__ == "__main__":
    unittest.main()
