
"""Supabase file storage and database helpers.

Storage architecture:

Supabase bucket:
    file_storage/

Objects:
    file_storage/
        documents/
            <user_id>/
                file1.pdf
                file2.pdf

A single bucket is shared by all users.
User isolation is achieved by storing files under the user's
Supabase Auth UUID.
"""

import json
import os
from uuid import UUID
from urllib.request import Request, urlopen

from db.supabase_client import supabase


# ============================================================================
# Configuration
# ============================================================================

# Your EXISTING Supabase Storage bucket.
DEFAULT_FILE_STORAGE_BUCKET = os.getenv(
    "SUPABASE_FILE_STORAGE_BUCKET",
    "file_storage",
)

FILES_TABLE = os.getenv(
    "SUPABASE_FILES_TABLE",
    "files",
)

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")


FILE_SELECT_COLUMNS = (
    "file_id,"
    "filename,"
    "file_type,"
    "file_size,"
    "file_url,"
    "owner_email,"
    "user_id,"
    "created_at,"
    "uploaded_at,"
    "is_summarized,"
    "is_vectored,"
    "content_hash"
)


# ============================================================================
# User / path helpers
# ============================================================================

def normalize_owner_email(owner_email: str | None) -> str:
    """Normalize an owner email for consistent database queries."""
    return (owner_email or "").strip().lower()


def normalize_user_id(user_id: str | UUID | None) -> str:
    """Validate and normalize a Supabase Auth user UUID."""

    if not user_id:
        raise ValueError("user_id is required for file storage.")

    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"Invalid Supabase user_id: {user_id}"
        ) from exc


def get_bucket_name() -> str:
    """Return the existing Supabase Storage bucket."""
    return DEFAULT_FILE_STORAGE_BUCKET


def get_storage_path(
    filename: str,
    user_id: str | UUID,
) -> str:
    """
    Return the storage object path for a user's file.

    Example:
        documents/550e8400-e29b-41d4-a716-446655440000/report.pdf
    """

    user_id = normalize_user_id(user_id)

    # Prevent path traversal.
    filename = os.path.basename(filename)

    if not filename:
        raise ValueError("Filename cannot be empty.")

    return f"documents/{user_id}/{filename}"


# ============================================================================
# Storage bucket
# ============================================================================

def ensure_bucket_exists() -> str:
    """
    Verify that the configured Supabase Storage bucket exists.

    IMPORTANT:
    The bucket is expected to be created manually in Supabase.
    This function deliberately does NOT attempt to create or modify
    the bucket automatically.
    """

    bucket = get_bucket_name()

    if not bucket:
        raise RuntimeError(
            "SUPABASE_FILE_STORAGE_BUCKET is empty."
        )

    try:
        supabase.storage.get_bucket(bucket)

    except Exception as exc:
        raise RuntimeError(
            f"Supabase Storage bucket '{bucket}' was not found "
            f"or is inaccessible. Create the bucket in Supabase "
            f"Storage or check SUPABASE_FILE_STORAGE_BUCKET."
        ) from exc

    return bucket


# ============================================================================
# Storage operations
# ============================================================================

def upload_file_to_bucket(
    filename,
    content,
    content_type,
    user_id,
):
    """
    Upload a user's file into:

        file_storage/documents/<user_id>/<filename>
    """

    bucket = ensure_bucket_exists()

    storage_path = get_storage_path(
        filename,
        user_id,
    )

    return supabase.storage.from_(bucket).upload(
        storage_path,
        content,
        {
            "content-type": content_type
            or "application/octet-stream",
            "upsert": "true",
        },
    )


def get_file_url(
    filename,
    user_id,
):
    """Return the public URL for a stored file."""

    bucket = get_bucket_name()

    storage_path = get_storage_path(
        filename,
        user_id,
    )

    return supabase.storage.from_(bucket).get_public_url(
        storage_path
    )


# ============================================================================
# Processing webhook
# ============================================================================

