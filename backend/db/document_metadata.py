"""Wrappers for document metadata table operations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from db.supabase_client import supabase


DOCUMENT_METADATA_TABLE = "document_metadata"


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
        "timeline_json": timeline_json or [],
        "updated_at": now,
    }

    response = (
        supabase.table(DOCUMENT_METADATA_TABLE)
        .upsert(row, on_conflict="file_id")
        .execute()
    )

    return response.data[0] if response.data else None
