"""Wrappers for standard file storage queries."""

import os
from uuid import UUID

from db.supabase_client import supabase


FILE_STORAGE_BUCKET = os.getenv("SUPABASE_FILE_STORAGE_BUCKET", "file_storage")
FILES_TABLE = os.getenv("SUPABASE_FILES_TABLE", "files")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
FILE_SELECT_COLUMNS = (
    "file_id,filename,file_type,file_size,file_url,created_at,uploaded_at,"
    "is_summarized,is_vectored"
)


def upload_file_to_bucket(filename, content, content_type):
    return supabase.storage.from_(FILE_STORAGE_BUCKET).upload(
        filename,
        content,
        {
            "content-type": content_type or "application/octet-stream",
            "upsert": "true",
        },
    )


def get_file_url(filename):
    # Use the official SDK method instead of manual string concatenation
    return supabase.storage.from_(FILE_STORAGE_BUCKET).get_public_url(filename)


def insert_file_record(filename, content_type, file_size, file_url):
    response = (
        supabase.table(FILES_TABLE)
        .insert(
            {
                "filename": filename,
                "file_type": content_type or "application/octet-stream",
                "file_size": file_size,
                "file_url": file_url,
                "is_summarized": False,
                "is_vectored": False,
            }
        )
        .execute()
    )
    return response.data[0] if response.data else None


def store_file(filename, content, content_type):
    upload_file_to_bucket(filename, content, content_type)
    return insert_file_record(filename, content_type, len(content), get_file_url(filename))


def list_documents():
    response = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .order("uploaded_at", desc=True)
        .execute()
    )
    return response.data


def get_document(file_id):
    UUID(str(file_id))
    response = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .eq("file_id", str(file_id))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_document_file_url(file_id):
    document = get_document(file_id)
    return document["file_url"] if document else None


def update_file_flags(file_id, **flags):
    UUID(str(file_id))

    allowed_flags = {"is_summarized", "is_vectored"}
    row = {
        key: bool(value)
        for key, value in flags.items()
        if key in allowed_flags
    }

    if not row:
        return None

    response = (
        supabase.table(FILES_TABLE)
        .update(row)
        .eq("file_id", str(file_id))
        .execute()
    )
    return response.data[0] if response.data else None


def mark_file_summarized(file_id):
    return update_file_flags(file_id, is_summarized=True)


def mark_file_vectored(file_id):
    return update_file_flags(file_id, is_vectored=True)