def trigger_processing_webhook(file_record):
    """Trigger the backend document-processing webhook."""

    webhook_secret = os.getenv("WEBHOOK_SECRET")

    backend_url = os.getenv(
        "API_BASE_URL",
        "http://localhost:8001",
    )

    url = (
        f"{backend_url.rstrip('/')}"
        "/webhooks/supabase/files"
    )

    headers = {
        "Content-Type": "application/json",
    }

    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret

    payload = json.dumps(file_record).encode("utf-8")

    request = Request(
        url,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except Exception as error:
        print(
            "Failed to trigger processing webhook "
            f"for {file_record.get('filename')}: {error}"
        )
        return None


# ============================================================================
# Database queries
# ============================================================================

def find_file_by_content_hash(
    content_hash: str,
    owner_email: str | None = None,
    user_id: str | UUID | None = None,
) -> dict | None:
    """
    Return an existing file record matching the content hash.

    Deduplication is scoped to the user.
    """

    if not content_hash:
        return None

    owner_email = normalize_owner_email(owner_email)

    query = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .eq("content_hash", content_hash)
    )

    if user_id:
        query = query.eq(
            "user_id",
            normalize_user_id(user_id),
        )

    elif owner_email:
        query = query.eq(
            "owner_email",
            owner_email,
        )

    try:
        response = query.limit(1).execute()

        return (
            response.data[0]
            if response.data
            else None
        )

    except Exception:
        return None


# ============================================================================
# File database record
# ============================================================================

def insert_file_record(
    filename,
    content_type,
    file_size,
    file_url,
    owner_email=None,
    user_id=None,
    content_hash: str | None = None,
):
    """
    Insert a new file record.

    user_id:
        Supabase Auth user UUID.

    owner_email:
        Application-level owner metadata.
    """

    owner_email = normalize_owner_email(owner_email)
    user_id = normalize_user_id(user_id)

    # ------------------------------------------------------------------
    # Deduplicate by content hash
    # ------------------------------------------------------------------

    if content_hash:

        existing = find_file_by_content_hash(
            content_hash,
            owner_email=owner_email,
            user_id=user_id,
        )

        if existing:
            print(
                "Duplicate document detected by content hash "
                f"({content_hash[:16]}...): "
                f"returning existing record "
                f"'{existing.get('filename')}'"
            )

            if (
                not existing.get("is_summarized")
                or not existing.get("is_vectored")
            ):
                trigger_processing_webhook(existing)

            return existing

    # ------------------------------------------------------------------
    # Deduplicate by storage URL
    # ------------------------------------------------------------------

    try:
        url_query = (
            supabase.table(FILES_TABLE)
            .select(FILE_SELECT_COLUMNS)
            .eq("file_url", file_url)
            .eq("user_id", user_id)
        )

        existing_by_url = url_query.execute()

        if existing_by_url.data:

            record = existing_by_url.data[0]

            if (
                not record.get("is_summarized")
                or not record.get("is_vectored")
            ):
                trigger_processing_webhook(record)

            return record

    except Exception:
        pass

    # ------------------------------------------------------------------
    # New file
    # ------------------------------------------------------------------

    row = {
        "filename": filename,
        "file_type": (
            content_type
            or "application/octet-stream"
        ),
        "file_size": file_size,
        "file_url": file_url,
        "owner_email": owner_email,
        "user_id": user_id,
        "is_summarized": False,
        "is_vectored": False,
    }

    if content_hash:
        row["content_hash"] = content_hash

    try:

        response = (
            supabase.table(FILES_TABLE)
            .insert(row)
            .execute()
        )

    except Exception as exc:

        error_msg = str(exc)

        # Handle race conditions / duplicate inserts.
        if (
            "23505" in error_msg
            or "duplicate key" in error_msg.lower()
        ):

            print(
                f"Duplicate document for user {user_id} "
                f"({content_hash[:16] if content_hash else '?' }...) "
                "— falling back to lookup."
            )

            existing = find_file_by_content_hash(
                content_hash,
                owner_email=owner_email,
                user_id=user_id,
            )

            if existing:
                return existing

            try:

                url_query = (
                    supabase.table(FILES_TABLE)
                    .select(FILE_SELECT_COLUMNS)
                    .eq("file_url", file_url)
                    .eq("user_id", user_id)
                )

                url_result = url_query.execute()

                if url_result.data:
                    return url_result.data[0]

            except Exception:
                pass

        raise

    new_record = (
        response.data[0]
        if response.data
        else None
    )

    if new_record:
        trigger_processing_webhook(new_record)

    return new_record


# ============================================================================
# Main storage entry point
# ============================================================================

