"""Supabase-backed Gmail connection storage."""

from __future__ import annotations

from datetime import datetime, timezone

from postgrest.exceptions import APIError

from db.supabase_client import supabase

GMAIL_CONNECTIONS_TABLE = "gmail_connections"
GMAIL_CONNECTIONS_SELECT_COLUMNS = (
    "owner_email,google_email,provider_access_token,provider_refresh_token,scopes,connected_at,updated_at"
)


def upsert_gmail_connection(owner_email, google_email, access_token, refresh_token, scopes):
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "owner_email": owner_email,
        "google_email": google_email,
        "provider_access_token": access_token,
        "provider_refresh_token": refresh_token,
        "scopes": scopes,
        "connected_at": now,
        "updated_at": now,
    }
    try:
        response = (
            supabase.table(GMAIL_CONNECTIONS_TABLE)
            .upsert(row, on_conflict="owner_email")
            .execute()
        )
    except APIError as exc:
        raise RuntimeError("gmail_connections table is missing or unavailable in Supabase.") from exc
    return response.data[0] if response.data else None


def get_gmail_connection(owner_email):
    try:
        response = (
            supabase.table(GMAIL_CONNECTIONS_TABLE)
            .select(GMAIL_CONNECTIONS_SELECT_COLUMNS)
            .eq("owner_email", owner_email)
            .limit(1)
            .execute()
        )
    except APIError:
        return []
    return response.data[0] if response.data else None


def clear_gmail_connections(owner_email=None):
    try:
        query = supabase.table(GMAIL_CONNECTIONS_TABLE).delete()
        if owner_email:
            query = query.eq("owner_email", owner_email)
        else:
            query = query.neq("owner_email", "__none__")
        response = query.execute()
    except APIError:
        return []
    return response.data or []


def list_gmail_connections():
    try:
        response = (
            supabase.table(GMAIL_CONNECTIONS_TABLE)
            .select(GMAIL_CONNECTIONS_SELECT_COLUMNS)
            .execute()
        )
    except APIError:
        return []
    return response.data or []


def update_gmail_connection_tokens(owner_email, access_token, refresh_token=None):
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "provider_access_token": access_token,
        "updated_at": now,
    }
    if refresh_token:
        row["provider_refresh_token"] = refresh_token

    try:
        response = (
            supabase.table(GMAIL_CONNECTIONS_TABLE)
            .update(row)
            .eq("owner_email", owner_email)
            .execute()
        )
    except APIError as exc:
        raise RuntimeError("gmail_connections table is missing or unavailable in Supabase.") from exc
    return response.data[0] if response.data else None


def delete_gmail_connection(owner_email):
    try:
        response = (
            supabase.table(GMAIL_CONNECTIONS_TABLE)
            .delete()
            .eq("owner_email", owner_email)
            .execute()
        )
    except APIError:
        return []
    return response.data
