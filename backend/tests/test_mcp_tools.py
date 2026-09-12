import unittest
from datetime import date
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from mcp.server import PatraRekhaMCPServer
from mcp.tools import (
    list_recent_documents_tool,
    get_deadlines_tool,
    get_upcoming_deadlines_tool,
    get_overdue_deadlines_tool,
    get_document_family_tool,
    get_document_changes_tool,
    get_document_evidence_tool,
)


class MCPToolsTests(unittest.TestCase):
    def setUp(self):
        self.mock_docs = [
            {
                "file_id": "doc_1",
                "filename": "Tender_2026.pdf",
                "file_heading": "National Highway Tender 2026",
                "created_at": "2026-03-01T10:00:00Z",
                "is_summarized": True,
                "is_vectored": True,
                "timeline_json": [
                    {"date": "20/03/2026", "iso_date": "2026-03-20", "event": "Submission closes", "event_type": "DEADLINE", "page": 4}
                ],
                "summary_source_sentences": [
                    {"page": 4, "text": "All proposals must be submitted before 20/03/2026 via portal."}
                ],
            },
            {
                "file_id": "doc_2",
                "filename": "Corrigendum_1.pdf",
                "file_heading": "Corrigendum 1 for National Highway Tender 2026",
                "created_at": "2026-03-10T10:00:00Z",
                "is_summarized": True,
                "is_vectored": True,
                "timeline_json": [
                    {"date": "31/03/2026", "iso_date": "2026-03-31", "event": "Submission closes extended", "event_type": "DEADLINE", "page": 1}
                ],
                "summary_source_sentences": [
                    {"page": 1, "text": "The last date of submission is extended to 31/03/2026."}
                ],
            }
        ]
        self.server = PatraRekhaMCPServer(lambda: self.mock_docs)

    def test_list_tools(self):
        tools = self.server.list_tools()
        names = {t["name"] for t in tools}
        self.assertIn("list_recent_documents", names)
        self.assertIn("get_deadlines", names)
        self.assertIn("get_upcoming_deadlines", names)
        self.assertIn("get_document_family", names)
        self.assertIn("get_document_changes", names)

    def test_call_list_recent_documents(self):
        res = self.server.call_tool("list_recent_documents", {"limit": 5})
        self.assertEqual(len(res["results"]), 2)
        self.assertEqual(res["results"][0]["file_id"], "doc_2")

    def test_call_get_deadlines(self):
        res = self.server.call_tool("get_deadlines", {})
        self.assertEqual(len(res["results"]), 2)
        dates = [d["deadline"] for d in res["results"]]
        self.assertIn("2026-03-20", dates)
        self.assertIn("2026-03-31", dates)

    def test_call_get_document_family(self):
        res = self.server.call_tool("get_document_family", {"file_id": "doc_2"})
        self.assertIsNotNone(res.get("result"))
        self.assertEqual(res["result"]["member_count"], 2)

    def test_call_get_document_changes(self):
        res = self.server.call_tool("get_document_changes", {"file_id": "doc_2"})
        changes = res["result"]["changes"]
        self.assertTrue(any(c["topic"] == "deadline" for c in changes))

    def test_call_get_document_evidence(self):
        res = self.server.call_tool("get_document_evidence", {"file_id": "doc_1", "term": "proposals"})
        evidence = res["results"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["page"], 4)


if __name__ == "__main__":
    unittest.main()
