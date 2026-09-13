"""Intake Gatekeeper administration API.

Endpoints (all scoped to the authenticated user's own workspace):

    GET   /intake/categories                 document type catalog
    GET   /intake/policies                   policy config for the user's workspace
    POST  /intake/policies                   create/update policy configuration
    DELETE /intake/policies/{workspace_id}   remove policy configuration
    GET   /intake/decisions                  quarantine / audit list
    POST  /intake/decisions/{file_id}/override   release (ALLOW) or hold (BLOCK)

These endpoints manage CONFIGURATION only.  The ALLOW/REVIEW/BLOCK business
logic lives in the gatekeeper package and applies to every ingestion source
at the document-processing choke point.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import (
    get_authenticated_identity,
)
from db import intake_decisions
from db import intake_policies
from db.files import get_document
from gatekeeper.categories import CATEGORY_LABELS, DEFAULT_CATEGORIES


router = APIRouter(prefix="/intake", tags=["intake"])


# ============================================================================
# Models
# ============================================================================

class SenderRule(BaseModel):
    match: str = "domain"
    value: str
    action: str = "block"


class KeywordRule(BaseModel):
    match: str = "regex"
    value: str
    action: str = "block"


class PolicyPayload(BaseModel):
    workspace_id: str
    name: Optional[str] = None
    allowed_categories: list[str] = Field(default_factory=list)
    blocked_categories: list[str] = Field(default_factory=list)
    review_categories: list[str] = Field(default_factory=list)
    sender_rules: list[SenderRule] = Field(default_factory=list)
    keyword_rules: list[KeywordRule] = Field(default_factory=list)
    min_confidence: float = 0
    default_decision: str = "REVIEW"
    enabled: bool = False


class OverridePayload(BaseModel):
    decision: str


def _validate_categories(categories: list[str]) -> None:
    valid = set(DEFAULT_CATEGORIES)
    for category in categories:
        if category not in valid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown document category: {category}",
            )


def _own_workspaces(user_id: str, owner_email: str | None) -> list[str]:
    workspaces = [user_id]
    if owner_email:
        workspaces.append(owner_email.lower())
    return workspaces


def _workspace_is_owned(workspace_id: str, user_id: str, owner_email: str | None) -> bool:
    return workspace_id in _own_workspaces(user_id, owner_email)


# ============================================================================
# Categories
# ============================================================================

@router.get("/categories")
def intake_categories():
    return {
        "categories": [
            {
                "id": category,
                "label": CATEGORY_LABELS.get(category, category),
            }
            for category in DEFAULT_CATEGORIES
        ]
    }


# ============================================================================
# Policy configuration
# ============================================================================

@router.get("/policies")
def list_policies(
    identity=Depends(get_authenticated_identity),
):
    user_id, owner_email = identity
    workspaces = _own_workspaces(user_id, owner_email)
    workspaces.append(intake_policies.DEFAULT_WORKSPACE)

    return {
        "policies": intake_policies.list_policies(workspaces),
    }


@router.post("/policies")
def upsert_policy(
    payload: PolicyPayload,
    identity=Depends(get_authenticated_identity),
):
    user_id, owner_email = identity

    workspace_id = payload.workspace_id.strip()

    if not _workspace_is_owned(workspace_id, user_id, owner_email):
        raise HTTPException(
            status_code=403,
            detail=(
                "You can only configure an intake policy for your own "
                "workspace (user_id or registered email)."
            ),
        )

    _validate_categories(payload.allowed_categories)
    _validate_categories(payload.blocked_categories)
    _validate_categories(payload.review_categories)

    if payload.default_decision.upper() not in {"ALLOW", "REVIEW", "BLOCK"}:
        raise HTTPException(
            status_code=400,
            detail="default_decision must be ALLOW, REVIEW or BLOCK.",
        )

    _validate_rules(payload.sender_rules)
    _validate_rules(payload.keyword_rules)

    try:
        policy = intake_policies.upsert_policy(
            workspace_id=workspace_id,
            name=payload.name,
            allowed_categories=payload.allowed_categories,
            blocked_categories=payload.blocked_categories,
            review_categories=payload.review_categories,
            sender_rules=[rule.model_dump() for rule in payload.sender_rules],
            keyword_rules=[rule.model_dump() for rule in payload.keyword_rules],
            min_confidence=payload.min_confidence,
            default_decision=payload.default_decision,
            enabled=payload.enabled,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not policy:
        raise HTTPException(
            status_code=500,
            detail="Failed to persist intake policy.",
        )

    return {"ok": True, "policy": policy}


@router.delete("/policies/{workspace_id}")
def delete_policy(
    workspace_id: str,
    identity=Depends(get_authenticated_identity),
):
    user_id, owner_email = identity

    if not _workspace_is_owned(workspace_id, user_id, owner_email):
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own workspace policy.",
        )

    intake_policies.delete_policy(workspace_id)

    return {"ok": True, "workspace_id": workspace_id}


# ============================================================================
# Quarantine / audit
# ============================================================================

@router.get("/decisions")
def list_decisions(
    decision: str | None = None,
    limit: int = 100,
    identity=Depends(get_authenticated_identity),
):
    user_id, owner_email = identity

    policies = intake_policies.list_policies(
        _own_workspaces(user_id, owner_email)
    )

    if not policies:
        return {"decisions": []}

    workspace_ids = _own_workspaces(user_id, owner_email)

    rows = []
    seen = set()
    for workspace_id in workspace_ids:
        for row in intake_decisions.list_decisions(
            workspace_id=workspace_id,
            decision=decision,
            limit=min(max(limit, 1), 200),
        ):
            row_id = str(row.get("id") or "")
            if row_id and row_id not in seen:
                seen.add(row_id)
                rows.append(row)

    rows.sort(
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )

    return {"decisions": rows[: min(max(limit, 1), 200)]}


@router.post("/decisions/{file_id}/override")
def set_override(
    file_id: str,
    payload: OverridePayload,
    identity=Depends(get_authenticated_identity),
):
    user_id, owner_email = identity

    decision = payload.decision.strip().upper()
    if decision not in {"ALLOW", "BLOCK"}:
        raise HTTPException(
            status_code=400,
            detail="Override decision must be ALLOW or BLOCK.",
        )

    try:
        document = get_document(
            file_id,
            user_id=user_id,
        )
    except Exception:
        document = get_document(
            file_id,
            owner_email=owner_email,
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    intake_decisions.set_override(
        file_id,
        decision,
        workspace_id=str(user_id or ""),
    )

    if decision == "ALLOW":
        _strip_metadata_for_refresh(document)

        from webhooks.service.document_queue import document_queue

        enqueued = document_queue.enqueue(
            {
                "file_id": str(document["file_id"]),
                "filename": document.get("filename"),
                "user_id": user_id,
                "owner_email": owner_email,
            }
        )
        if not enqueued:
            raise HTTPException(
                status_code=503,
                detail="Document queue is full. Override saved; retry release.",
            )
    else:
        _clear_processed_state(document)

    return {
        "ok": True,
        "file_id": file_id,
        "override_decision": decision,
        "reprocessing": decision == "ALLOW",
    }


# ============================================================================
# Helpers
# ============================================================================

def _strip_metadata_for_refresh(document: dict) -> None:
    """Drop stale summary metadata before a release (ALLOW) reprocess.

    The document-processing worker skips summarization when a metadata row
    already exists.  Releasing an override therefore would keep the OLD
    summary unless we remove it first.  This guarantees the document is
    re-summarized with the newer extractive pipeline.
    """

    file_id = str(document.get("file_id") or "")

    try:
        from db.files import update_file_flags
        update_file_flags(file_id, is_summarized=False)
    except Exception as exc:
        print(f"Intake gatekeeper: could not clear is_summarized for {file_id}: {exc}")

    try:
        from db.document_metadata import delete_document_metadata
        delete_document_metadata(file_id)
    except Exception as exc:
        print(f"Intake gatekeeper: could not delete metadata for {file_id}: {exc}")


def _clear_processed_state(document: dict) -> None:
    """Completely delete a BLOCKED document from storage, DB records, metadata, and Pinecone vectors."""

    file_id = str(document.get("file_id") or "")
    filename = str(document.get("filename") or "")
    user_id = document.get("user_id")
    owner_email = document.get("owner_email")

    # 1. Delete Pinecone vectors
    namespace = str(user_id or owner_email or "").strip()
    if namespace:
        try:
            from vectorstore.pinecone_store import PineconeStore
            store = PineconeStore(namespace=namespace)
            clean_name = filename.replace(".pdf", "").replace(".PDF", "")
            for candidate in {filename, clean_name, f"{file_id}-{filename}", f"{file_id}-{clean_name}"}:
                store.delete_document(candidate, namespace=namespace)
        except Exception as exc:
            print(f"Intake gatekeeper: Pinecone cleanup for {file_id}: {exc}")

    # 2. Delete file from storage bucket
    try:
        from db.files import delete_file_from_storage
        delete_file_from_storage(filename, owner_email=owner_email, user_id=user_id)
    except Exception as exc:
        print(f"Intake gatekeeper: storage cleanup failed for {file_id}: {exc}")

    # 3. Delete DB file record
    try:
        from db.files import delete_file_record
        delete_file_record(file_id, owner_email=owner_email, user_id=user_id)
    except Exception as exc:
        print(f"Intake gatekeeper: file record deletion failed for {file_id}: {exc}")

    # 4. Delete document metadata
    try:
        from db.document_metadata import delete_document_metadata
        delete_document_metadata(file_id)
    except Exception as exc:
        print(f"Intake gatekeeper: metadata deletion failed for {file_id}: {exc}")


def _validate_rules(rules) -> None:
    for rule in rules:
        value = str(rule.value or "").strip()
        if not value:
            raise HTTPException(
                status_code=400,
                detail="Rule value cannot be empty.",
            )
        if rule.match not in {"domain", "email", "regex"}:
            raise HTTPException(
                status_code=400,
                detail="Rule match must be domain, email or regex.",
            )
        if rule.action not in {"allow", "block"}:
            raise HTTPException(
                status_code=400,
                detail="Rule action must be allow or block.",
            )