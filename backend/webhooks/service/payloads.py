"""Helpers for normalizing Supabase webhook payloads."""


def document_from_supabase_payload(payload):
    if not isinstance(payload, dict):
        return None

    record = (
        payload.get("record")
        or payload.get("new")
        or payload.get("data", {}).get("record")
        or payload.get("data", {}).get("new")
    )

    if not isinstance(record, dict):
        record = payload

    file_id = record.get("file_id") or record.get("id")
    filename = record.get("filename") or record.get("name")
    file_url = record.get("file_url") or record.get("url")

    if not file_id or not filename:
        return None

    return {
        "file_id": str(file_id),
        "filename": filename,
        "file_url": file_url,
        "file_type": record.get("file_type") or record.get("content_type"),
        "file_size": record.get("file_size") or record.get("size"),
        "created_at": record.get("created_at"),
        "uploaded_at": record.get("uploaded_at"),
        "raw": record,
    }
