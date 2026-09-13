"""Supabase helpers for the email_records table.

Table: email_records
Columns:
  email_id         UUID PRIMARY KEY DEFAULT gen_random_uuid()
  gmail_message_id TEXT UNIQUE NOT NULL
  user_id          UUID NOT NULL REFERENCES auth.users
  owner_email      TEXT NOT NULL
  subject          TEXT
  sender           TEXT
  thread_id        TEXT
  received_at      TIMESTAMPTZ
  body_text        TEXT
  email_intent     TEXT
  created_at       TIMESTAMPTZ DEFAULT NOW()
"""

from __future__ import annotations

from uuid import UUID

from postgrest.exceptions import APIError

from db.supabase_client import supabase


TABLE = "email_records"

SELECT_COLS = (
    "email_id,"
    "gmail_message_id,"
    "user_id,"
    "owner_email,"
    "subject,"
    "sender,"
    "thread_id,"
    "received_at,"
    "body_text,"
    "email_intent,"
    "created_at"
)


# ============================================================================
# Helpers
# ============================================================================

def _normalize_user_id(user_id: str | UUID | None) -> str:
    """Validate and normalise a Supabase Auth user UUID."""
    if not user_id:
        raise ValueError("user_id is required for email_records.")
    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid user_id: {user_id}") from exc


def _normalize_owner_email(owner_email: str | None) -> str:
    return (owner_email or "").strip().lower()


# ============================================================================
# Write
# ============================================================================

def insert_email_record(
    gmail_message_id: str,
    user_id: str | UUID,
    owner_email: str,
    *,
    subject: str | None = None,
    sender: str | None = None,
    thread_id: str | None = None,
    received_at: str | None = None,
    body_text: str | None = None,
    email_intent: str | None = None,
) -> dict | None:
    """Upsert a plain-email record (idempotent on gmail_message_id).

    Returns the upserted row or None on failure.
    """
    row: dict = {
        "gmail_message_id": gmail_message_id,
        "user_id": _normalize_user_id(user_id),
        "owner_email": _normalize_owner_email(owner_email),
    }

    if subject is not None:
        row["subject"] = subject
    if sender is not None:
        row["sender"] = sender
    if thread_id is not None:
        row["thread_id"] = thread_id
    if received_at is not None:
        row["received_at"] = received_at
    if body_text is not None:
        row["body_text"] = body_text
    if email_intent is not None:
        row["email_intent"] = email_intent

    try:
        response = (
            supabase.table(TABLE)
            .upsert(row, on_conflict="gmail_message_id")
            .execute()
        )
        return response.data[0] if response.data else None

    except APIError as exc:
        print(
            f"Warning: could not upsert email_record "
            f"for {gmail_message_id}: {exc}"
        )
        return None

    except Exception as exc:
        print(
            f"Warning: unexpected error storing email_record "
            f"for {gmail_message_id}: {exc}"
        )
        return None


# ============================================================================
# Read
# ============================================================================

def list_email_records(
    user_id: str | UUID | None = None,
    owner_email: str | None = None,
) -> list[dict]:
    """Return email records for a user, newest first."""
    try:
        query = supabase.table(TABLE).select(SELECT_COLS)

        if user_id:
            query = query.eq(
                "user_id",
                _normalize_user_id(user_id),
            )
        elif owner_email:
            query = query.eq(
                "owner_email",
                _normalize_owner_email(owner_email),
            )

        response = query.order("received_at", desc=True).execute()
        return response.data or []

    except APIError:
        return []
    except Exception:
        return []


def get_email_record(
    email_id: str,
    user_id: str | UUID | None = None,
) -> dict | None:
    """Return a single email record owned by the user."""
    try:
        UUID(str(email_id))  # validate

        query = (
            supabase.table(TABLE)
            .select(SELECT_COLS)
            .eq("email_id", str(email_id))
        )

        if user_id:
            query = query.eq(
                "user_id",
                _normalize_user_id(user_id),
            )

        response = query.limit(1).execute()
        return response.data[0] if response.data else None

    except (ValueError, TypeError):
        return None
    except APIError:
        return None


# ============================================================================
# Delete
# ============================================================================

def delete_email_record(
    email_id: str,
    user_id: str | UUID,
) -> dict | None:
    """Delete a single email record.  Scoped to the owning user."""
    try:
        UUID(str(email_id))  # validate

        response = (
            supabase.table(TABLE)
            .delete()
            .eq("email_id", str(email_id))
            .eq("user_id", _normalize_user_id(user_id))
            .execute()
        )
        return response.data[0] if response.data else None

    except (ValueError, TypeError):
        return None
    except APIError as exc:
        print(f"Warning: could not delete email_record {email_id}: {exc}")
        return None
