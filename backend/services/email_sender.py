"""Outbound email notifications for deadline reminders and document changes.

Features:
- Formatted notification templates (deadline changes, reminders)
- Safe logging of outbound messages to prevent spam
- Dispatch via Gmail API if active connection present, or local log dispatch
"""

from __future__ import annotations

import base64
from email.message import EmailMessage
import json
import logging
from typing import Any


logger = logging.getLogger("patrarekha.outbound")


def format_deadline_change_notification(
    document_title: str,
    original_date: str,
    new_date: str,
    source_citation: str = "Amendment Notice",
) -> dict[str, str]:
    """Format subject and body for a deadline change notification."""
    subject = f"[PatraRekha] Deadline Changed: {document_title[:40]}"
    body = (
        f"Notice: The deadline for '{document_title}' has changed.\n\n"
        f"Original Deadline: {original_date}\n"
        f"New Deadline:      {new_date}\n\n"
        f"Source: {source_citation}\n\n"
        f"---\nSent automatically by PatraRekhaAI Document Intelligence"
    )
    return {"subject": subject, "body": body}


def format_reminder_notification(
    document_title: str,
    event_label: str,
    deadline_date: str,
    reminder_type: str,
) -> dict[str, str]:
    """Format subject and body for a scheduled reminder."""
    label = reminder_type.replace("_", " ").title()
    subject = f"[Reminder: {label}] {event_label} - {deadline_date}"
    body = (
        f"Upcoming Deadline Alert:\n\n"
        f"Event:    {event_label}\n"
        f"Document: {document_title}\n"
        f"Deadline: {deadline_date}\n\n"
        f"---\nSent by PatraRekhaAI Reminders"
    )
    return {"subject": subject, "body": body}


def send_outbound_notification(
    recipient_email: str,
    subject: str,
    body: str,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Send an outbound email via Gmail API or log for local delivery."""
    logger.info("Outbound notification to %s: %s", recipient_email, subject)

    if not access_token:
        # Dry-run / audit log delivery
        return {
            "delivered": True,
            "channel": "log",
            "recipient": recipient_email,
            "subject": subject,
        }

    # If active access token is present, dispatch via Gmail API
    import urllib.request
    import urllib.error

    msg = EmailMessage()
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.set_content(body)

    raw_bytes = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    payload = json.dumps({"raw": raw_bytes}).encode("utf-8")

    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return {
                "delivered": True,
                "channel": "gmail_api",
                "message_id": data.get("id"),
                "recipient": recipient_email,
            }
    except Exception as exc:
        logger.error("Failed to dispatch email via Gmail API: %s", exc)
        return {
            "delivered": False,
            "error": str(exc),
            "recipient": recipient_email,
        }
