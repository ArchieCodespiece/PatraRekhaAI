"""Core tools for PatraRekhaAI Model Context Protocol (MCP) integration.

Thin integration layer calling existing backend services:
- list_recent_documents
- get_deadlines
- get_upcoming_deadlines
- get_overdue_deadlines
- get_document_family
- get_document_changes
- summarize_thread
- search_inbox
- get_document_evidence
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from services.deadline_intelligence import (
    build_deadline_model,
    detect_deadline_conflicts,
)
from services.document_families import (
    build_document_family,
    are_documents_in_same_family,
)
from services.document_diff import (
    compare_documents,
)


def list_recent_documents_tool(
    documents: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """List most recently processed documents with headings and metadata."""
    sorted_docs = sorted(
        documents,
        key=lambda d: str(d.get("created_at") or d.get("uploaded_at") or ""),
        reverse=True,
    )
    results = []
    for doc in sorted_docs[:limit]:
        results.append({
            "file_id": str(doc.get("file_id")),
            "filename": doc.get("filename"),
            "file_heading": doc.get("file_heading") or "Untitled Document",
            "created_at": doc.get("created_at") or doc.get("uploaded_at"),
            "is_summarized": bool(doc.get("is_summarized")),
            "is_vectored": bool(doc.get("is_vectored")),
        })
    return results


def get_deadlines_tool(
    documents: list[dict[str, Any]],
    status_filter: str | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Extract and normalize all deadlines across documents with status and priority."""
    today = today or date.today()
    all_deadlines = []

    for doc in documents:
        file_id = str(doc.get("file_id"))
        doc_name = doc.get("file_heading") or doc.get("filename") or "Document"
        timeline = doc.get("timeline_json") or []
        if isinstance(timeline, str):
            try: timeline = json.loads(timeline)
            except Exception: timeline = []

        for item in timeline:
            raw_date = item.get("iso_date") or item.get("date")
            event_label = item.get("event") or "Important date"
            page = item.get("page")
            status = item.get("status")

            dl = build_deadline_model(
                raw_date=raw_date,
                event_label=event_label,
                document_id=file_id,
                document_name=doc_name,
                page=page,
                status=status,
                today=today,
            )
            if dl:
                if status_filter and dl["status"].upper() != status_filter.upper():
                    continue
                all_deadlines.append(dl)

    return sorted(all_deadlines, key=lambda d: d["deadline"])


def get_upcoming_deadlines_tool(
    documents: list[dict[str, Any]],
    days: int = 7,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Get deadlines due within the specified number of days."""
    today = today or date.today()
    deadlines = get_deadlines_tool(documents, today=today)
    upcoming = []
    for d in deadlines:
        if d["status"] in ("SUPERSEDED", "COMPLETED"):
            continue
        try:
            dt = date.fromisoformat(d["deadline"])
            diff = (dt - today).days
            if 0 <= diff <= days:
                upcoming.append(d)
        except ValueError:
            continue
    return upcoming


def get_overdue_deadlines_tool(
    documents: list[dict[str, Any]],
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Get active deadlines that are past due."""
    today = today or date.today()
    deadlines = get_deadlines_tool(documents, status_filter="OVERDUE", today=today)
    return [d for d in deadlines if d.get("status") == "OVERDUE"]


def get_document_family_tool(
    file_id: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Retrieve the entire document family and lineage containing the given file_id."""
    families = build_document_family(documents)
    for fam in families:
        member_ids = {str(m.get("file_id")) for m in fam.get("lineage", [])}
        if str(file_id) in member_ids:
            return fam
    return None


def get_document_changes_tool(
    file_id: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Retrieve what changed between this document and its predecessor in the family."""
    fam = get_document_family_tool(file_id, documents)
    if not fam or len(fam.get("lineage", [])) < 2:
        return {"file_id": file_id, "changes": [], "message": "No predecessor document in family."}

    lineage = fam["lineage"]
    target_idx = None
    for idx, member in enumerate(lineage):
        if str(member.get("file_id")) == str(file_id):
            target_idx = idx
            break

    if target_idx is None or target_idx == 0:
        return {"file_id": file_id, "changes": [], "message": "Document is the root/original."}

    older_doc_id = lineage[target_idx - 1]["file_id"]
    doc_map = {str(d.get("file_id")): d for d in documents}
    doc_older = doc_map.get(str(older_doc_id), {})
    doc_newer = doc_map.get(str(file_id), {})

    return compare_documents(doc_older, doc_newer)


def get_document_evidence_tool(
    file_id: str,
    term: str,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Locate source sentences and page citations for a given term or date in a document."""
    doc_map = {str(d.get("file_id")): d for d in documents}
    doc = doc_map.get(str(file_id))
    if not doc:
        return []

    source_sentences = doc.get("summary_source_sentences") or []
    if isinstance(source_sentences, str):
        try: source_sentences = json.loads(source_sentences)
        except Exception: source_sentences = []

    matching = []
    term_lower = term.lower()
    for item in source_sentences:
        text = (item.get("text") or "").strip()
        if term_lower in text.lower():
            matching.append({
                "page": item.get("page"),
                "sentence": text,
                "file_id": file_id,
            })
    return matching
