"""Email body cleaning, provenance tracking, and intent classification.

Handles:
- Stripping signatures, disclaimers, repeated quoted replies, and HTML noise
- Provenance record generation for attachments and email bodies
- Intent classification: NOTICE, AMENDMENT, DEADLINE_CHANGE, REMINDER,
  RESULT, APPEAL, INFORMATIONAL, OTHER
"""

from __future__ import annotations

import html
import re
from typing import Any


# Patterns identifying repetitive reply headers
_QUOTE_HEADERS = [
    re.compile(r"^\s*On\s+.+?wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*From:\s*.+?Sent:\s*.+?To:\s*.+?Subject:\s*", re.MULTILINE | re.DOTALL | re.IGNORECASE),
    re.compile(r"^\s*-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*_{10,}\s*$", re.MULTILINE),
]

# Patterns identifying sign-offs / signatures
_SIGNATURE_PATTERNS = [
    re.compile(r"^\s*(?:warm\s+)?regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*sincerely,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*thanks\s*(?:&|and)?\s*regards,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*best\s*wishes,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*cheers,?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\s*sent from my (?:iphone|android|ipad|galaxy|phone)\b", re.MULTILINE | re.IGNORECASE),
]

# Boilerplate / disclaimer keywords
_DISCLAIMER_PATTERNS = [
    re.compile(r"This email (?:and any attachments )?is confidential.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"If you (?:have received|are not the intended).*delete.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"Click here to unsubscribe.*", re.IGNORECASE | re.DOTALL),
    re.compile(r"To unsubscribe from this list.*", re.IGNORECASE | re.DOTALL),
]


def strip_html_tags(html_content: str) -> str:
    """Convert HTML email body into clean plain text."""
    if not html_content:
        return ""
    # Strip script and style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Convert <br> and <p> into newlines
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</p>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</div>", "\n", cleaned, flags=re.IGNORECASE)
    # Strip remaining tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Unescape entities
    unescaped = html.unescape(cleaned)
    # Normalize whitespaces
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in unescaped.splitlines()]
    return "\n".join(lines).strip()


def clean_email_body(body_text: str) -> str:
    """Strip quoted replies, email signatures, and legal disclaimer boilerplate."""
    if not body_text:
        return ""

    text = body_text.strip()

    # 1. Truncate at quoted thread reply boundaries
    for p in _QUOTE_HEADERS:
        match = p.search(text)
        if match:
            text = text[:match.start()].strip()

    # 2. Truncate at signature start
    for p in _SIGNATURE_PATTERNS:
        match = p.search(text)
        if match:
            # Keep up to the sign-off, omit trailing contact card
            text = text[:match.start()].strip()

    # 3. Strip legal disclaimers
    for p in _DISCLAIMER_PATTERNS:
        match = p.search(text)
        if match:
            text = text[:match.start()].strip()

    # Normalize double linebreaks
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def classify_email_intent(subject: str, body: str) -> str:
    """Classify email intent into standard administrative categories:
    
    NOTICE, AMENDMENT, DEADLINE_CHANGE, REMINDER, RESULT, APPEAL, INFORMATIONAL, OTHER
    """
    combined = f"{subject}\n{body}".lower()

    if any(k in combined for k in ("corrigendum", "amendment", "addendum", "rectification", "revised")):
        return "AMENDMENT"
    if any(k in combined for k in ("extended", "extension", "postponed", "deadline changed", "new date", "last date extended")):
        return "DEADLINE_CHANGE"
    if any(k in combined for k in ("reminder", "urgent reminder", "due tomorrow", "impending")):
        return "REMINDER"
    if any(k in combined for k in ("result", "selected", "shortlist", "award of contract", "merit list", "disqualified")):
        return "RESULT"
    if any(k in combined for k in ("appeal", "grievance", "objection", "representation", "clarification")):
        return "APPEAL"
    if any(k in combined for k in ("notice", "circular", "tender", "rfp", "invitation for bid", "eoi", "notification")):
        return "NOTICE"
    if len(combined.strip()) > 50:
        return "INFORMATIONAL"

    return "OTHER"


def build_email_provenance(
    source_type: str,
    email_id: str,
    thread_id: str | None = None,
    sender: str | None = None,
    subject: str | None = None,
    timestamp: str | None = None,
    filename: str | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    """Build a standardized provenance object for attachment or email body sources."""
    prov: dict[str, Any] = {
        "source_type": source_type,
        "email_id": email_id,
        "thread_id": thread_id,
    }
    if source_type == "attachment":
        prov["filename"] = filename
        prov["page"] = page or 1
        if sender:
            prov["sender"] = sender
        if subject:
            prov["subject"] = subject
    else:
        prov["sender"] = sender
        prov["subject"] = subject
        prov["timestamp"] = timestamp
        prov["page"] = page or 1

    return prov
