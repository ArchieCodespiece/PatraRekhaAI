"""Inbound email command execution.

Turns a validated email-body command (see ``services.email_commands``) into a
concrete reply: resolves the user's document family for the incoming thread,
computes the requested answer (what changed / thread summary / reminder ack /
deadline-move confirmation), and dispatches the reply email back to the sender.

Designed to be testable without a live database: all I/O is injected via
``hydrate_documents`` and ``dispatch`` callables.
"""

from __future__ import annotations

from typing import Any, Callable

from services.document_diff import compare_documents
from services.email_commands import (
    execute_email_command,
    parse_email_command,
)
from services.email_sender import send_outbound_notification


# ============================================================================
# Document resolution
# ============================================================================

def default_hydrate_documents(owner_email: str) -> list[dict[str, Any]]:
    """Load a user's files with their metadata merged in.

    Imported lazily so the module stays importable in offline tests.
    """
    from db import document_metadata as db_meta
    from db import files as db_files

    files = db_files.list_documents(owner_email=owner_email) or []

    if not files:
        return []

    meta_rows = (
        db_meta.list_document_metadata_by_file_ids(
            [str(f.get("file_id")) for f in files]
        )
        or []
    )

    meta_by_file = {
        str(row.get("file_id")): row
        for row in meta_rows
    }

    documents = []

    for file_row in files:
        doc = dict(file_row)
        meta = meta_by_file.get(
            str(file_row.get("file_id"))
        ) or {}
        doc.update(meta)
        documents.append(doc)

    return documents


