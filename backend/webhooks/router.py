"""Supabase webhook endpoints."""

import os
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from webhooks.service.document_queue import document_queue
from webhooks.service.payloads import document_from_supabase_payload


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _secret_is_valid(authorization, webhook_secret):
    expected = os.getenv("WEBHOOK_SECRET")
    if not expected:
        return True

    if webhook_secret == expected:
        return True

    return authorization == f"Bearer {expected}"


@router.post("/supabase/files", status_code=status.HTTP_202_ACCEPTED)
async def supabase_files_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    x_webhook_secret: str | None = Header(default=None),
):
    if not _secret_is_valid(authorization, x_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload = await request.json()
    event_type = str(payload.get("type") or payload.get("event") or "").upper()
    if event_type and event_type not in {"INSERT", "INSERTED"}:
        return {"accepted": False, "ignored": True, "event_type": event_type}

    document = document_from_supabase_payload(payload)
    if not document:
        raise HTTPException(status_code=400, detail="Webhook payload does not contain a file record")

    try:
        UUID(str(document["file_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Webhook payload has an invalid file_id") from exc

    accepted = document_queue.enqueue(document)
    if not accepted:
        raise HTTPException(status_code=503, detail="Document queue is full")

    return {
        "accepted": True,
        "file_id": document["file_id"],
        "queue": document_queue.status(),
    }


@router.get("/queue/status")
async def queue_status():
    return document_queue.status()
