"""PatraRekhaAI Model Context Protocol (MCP) Server.

Exposes document intelligence capabilities as standardized MCP tools:
- list_recent_documents
- get_deadlines
- get_upcoming_deadlines
- get_overdue_deadlines
- get_document_family
- get_document_changes
- get_document_evidence
"""

from __future__ import annotations

import json
from typing import Any, Callable

from mcp.tools import (
    get_deadlines_tool,
    get_document_changes_tool,
    get_document_evidence_tool,
    get_document_family_tool,
    get_overdue_deadlines_tool,
    get_upcoming_deadlines_tool,
    list_recent_documents_tool,
)


MCP_TOOLS_MANIFEST = [
    {
        "name": "list_recent_documents",
        "description": "List recently ingested documents with file heading, status, and metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "description": "Max documents to return."}
            },
        },
    },
    {
        "name": "get_deadlines",
        "description": "Get all grounded deadlines and important dates with priority and status.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["UPCOMING", "DUE_SOON", "OVERDUE", "SUPERSEDED", "COMPLETED"], "description": "Optional status filter."}
            },
        },
    },
    {
        "name": "get_upcoming_deadlines",
        "description": "Get upcoming deadlines due within the specified lookahead window (days).",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "default": 7, "description": "Lookahead days window."}
            },
        },
    },
    {
        "name": "get_overdue_deadlines",
        "description": "List all active deadlines that have passed without completion.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_document_family",
        "description": "Retrieve the document lineage and version tree for a document (original, amendments, extensions).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Supabase UUID of the document."}
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "get_document_changes",
        "description": "Retrieve 'What changed?' diff between an amendment and its predecessor document.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Supabase UUID of the amendment document."}
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "get_document_evidence",
        "description": "Get verbatim source sentences and page citations for a given date, amount, or phrase.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Supabase UUID of the document."},
                "term": {"type": "string", "description": "Search term, date, or phrase to locate."}
            },
            "required": ["file_id", "term"],
        },
    },
]


class PatraRekhaMCPServer:
    """Dispatches MCP tool calls against backend data."""

    def __init__(self, document_provider: Callable[[], list[dict[str, Any]]]):
        self._document_provider = document_provider

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the manifest of available MCP tools."""
        return MCP_TOOLS_MANIFEST

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call with arguments and return result."""
        documents = self._document_provider()

        if name == "list_recent_documents":
            limit = int(arguments.get("limit", 10))
            return {"results": list_recent_documents_tool(documents, limit=limit)}

        if name == "get_deadlines":
            status = arguments.get("status")
            return {"results": get_deadlines_tool(documents, status_filter=status)}

        if name == "get_upcoming_deadlines":
            days = int(arguments.get("days", 7))
            return {"results": get_upcoming_deadlines_tool(documents, days=days)}

        if name == "get_overdue_deadlines":
            return {"results": get_overdue_deadlines_tool(documents)}

        if name == "get_document_family":
            file_id = arguments.get("file_id")
            if not file_id:
                return {"error": "file_id is required"}
            return {"result": get_document_family_tool(file_id, documents)}

        if name == "get_document_changes":
            file_id = arguments.get("file_id")
            if not file_id:
                return {"error": "file_id is required"}
            return {"result": get_document_changes_tool(file_id, documents)}

        if name == "get_document_evidence":
            file_id = arguments.get("file_id")
            term = arguments.get("term")
            if not file_id or not term:
                return {"error": "file_id and term are required"}
            return {"results": get_document_evidence_tool(file_id, term, documents)}

        return {"error": f"Unknown tool: {name}"}
