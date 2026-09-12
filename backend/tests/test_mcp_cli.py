import unittest
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
for _P in (str(_ROOT), str(_BACKEND)):
    if _P not in sys.path:
        sys.path.insert(0, _P)

from mcp.cli import _handle
from mcp.server import MCP_TOOLS_MANIFEST, PatraRekhaMCPServer


def _make_server():
    doc = {
        "file_id": "doc_1",
        "file_heading": "Tender Notice",
        "filename": "notice.pdf",
        "dates_json": [
            {"iso_date": "2026-04-15", "event": "Submission", "event_type": "DEADLINE"}
        ],
        "timeline_json": [],
        "summary_source_sentences": ["Deadline is 15 April 2026."],
    }
    return PatraRekhaMCPServer(document_provider=lambda: [doc])


class McpCliTests(unittest.TestCase):
    def test_initialize_response(self):
        resp = _handle(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test"},
                },
            },
            _make_server(),
        )
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(resp["result"]["serverInfo"]["name"], "patrarekha-mcp")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list_is_claude_compliant(self):
        resp = _handle(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            _make_server(),
        )
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), len(MCP_TOOLS_MANIFEST))

        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_tools_call_returns_text_content(self):
        resp = _handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_recent_documents",
                    "arguments": {"limit": 5},
                },
            },
            _make_server(),
        )
        content = resp["result"]["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["type"], "text")
        self.assertIn("Tender Notice", content[0]["text"])

    def test_notifications_require_no_response(self):
        resp = _handle(
            {
                "jsonrpc": "2.0",
                "method": "notifications/shutdown",
                "params": {},
            },
            _make_server(),
        )
        self.assertIsNone(resp)

    def test_unknown_method_error(self):
        resp = _handle(
            {"jsonrpc": "2.0", "id": 9, "method": "bogus/method", "params": {}},
            _make_server(),
        )
        self.assertEqual(resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()