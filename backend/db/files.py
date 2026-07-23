"""Wrappers for standard file storage queries."""

import os
from uuid import UUID

from db.supabase_client import supabase


FILE_STORAGE_BUCKET = os.getenv("SUPABASE_FILE_STORAGE_BUCKET", "file_storage")
FILES_TABLE = os.getenv("SUPABASE_FILES_TABLE", "files")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")


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
        .select("file_id,filename,file_type,file_size,file_url,created_at,uploaded_at")
        .order("uploaded_at", desc=True)
        .execute()
    )
    return response.data


def get_document_file_url(file_id):
    UUID(str(file_id))
    response = (
        supabase.table(FILES_TABLE)
        .select("file_url")
        .eq("file_id", str(file_id))
        .limit(1)
        .execute()
    )
    return response.data[0]["file_url"] if response.data else None
