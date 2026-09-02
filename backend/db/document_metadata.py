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
DOCUMENT_METADATA_SELECT_COLUMNS_WITH_LANG = (
    "file_id,file_heading,summarization,timeline_json,created_at,updated_at,"
    "language,languages,script,scripts,language_confidence,is_romanized,is_code_switched"
)


def upsert_document_metadata(
    file_id: str,
    file_heading: str,
    summarization: str | None,
    timeline_json: list[dict] | dict | None,
    language: str | None = None,
    languages: list[str] | None = None,
    script: str | None = None,
    scripts: list[str] | None = None,
    language_confidence: float | None = None,
    is_romanized: bool | None = None,
    is_code_switched: bool | None = None,
):
    """
    Insert or update LLM-extracted document metadata for a file.

    Parameters
    ----------
    file_id : str
        Supabase file UUID.
    file_heading : str
        Extracted document heading/title.
    summarization : str
        Document summary.
    timeline_json : list[dict] | dict | None
        Extracted deadlines and events.
    language : str | None
        Primary detected language code (ISO 639-1).
    languages : list[str] | None
        All detected languages.
    script : str | None
        Primary detected script name.
    scripts : list[str] | None
        All detected scripts.
    language_confidence : float | None
        Confidence score for language detection.
    is_romanized : bool | None
        Whether the document contains Romanized Indic content.
    is_code_switched : bool | None
        Whether the document contains multiple languages.
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

    # Add language metadata if provided
    if language is not None:
        row["language"] = language
    if languages is not None:
        row["languages"] = json.dumps(languages)
    if script is not None:
        row["script"] = script
    if scripts is not None:
        row["scripts"] = json.dumps(scripts)
    if language_confidence is not None:
        row["language_confidence"] = language_confidence
    if is_romanized is not None:
        row["is_romanized"] = bool(is_romanized)
    if is_code_switched is not None:
        row["is_code_switched"] = bool(is_code_switched)

    try:
        response = (
            supabase.table(DOCUMENT_METADATA_TABLE)
            .upsert(row, on_conflict="file_id")
            .execute()
        )
    except Exception:
        # Language columns may not exist yet — upsert without them
        safe_row = {
            k: v
            for k, v in row.items()
            if k
            in {
                "file_id",
                "file_heading",
                "summarization",
                "timeline_json",
                "updated_at",
            }
        }
        response = (
            supabase.table(DOCUMENT_METADATA_TABLE)
            .upsert(safe_row, on_conflict="file_id")
            .execute()
        )

    return response.data[0] if response.data else None


def list_document_metadata_by_file_ids(file_ids: list[str]):
    if not file_ids:
        return []

    for file_id in file_ids:
        UUID(str(file_id))

    try:
        response = (
            supabase.table(DOCUMENT_METADATA_TABLE)
            .select(DOCUMENT_METADATA_SELECT_COLUMNS_WITH_LANG)
            .in_("file_id", [str(file_id) for file_id in file_ids])
            .execute()
        )
    except Exception:
        response = (
            supabase.table(DOCUMENT_METADATA_TABLE)
            .select(DOCUMENT_METADATA_SELECT_COLUMNS)
            .in_("file_id", [str(file_id) for file_id in file_ids])
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
