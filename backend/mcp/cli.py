"""MCP stdio transport for Claude Desktop / CLI integrations.

Reads newline-delimited JSON-RPC on stdin, writes responses on stdout.
Suitable for ``claude_desktop_config.json`` MCP server entries::

    {
      "mcpServers": {
        "patrarekha": {
          "command": "python",
          "args": ["backend/mcp/cli.py"],
          "env": {
            "PATRA_REKHA_OWNER_EMAIL": "you@example.com"
          }
        }
      }
    }

Environment
------------
``PATRA_REKHA_OWNER_EMAIL``
    Required. Email of the PatraRekha user whose documents are exposed.
"""

from __future__ import annotations

import json
import os
import sys

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)
for _path in (_BACKEND_DIR, os.path.dirname(_BACKEND_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from typing import Any

from mcp.server import MCP_TOOLS_MANIFEST, PatraRekhaMCPServer


# ============================================================================
# Document provider
# ============================================================================

def _get_owner_email() -> str:
    email = (os.getenv("PATRA_REKHA_OWNER_EMAIL") or "").strip().lower()
    if not email:
        print(
            "[mcp-cli] Error: PATRA_REKHA_OWNER_EMAIL "
            "environment variable is not set.",
            file=sys.stderr,
        )
        sys.exit(1)
    return email


def _build_provider(owner_email: str):
    def provider() -> list[dict[str, Any]]:
        from services.email_command_handler import (
            default_hydrate_documents,
        )
        return default_hydrate_documents(owner_email)
    return provider


# ============================================================================
# JSON-RPC dispatch
# ============================================================================

def _handle(
    request: dict[str, Any],
    server: PatraRekhaMCPServer,
) -> dict[str, Any] | None:
    """Return a JSON-RPC response dict, or ``None`` for notifications."""
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    # Notifications (no id) require no response
    if req_id is None and method in (
        "initialized",
        "notifications/shutdown",
    ):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "patrarekha-mcp",
                    "version": "0.1.0",
                },
            },
        }

    if method == "tools/list":
        tools = [
            {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "inputSchema": (
                    tool.get("parameters")
                    or {
                        "type": "object",
                        "properties": {},
                    }
                ),
            }
            for tool in MCP_TOOLS_MANIFEST
        ]

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools},
        }

    if method == "tools/call":
        tool_name = params.get("name") or ""
        arguments = params.get("arguments") or {}

        result = server.call_tool(tool_name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            result, default=str
                        ),
                    }
                ]
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


# ============================================================================
# Main loop
# ============================================================================

def main() -> None:
    owner_email = _get_owner_email()

    server = PatraRekhaMCPServer(
        document_provider=_build_provider(owner_email),
    )

    print(
        f"[mcp-cli] Ready — owner={owner_email}",
        file=sys.stderr,
    )

    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {exc}",
                },
            }
            _write(err)
            continue

        response = _handle(request, server)

        if response is not None:
            _write(response)


def _write(response: dict[str, Any]) -> None:
    """Write a JSON-RPC response as one newline-delimited line."""
    sys.stdout.write(json.dumps(response, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()