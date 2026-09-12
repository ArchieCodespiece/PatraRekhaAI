"""Deadlines, document families, actions, and MCP API router."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.dependencies import (
    get_authenticated_identity,
    verify_requested_email,
)
from db.document_metadata import list_document_metadata_by_file_ids
from db.files import list_documents
from mcp.server import PatraRekhaMCPServer
from services.deadline_intelligence import (
    build_deadline_model,
    detect_deadline_conflicts,
)
from services.document_diff import compare_documents
from services.document_families import (
    build_document_family,
)


router = APIRouter(tags=["deadlines"])


def _hydrate_user_documents(effective_email: str) -> list[dict[str, Any]]:
    """Fetch files and join metadata for the authenticated user."""
    documents = list_documents(owner_email=effective_email)
    file_ids = [str(d.get("file_id")) for d in documents if d.get("file_id")]
    metadata_rows = list_document_metadata_by_file_ids(file_ids)
    meta_by_id = {str(m.get("file_id")): m for m in metadata_rows}

    hydrated = []
    for doc in documents:
        fid = str(doc.get("file_id"))
        meta = meta_by_id.get(fid, {})
        merged = dict(doc)
        merged["file_heading"] = meta.get("file_heading") or doc.get("filename")
        merged["summarization"] = meta.get("summarization")
        merged["timeline_json"] = meta.get("timeline_json")
        merged["dates_json"] = meta.get("dates_json")
        merged["actions_json"] = meta.get("actions_json")
        merged["summary_source_sentences"] = meta.get("summary_source_sentences")
        hydrated.append(merged)
    return hydrated


@router.get("/deadlines")
def get_deadlines_endpoint(
    status: str | None = Query(None, description="Filter by UPCOMING, DUE_SOON, OVERDUE, SUPERSEDED, COMPLETED"),
    priority: str | None = Query(None, description="Filter by CRITICAL, HIGH, MEDIUM, LOW"),
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Retrieve normalized deadline intelligence across all user documents."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    hydrated_docs = _hydrate_user_documents(effective_email)
    all_deadlines = []
    today = date.today()

    for doc in hydrated_docs:
        fid = str(doc.get("file_id"))
        name = doc.get("file_heading") or doc.get("filename")
        timeline = doc.get("dates_json") or doc.get("timeline_json") or []
        if isinstance(timeline, str):
            try: timeline = json.loads(timeline)
            except Exception: timeline = []

        for item in timeline:
            raw_date = item.get("iso_date") or item.get("normalized") or item.get("date")
            event_label = item.get("event") or item.get("event_label") or "Important date"
            model = build_deadline_model(
                raw_date=raw_date,
                event_label=event_label,
                document_id=fid,
                document_name=name,
                page=item.get("page"),
                responsible_party=item.get("responsible_party"),
                source_sentence=item.get("sentence") or item.get("source_sentence"),
                status=item.get("status"),
                superseded_by=item.get("superseded_by"),
                today=today,
            )
            if model:
                if status and model["status"].upper() != status.upper():
                    continue
                if priority and model["priority"].upper() != priority.upper():
                    continue
                all_deadlines.append(model)

    all_deadlines.sort(key=lambda d: d["deadline"])
    return {
        "deadlines": all_deadlines,
        "count": len(all_deadlines),
    }


@router.get("/deadlines/conflicts")
def get_deadline_conflicts_endpoint(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Detect competing or conflicting deadlines across related documents."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    hydrated_docs = _hydrate_user_documents(effective_email)
    deadlines_res = get_deadlines_endpoint(owner_email=effective_email, identity=identity)
    conflicts = detect_deadline_conflicts(deadlines_res["deadlines"])

    return {
        "conflicts": conflicts,
        "count": len(conflicts),
    }


@router.get("/deadlines/actions")
def get_actions_endpoint(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Retrieve grounded actionable requirements and obligations."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    hydrated_docs = _hydrate_user_documents(effective_email)
    actions = []

    for doc in hydrated_docs:
        fid = str(doc.get("file_id"))
        actions_raw = doc.get("actions_json") or []
        if isinstance(actions_raw, str):
            try: actions_raw = json.loads(actions_raw)
            except Exception: actions_raw = []

        for act in actions_raw:
            act_copy = dict(act)
            act_copy["document_id"] = fid
            act_copy["document_name"] = doc.get("file_heading") or doc.get("filename")
            actions.append(act_copy)

    return {
        "actions": actions,
        "count": len(actions),
    }


@router.get("/documents/{file_id}/family")
def get_document_family_endpoint(
    file_id: str,
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Retrieve the document lineage family for a given document."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    hydrated_docs = _hydrate_user_documents(effective_email)
    families = build_document_family(hydrated_docs)

    for fam in families:
        member_ids = {str(m.get("file_id")) for m in fam.get("lineage", [])}
        if file_id in member_ids:
            return fam

    raise HTTPException(status_code=404, detail="Document not found or has no family.")


@router.get("/documents/{file_id}/changes")
def get_document_changes_endpoint(
    file_id: str,
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Retrieve 'What changed?' diff between an amendment document and its predecessor."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    hydrated_docs = _hydrate_user_documents(effective_email)
    families = build_document_family(hydrated_docs)

    target_family = None
    target_idx = None
    for fam in families:
        lineage = fam.get("lineage", [])
        for idx, m in enumerate(lineage):
            if str(m.get("file_id")) == str(file_id):
                target_family = fam
                target_idx = idx
                break
        if target_family:
            break

    if not target_family or target_idx is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if target_idx == 0:
        return {
            "file_id": file_id,
            "change_count": 0,
            "changes": [],
            "message": "This is the original/root document in the family.",
        }

    older_id = target_family["lineage"][target_idx - 1]["file_id"]
    doc_map = {str(d.get("file_id")): d for d in hydrated_docs}
    older_doc = doc_map.get(str(older_id), {})
    newer_doc = doc_map.get(str(file_id), {})

    return compare_documents(older_doc, newer_doc)


@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """Standard Model Context Protocol (MCP) JSON-RPC endpoint."""
    user_id, authenticated_email = identity
    effective_email = verify_requested_email(owner_email, authenticated_email)

    body = await request.json()
    method = body.get("method")
    params = body.get("params") or {}
    req_id = body.get("id", 1)

    provider = lambda: _hydrate_user_documents(effective_email)
    server = PatraRekhaMCPServer(provider)

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": server.list_tools()},
        }

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        res = server.call_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": res,
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }
