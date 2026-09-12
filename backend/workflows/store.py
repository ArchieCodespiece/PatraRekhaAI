"""Delivery of generated export files to Supabase Storage."""

from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

EXPORT_FOLDER = "exports"


def _get_supabase():
    from db.supabase_client import supabase

    return supabase


def _get_bucket_name() -> str:
    from db.files import get_bucket_name

    return get_bucket_name()


def storage_path(
    user_id: str,
    conversation_id: str,
    filename: str,
) -> str:
    UUID(str(user_id))

    safe_name = os.path.basename(filename)

    return f"{EXPORT_FOLDER}/{user_id}/{conversation_id}/{safe_name}"


def upload_export_file(
    user_id: str,
    conversation_id: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    """
    Upload a generated export and return its public/shared URL.

    Uses a signed URL (one-day default lifetime); falls back to the
    public URL when the bucket is public.
    """

    supabase = _get_supabase()
    bucket = _get_bucket_name()

    path = storage_path(user_id, conversation_id, filename)

    supabase.storage.from_(bucket).upload(
        path,
        content,
        {
            "content-type": content_type or "application/octet-stream",
            "upsert": "true",
        },
    )

    return signed_url_for_path(path, lifetime=86400)


def signed_url_for_path(
    path: str,
    lifetime: int = 86400,
) -> str:
    supabase = _get_supabase()
    bucket = _get_bucket_name()

    try:
        response = supabase.storage.from_(bucket).create_signed_url(
            path,
            lifetime,
        )

        if isinstance(response, dict):
            url = response.get("signedURL") or response.get("signedUrl")
        else:
            url = (
                getattr(response, "signedURL", None)
                or getattr(response, "signedUrl", None)
            )

        if url:
            return url

    except Exception as exc:
        print(f"[workflows] signed URL failed for {path}: {exc}")

    return supabase.storage.from_(bucket).get_public_url(path)