"""Wrappers for document metadata table operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from db.supabase_client import supabase


DOCUMENT_METADATA_TABLE = "document_metadata"
DOCUMENT_METADATA_SELECT_COLUMNS = (
    "file_id,file_heading,summarization,timeline_json,created_at,updated_at"
)


def upsert_document_metadata(
    file_id: str,
    file_heading: str,
    summarization: str | None,
    timeline_json: list[dict] | dict | None,
):
    """
    Insert or update LLM-extracted document metadata for a file.
    """

    UUID(str(file_id))

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "file_id": str(file_id),
        "file_heading": file_heading or "Untitled Document",
        "summarization": summarization,
        "timeline_json": json.dumps(timeline_json or []),
        "updated_at": now,
    }

    response = (
        supabase.table(DOCUMENT_METADATA_TABLE)
        .upsert(row, on_conflict="file_id")
        .execute()
    )

    return response.data[0] if response.data else None


def list_document_metadata_by_file_ids(file_ids: list[str]):
    if not file_ids:
        return []

    for file_id in file_ids:
        UUID(str(file_id))

    response = (
        supabase.table(DOCUMENT_METADATA_TABLE)
        .select(DOCUMENT_METADATA_SELECT_COLUMNS)
        .in_("file_id", [str(file_id) for file_id in file_ids])
        .execute()
    )

    return response.data


def list_document_metadata():
    response = (
        supabase.table(DOCUMENT_METADATA_TABLE)
        .select(DOCUMENT_METADATA_SELECT_COLUMNS)
        .execute()
    )

    return response.data


def delete_document_metadata(file_id: str):
    """Delete the metadata row for a file (idempotent)."""
    UUID(str(file_id))
    response = (
        supabase.table(DOCUMENT_METADATA_TABLE)
        .delete()
        .eq("file_id", str(file_id))
        .execute()
    )
    return response.data