def resolve_family_documents(
    documents: list[dict[str, Any]],
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return documents for the incoming thread, newest first.

    Falls back to recently updated documents when no thread context exists.
    """
    thread_docs = (
        [
            d
            for d in documents
            if thread_id and d.get("thread_id") == thread_id
        ]
        if thread_id
        else []
    )

    pool = thread_docs or documents

    return sorted(
        pool,
        key=lambda d: (
            str(d.get("created_at") or d.get("uploaded_at") or "")
        ),
        reverse=True,
    )


# ============================================================================
# Reply builders
# ============================================================================

def _deadline_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deadline/event items from a document's timeline/dates json."""
    items = (
        document.get("dates_json")
        or document.get("timeline_json")
        or []
    )
    if isinstance(items, str):
        import json
        try:
            items = json.loads(items)
        except Exception:
            items = []
    return list(items) if isinstance(items, list) else []


def _format_date(item: dict[str, Any]) -> str:
    value = item.get("iso_date") or item.get("date") or ""
    text = value.replace("-", "/")
    return text


def build_what_changed_reply(
    documents: list[dict[str, Any]],
) -> tuple[str, str]:
    """Build the reply for a WHAT_CHANGED command.

    Returns (title, body). Needs at least two family documents to diff.
    """
    if len(documents) < 2:
        title = "Re: What changed"
        body = (
            "No prior version of this document is available yet, so "
            "no changes could be computed. The latest version is: "
            f"{documents[0].get('file_heading') or documents[0].get('filename') if documents else '(none)'}"
        )
        return title, body

    newer = documents[0]
    older = documents[-1]

    result = compare_documents(older, newer)

    changes = result.get("changes") or []

    title = f"Re: What changed - {newer.get('file_heading') or newer.get('filename') or 'Document'}"

    if not changes:
        body = (
            f"No notable changes detected between "
            f"'{older.get('file_heading') or older.get('filename')}' "
            f"and the latest version."
        )
        return title, body

    lines = [
        f"{result.get('change_count')} change(s) detected between the "
        "prior version and the latest document:\n"
    ]

    for change in changes:
        topic = change.get("topic", "change")
        importance = change.get("importance", "medium")
        old = change.get("old") or "n/a"
        new = change.get("new") or "n/a"
        source = change.get("source") or ""
        lines.append(
            f"- {topic} ({importance}): {old} -> {new}  [{source}]"
        )

    lines.append(
        "\nLatest document: "
        f"{newer.get('file_heading') or newer.get('filename')}"
    )

    return title, "\n".join(lines)


def build_thread_summary_reply(
    documents: list[dict[str, Any]],
) -> tuple[str, str]:
    """Build the reply for a SUMMARIZE_THREAD command."""
    title = "Re: Thread summary"

    if not documents:
        return title, "No documents were found for this thread."

    lines = [
        "This thread contains the following documents:\n"
    ]

    for index, doc in enumerate(documents, start=1):
        heading = (
            doc.get("file_heading")
            or doc.get("filename")
            or "Untitled document"
        )
        summary = (
            doc.get("summarization")
            or "(no summary generated yet)"
        )
        lines.append(f"{index}. {heading}\n   {summary}\n")

    return title, "\n".join(lines)


def build_reminder_reply(
    documents: list[dict[str, Any]],
    days_before: int,
) -> tuple[str, str]:
    """Build the acknowledgement for a SET_REMINDER command."""
    title = "Re: Reminder scheduled"

    if not documents:
        return title, (
            "Reminder request noted, but no documents were found for "
            "this thread to attach it to."
        )

    newest = documents[0]
    heading = (
        newest.get("file_heading")
        or newest.get("filename")
        or "Your document"
    )

    deadlines = _deadline_items(newest)
    if not deadlines:
        return title, (
            f"Reminder noted: I'll send a reminder "
            f"{days_before} day(s) before the deadline for "
            f"'{heading}'. No explicit deadlines were extracted yet."
        )

    lines = [
        f"Reminder scheduled {days_before} day(s) before each deadline "
        f"for '{heading}':\n"
    ]

    for item in deadlines:
        label = (
            item.get("event")
            or item.get("event_type")
            or "Deadline"
        )
        lines.append(f"- {label}: {_format_date(item)}")

    lines.append("\nYou can also reply 'remind me X days before' any time.")

    return title, "\n".join(lines)


def build_deadline_move_reply(
    documents: list[dict[str, Any]],
    target_date: str,
    confirmed: bool = False,
) -> tuple[str, str]:
    """Build the confirmation / confirmation-request for MOVE_DEADLINE."""
    title = "Re: Move deadline"

    if not documents:
        return title, (
            "No documents were found for this thread, so the deadline "
            "could not be updated."
        )

    newest = documents[0]
    heading = (
        newest.get("file_heading")
        or newest.get("filename")
        or "Your document"
    )

    if not confirmed:
        body = (
            f"Please confirm moving the deadline for '{heading}' "
            f"to {target_date}. Reply 'CONFIRM' to apply this change."
        )
        return title, body

    body = (
        f"The deadline for '{heading}' has been moved to {target_date}."
    )
    return title, body


# ============================================================================
# Command handler
# ============================================================================

def handle_email_command(
    body_text: str,
    owner_email: str,
    user_id: str | None = None,
    thread_id: str | None = None,
    sender: str | None = None,
    subject: str | None = None,
    access_token: str | None = None,
    confirmed: bool = False,
    hydrate_documents: (
        Callable[[], list[dict[str, Any]]] | None
    ) = None,
    dispatch: (
        Callable[[str, str, str], dict[str, Any]] | None
    ) = None,
) -> dict[str, Any]:
    """Parse and execute an email command, dispatching a reply.

    Parameters
    ----------
    body_text : received email body (commands are parsed from here).
    owner_email : PatraRekha user the documents belong to.
    thread_id : Gmail thread the incoming message arrived in.
    sender : reply recipient (incoming From).
    access_token : Gmail access token for real delivery; ``None`` logs only.
    confirmed : whether this message is a CONFIRM reply to a pending move.
    hydrate_documents : returns the user's merged file+metadata docs.
    dispatch : (recipient, subject, body) -> result dict.

    Returns
    -------
    dict with ``handled`` True when a command was recognized and a reply
    dispatched, plus the generated ``reply`` for audit logging.
    """
    command_data = parse_email_command(body_text)

    if not command_data.get("valid"):
        return {
            "handled": False,
            "command": command_data.get("command", "UNKNOWN"),
            "reason": command_data.get("error", "no_valid_command"),
        }

    if sender is None:
        return {
            "handled": False,
            "command": command_data.get("command"),
            "reason": "no_sender",
        }

    load_documents = hydrate_documents or (
        lambda: default_hydrate_documents(owner_email)
    )

    documents = load_documents() or []

    family = resolve_family_documents(documents, thread_id)

    action = execute_email_command(
        command_data,
        context={
            "thread_id": thread_id,
        },
    )

    command = command_data.get("command")

    if command == "WHAT_CHANGED":
        title, reply_body = build_what_changed_reply(family)

    elif command == "SUMMARIZE_THREAD":
        title, reply_body = build_thread_summary_reply(family)

    elif command == "SET_REMINDER":
        title, reply_body = build_reminder_reply(
            family,
            command_data.get("days_before", 1),
        )

    elif command == "MOVE_DEADLINE":
        title, reply_body = build_deadline_move_reply(
            family,
            command_data.get("target_date", ""),
            confirmed=confirmed,
        )

    else:
        return {
            "handled": False,
            "command": command,
            "reason": "unsupported_command",
        }

    dispatcher = dispatch or (
        lambda recipient, subj, body: send_outbound_notification(
            recipient,
            subj,
            body,
            access_token=access_token,
        )
    )

    delivery = dispatcher(sender, title, reply_body)

    return {
        "handled": True,
        "command": command,
        "action": action.get("action"),
        "delivery": delivery,
        "reply_subject": title,
        "reply": reply_body,
    }