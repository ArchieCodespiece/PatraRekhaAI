"""Wrappers for standard file storage queries."""

import os
from uuid import UUID

from db.supabase_client import supabase


FILE_STORAGE_BUCKET = os.getenv("SUPABASE_FILE_STORAGE_BUCKET", "file_storage")
FILES_TABLE = os.getenv("SUPABASE_FILES_TABLE", "files")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
FILE_SELECT_COLUMNS = (
    "file_id,filename,file_type,file_size,file_url,owner_email,created_at,uploaded_at,"
    "is_summarized,is_vectored,content_hash"
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


import json
from urllib.request import Request, urlopen

def trigger_processing_webhook(file_record):
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    backend_url = os.getenv("API_BASE_URL", "http://localhost:8001")
    url = f"{backend_url.rstrip('/')}/webhooks/supabase/files"
    
    headers = {
        "Content-Type": "application/json",
    }
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    payload = json.dumps(file_record).encode("utf-8")
    request = Request(url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        print(f"Failed to trigger processing webhook for {file_record.get('filename')}: {error}")
        return None


def find_file_by_content_hash(content_hash: str) -> dict | None:
    """Return an existing file record whose full SHA-256 content hash matches.

    This is the primary deduplication check: two files with identical bytes
    are the same document regardless of their filename or who sent them.
    Returns ``None`` when the column doesn't exist yet (migration not run).
    """
    if not content_hash:
        return None
    try:
        response = (
            supabase.table(FILES_TABLE)
            .select(FILE_SELECT_COLUMNS)
            .eq("content_hash", content_hash)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None
    except Exception:
        # Column may not exist yet – degrade gracefully
        return None


def insert_file_record(
    filename,
    content_type,
    file_size,
    file_url,
    owner_email=None,
    content_hash: str | None = None,
):
    # ----------------------------------------------------------------
    # Priority 1: deduplicate by full content hash (same bytes = same
    # document, regardless of filename or sender)
    # ----------------------------------------------------------------
    if content_hash:
        existing = find_file_by_content_hash(content_hash)
        if existing:
            print(
                f"Duplicate document detected by content hash "
                f"({content_hash[:16]}…): returning existing record "
                f"'{existing.get('filename')}'"
            )
            if not existing.get("is_summarized") or not existing.get("is_vectored"):
                trigger_processing_webhook(existing)
            return existing

    # ----------------------------------------------------------------
    # Priority 2: deduplicate by Supabase storage URL (same stored file)
    # ----------------------------------------------------------------
    try:
        existing_by_url = (
            supabase.table(FILES_TABLE)
            .select(FILE_SELECT_COLUMNS)
            .eq("file_url", file_url)
            .execute()
        )
        if existing_by_url.data:
            record = existing_by_url.data[0]
            if owner_email and record.get("owner_email") != owner_email:
                supabase.table(FILES_TABLE).update({"owner_email": owner_email}).eq("file_id", record["file_id"]).execute()
                record["owner_email"] = owner_email

            if not record.get("is_summarized") or not record.get("is_vectored"):
                trigger_processing_webhook(record)

            return record
    except Exception:
        pass

    # ----------------------------------------------------------------
    # New file: insert into the database
    # ----------------------------------------------------------------
    row = {
        "filename": filename,
        "file_type": content_type or "application/octet-stream",
        "file_size": file_size,
        "file_url": file_url,
        "owner_email": owner_email,
        "is_summarized": False,
        "is_vectored": False,
    }
    if content_hash:
        row["content_hash"] = content_hash

    response = (
        supabase.table(FILES_TABLE)
        .insert(row)
        .execute()
    )
    new_record = response.data[0] if response.data else None
    if new_record:
        trigger_processing_webhook(new_record)
    return new_record



def store_file(filename, content, content_type, owner_email=None, content_hash: str | None = None):
    """Upload content to bucket and insert/return the file DB record.

    ``content_hash`` should be the full SHA-256 hex digest of ``content``.
    When provided it is stored in the DB and used for content-based dedup
    so that identical documents from different senders are never processed twice.
    """
    upload_file_to_bucket(filename, content, content_type)
    return insert_file_record(
        filename,
        content_type,
        len(content),
        get_file_url(filename),
        owner_email=owner_email,
        content_hash=content_hash,
    )


def list_documents(owner_email=None):
    query = supabase.table(FILES_TABLE).select(FILE_SELECT_COLUMNS)
    if owner_email:
        query = query.eq("owner_email", owner_email)

    response = query.order("uploaded_at", desc=True).execute()
    return response.data


def list_ready_documents(owner_email=None):
    query = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .eq("is_summarized", True)
        .eq("is_vectored", True)
    )
    if owner_email:
        query = query.eq("owner_email", owner_email)

    response = query.order("uploaded_at", desc=True).execute()
    return response.data


def get_document(file_id, owner_email=None):
    UUID(str(file_id))
    query = supabase.table(FILES_TABLE).select(FILE_SELECT_COLUMNS).eq("file_id", str(file_id))
    if owner_email:
        query = query.eq("owner_email", owner_email)
    response = query.limit(1).execute()
    return response.data[0] if response.data else None


def get_document_file_url(file_id, owner_email=None):
    document = get_document(file_id, owner_email=owner_email)
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