def store_file(
    filename,
    content,
    content_type,
    owner_email=None,
    user_id=None,
    content_hash: str | None = None,
):
    """
    Upload content to the existing Supabase Storage bucket
    and create/return the corresponding database record.

    Storage:

        file_storage/
            documents/
                <user_id>/
                    <filename>
    """

    user_id = normalize_user_id(user_id)

    # Verify the existing bucket.
    # This NO LONGER attempts to create it.
    ensure_bucket_exists()

    # Upload file.
    upload_file_to_bucket(
        filename,
        content,
        content_type,
        user_id=user_id,
    )

    # Generate public URL.
    file_url = get_file_url(
        filename,
        user_id=user_id,
    )

    # Store metadata.
    return insert_file_record(
        filename,
        content_type,
        len(content),
        file_url,
        owner_email=owner_email,
        user_id=user_id,
        content_hash=content_hash,
    )


# ============================================================================
# Document listing
# ============================================================================

def list_documents(
    owner_email=None,
    user_id=None,
):
    """Return documents belonging to a user."""

    owner_email = normalize_owner_email(owner_email)

    query = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
    )

    if user_id:

        query = query.eq(
            "user_id",
            normalize_user_id(user_id),
        )

    elif owner_email:

        query = query.eq(
            "owner_email",
            owner_email,
        )

    response = query.order(
        "uploaded_at",
        desc=True,
    ).execute()

    return response.data


def list_ready_documents(
    owner_email=None,
    user_id=None,
):
    """Return documents that have completed processing."""

    owner_email = normalize_owner_email(owner_email)

    query = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .eq("is_summarized", True)
        .eq("is_vectored", True)
    )

    if user_id:

        query = query.eq(
            "user_id",
            normalize_user_id(user_id),
        )

    elif owner_email:

        query = query.eq(
            "owner_email",
            owner_email,
        )

    response = query.order(
        "uploaded_at",
        desc=True,
    ).execute()

    return response.data


# ============================================================================
# Individual document operations
# ============================================================================

def get_document(
    file_id,
    owner_email=None,
    user_id=None,
):
    """Return a single document belonging to the user."""

    owner_email = normalize_owner_email(owner_email)

    UUID(str(file_id))

    query = (
        supabase.table(FILES_TABLE)
        .select(FILE_SELECT_COLUMNS)
        .eq("file_id", str(file_id))
    )

    if user_id:

        query = query.eq(
            "user_id",
            normalize_user_id(user_id),
        )

    elif owner_email:

        query = query.eq(
            "owner_email",
            owner_email,
        )

    response = query.limit(1).execute()

    return (
        response.data[0]
        if response.data
        else None
    )


def get_document_file_url(
    file_id,
    owner_email=None,
    user_id=None,
):
    """Return the stored URL for a document."""

    document = get_document(
        file_id,
        owner_email=owner_email,
        user_id=user_id,
    )

    return (
        document["file_url"]
        if document
        else None
    )


# ============================================================================
# Storage deletion
# ============================================================================

def delete_file_from_storage(
    filename,
    user_id,
):
    """
    Remove a user's stored file.

    Storage path:

        documents/<user_id>/<filename>
    """

    bucket = get_bucket_name()

    storage_path = get_storage_path(
        filename,
        user_id,
    )

    try:

        return supabase.storage.from_(bucket).remove(
            [storage_path]
        )

    except Exception as exc:

        print(
            f"Failed to delete storage file "
            f"'{storage_path}': {exc}"
        )

        return []


def delete_file_record(
    file_id,
    owner_email=None,
    user_id=None,
):
    """Delete a file row from the files table."""

    owner_email = normalize_owner_email(owner_email)

    UUID(str(file_id))

    query = (
        supabase.table(FILES_TABLE)
        .delete()
        .eq("file_id", str(file_id))
    )

    if user_id:

        query = query.eq(
            "user_id",
            normalize_user_id(user_id),
        )

    elif owner_email:

        query = query.eq(
            "owner_email",
            owner_email,
        )

    response = query.execute()

    return (
        response.data[0]
        if response.data
        else None
    )


# ============================================================================
# Processing flags
# ============================================================================

def update_file_flags(
    file_id,
    **flags,
):
    """Update document processing flags."""

    UUID(str(file_id))

    allowed_flags = {
        "is_summarized",
        "is_vectored",
    }

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

    return (
        response.data[0]
        if response.data
        else None
    )


def mark_file_summarized(file_id):
    """Mark a document as summarized."""

    return update_file_flags(
        file_id,
        is_summarized=True,
    )


def mark_file_vectored(file_id):
    """Mark a document as vectored."""

    return update_file_flags(
        file_id,
        is_vectored=True,
    )

