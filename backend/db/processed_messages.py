"""Supabase helpers to track which Gmail messages have been processed.

Table: processed_gmail_messages
Columns:
  message_id  TEXT PRIMARY KEY
  owner_email TEXT NOT NULL
  processed_at TIMESTAMPTZ DEFAULT NOW()
  skipped     BOOLEAN DEFAULT FALSE
  skip_reason TEXT
"""

from __future__ import annotations

from datetime import datetime, timezone

from postgrest.exceptions import APIError

from db.supabase_client import supabase

TABLE = "processed_gmail_messages"
SELECT_COLS = "message_id,owner_email,processed_at,skipped,skip_reason"


def is_message_processed(message_id: str) -> bool:
    """Return True if this Gmail message ID is already in the processed table."""
    try:
        response = (
            supabase.table(TABLE)
            .select("message_id")
            .eq("message_id", message_id)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except APIError:
        # If the table doesn't exist yet, treat as not processed
        return False


def mark_message_processed(
    message_id: str,
    owner_email: str,
    skipped: bool = False,
    skip_reason: str | None = None,
) -> dict | None:
    """Insert a row marking this Gmail message as processed (idempotent)."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "message_id": message_id,
        "owner_email": owner_email,
        "processed_at": now,
        "skipped": skipped,
        "skip_reason": skip_reason,
    }
    try:
        response = (
            supabase.table(TABLE)
            .upsert(row, on_conflict="message_id")
            .execute()
        )
        return response.data[0] if response.data else None
    except APIError as exc:
        # Log but don't crash — the local cache still protects us
        print(f"Warning: could not persist processed status for {message_id}: {exc}")
        return None


def list_processed_messages(owner_email: str | None = None) -> list[dict]:
    """List processed message records, optionally filtered by owner."""
    try:
        query = supabase.table(TABLE).select(SELECT_COLS)
        if owner_email:
            query = query.eq("owner_email", owner_email)
        response = query.order("processed_at", desc=True).execute()
        return response.data or []
    except APIError:
        return []
