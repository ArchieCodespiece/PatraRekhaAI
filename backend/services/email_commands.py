"""Inbound two-way email command parser and validator.

Interprets and executes commands received in email bodies:
- "remind me 2 days before"
- "move the deadline to 10 April 2026"
- "summarize this thread"
- "what changed?"
"""

from __future__ import annotations

import re
from typing import Any

from document_preprocessing.date_utils import normalise_date_iso


_CMD_REMIND = re.compile(
    r"\bremind\s+me\s+(?:(\d+)\s+days?\s+before|same\s+day|1\s+day\s+before|tomorrow)\b",
    re.IGNORECASE,
)
_CMD_MOVE_DEADLINE = re.compile(
    r"\bmove\s+(?:the\s+)?deadline\s+(?:to|for)\s+([0-9a-zA-Z\s,/-]+)\b",
    re.IGNORECASE,
)
_CMD_SUMMARIZE = re.compile(
    r"\bsummarize\s+(?:this\s+)?(?:thread|document|email)\b",
    re.IGNORECASE,
)
_CMD_WHAT_CHANGED = re.compile(
    r"\bwhat\s+changed\??\b",
    re.IGNORECASE,
)


def parse_email_command(body_text: str) -> dict[str, Any]:
    """Parse a natural language command from an email body."""
    text = body_text.strip()

    # 1. "what changed?"
    if _CMD_WHAT_CHANGED.search(text):
        return {
            "command": "WHAT_CHANGED",
            "valid": True,
            "requires_confirmation": False,
        }

    # 2. "summarize this thread"
    if _CMD_SUMMARIZE.search(text):
        return {
            "command": "SUMMARIZE_THREAD",
            "valid": True,
            "requires_confirmation": False,
        }

    # 3. "remind me X days before"
    m_remind = _CMD_REMIND.search(text)
    if m_remind:
        days_str = m_remind.group(1)
        days = int(days_str) if days_str else 1
        if "same day" in m_remind.group(0).lower():
            days = 0
        return {
            "command": "SET_REMINDER",
            "valid": True,
            "days_before": days,
            "requires_confirmation": False,
        }

    # 4. "move the deadline to <date>"
    m_move = _CMD_MOVE_DEADLINE.search(text)
    if m_move:
        raw_target_date = m_move.group(1).strip(" .!?;")
        iso = normalise_date_iso(raw_target_date)
        if not iso:
            return {
                "command": "MOVE_DEADLINE",
                "valid": False,
                "error": f"Could not parse valid date from: '{raw_target_date}'",
            }
        return {
            "command": "MOVE_DEADLINE",
            "valid": True,
            "target_date": iso,
            "requires_confirmation": True,  # Destructive/important edit requires confirmation
            "raw_input": raw_target_date,
        }

    return {
        "command": "UNKNOWN",
        "valid": False,
        "error": "No recognized email command in message body.",
    }


def execute_email_command(
    command_data: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute or prepare the action requested by the validated command."""
    context = context or {}
    cmd = command_data.get("command")

    if not command_data.get("valid"):
        return {
            "status": "ERROR",
            "error": command_data.get("error", "Invalid command"),
        }

    if cmd == "WHAT_CHANGED":
        return {
            "status": "SUCCESS",
            "action": "FETCH_DIFF",
            "document_id": context.get("document_id"),
            "thread_id": context.get("thread_id"),
        }

    if cmd == "SUMMARIZE_THREAD":
        return {
            "status": "SUCCESS",
            "action": "SUMMARIZE_THREAD",
            "thread_id": context.get("thread_id"),
        }

    if cmd == "SET_REMINDER":
        return {
            "status": "SUCCESS",
            "action": "SCHEDULE_REMINDER",
            "days_before": command_data.get("days_before"),
            "document_id": context.get("document_id"),
            "deadline": context.get("deadline"),
        }

    if cmd == "MOVE_DEADLINE":
        if command_data.get("requires_confirmation") and not context.get("confirmed"):
            return {
                "status": "AWAITING_CONFIRMATION",
                "action": "MOVE_DEADLINE",
                "target_date": command_data.get("target_date"),
                "message": (
                    f"Please confirm: Move deadline from {context.get('deadline')} "
                    f"to {command_data.get('target_date')}? Reply 'CONFIRM' to proceed."
                ),
            }

        return {
            "status": "SUCCESS",
            "action": "DEADLINE_UPDATED",
            "new_deadline": command_data.get("target_date"),
            "previous_deadline": context.get("deadline"),
        }

    return {
        "status": "UNKNOWN",
        "command": cmd,
    }
