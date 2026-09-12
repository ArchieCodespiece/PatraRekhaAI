import unittest
from datetime import date, timedelta
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from services.deadline_intelligence import (
    build_deadline_model,
    calculate_deadline_priority,
    calculate_deadline_status,
    detect_deadline_conflicts,
)


class DeadlineIntelligenceTests(unittest.TestCase):
    def test_priority_calculation(self):
        today = date(2026, 3, 15)
        # Critical (< 48 hours)
        self.assertEqual(calculate_deadline_priority(date(2026, 3, 16), today=today), "CRITICAL")
        # High (< 7 days)
        self.assertEqual(calculate_deadline_priority(date(2026, 3, 20), today=today), "HIGH")
        # Medium (< 30 days)
        self.assertEqual(calculate_deadline_priority(date(2026, 4, 1), today=today), "MEDIUM")
        # Low (>= 30 days)
        self.assertEqual(calculate_deadline_priority(date(2026, 5, 1), today=today), "LOW")

    def test_deadline_status(self):
        today = date(2026, 3, 15)
        # Overdue
        self.assertEqual(calculate_deadline_status(date(2026, 3, 10), today=today), "OVERDUE")
        # Due soon (within 3 days)
        self.assertEqual(calculate_deadline_status(date(2026, 3, 17), today=today), "DUE_SOON")
        # Upcoming
        self.assertEqual(calculate_deadline_status(date(2026, 3, 25), today=today), "UPCOMING")
        # Superseded
        self.assertEqual(calculate_deadline_status(date(2026, 3, 25), is_superseded=True, today=today), "SUPERSEDED")

    def test_detect_deadline_conflicts(self):
        doc1 = build_deadline_model("2026-03-30", "Bid Submission Deadline", "doc_1", "DocA.pdf", page=2)
        doc2 = build_deadline_model("2026-03-31", "Tender Submission Last Date", "doc_2", "DocB.pdf", page=1)

        conflicts = detect_deadline_conflicts([doc1, doc2])
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c["conflict_type"], "DEADLINE_CONFLICT")
        self.assertEqual(sorted(c["competing_dates"]), ["2026-03-30", "2026-03-31"])
        self.assertEqual(len(c["sources"]), 2)


if __name__ == "__main__":
    unittest.main()
