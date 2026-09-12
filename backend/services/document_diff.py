"""Document diffing, change detection, and deadline supersession tracking.

Compares two related documents in a family to identify:
- Deadline changes (original -> revised -> current)
- Action/obligation modifications
- Structured change items: {topic, old, new, importance, source}
- Marking older deadlines as SUPERSEDED for auditability
"""

from __future__ import annotations

from typing import Any


def detect_deadline_supersessions(
    older_timeline: list[dict[str, Any]],
    newer_timeline: list[dict[str, Any]],
    older_doc_id: str | None = None,
    newer_doc_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Detect superseded deadlines between older and newer versions of a document.
    
    Returns:
    - updated_older_timeline: older timeline items marked as SUPERSEDED with superseded_by
    - changes: list of detected changes
    """
    updated_older = []
    changes = []

    # Map newer timeline by event_type or semantic similarity
    newer_by_type: dict[str, dict[str, Any]] = {}
    for item in newer_timeline:
        etype = item.get("event_type") or "DEADLINE"
        if etype not in newer_by_type:
            newer_by_type[etype] = item

    for old_item in older_timeline:
        old_copy = dict(old_item)
        old_type = old_item.get("event_type") or "DEADLINE"
        old_date = old_item.get("iso_date") or old_item.get("date")

        matching_new = newer_by_type.get(old_type)
        if matching_new:
            new_date = matching_new.get("iso_date") or matching_new.get("date")
            if new_date and old_date and new_date != old_date:
                # Mark as superseded
                old_copy["status"] = "SUPERSEDED"
                old_copy["superseded_by"] = newer_doc_id
                old_copy["superseded_date"] = new_date

                changes.append({
                    "topic": "deadline",
                    "event": old_item.get("event", "Deadline"),
                    "old": old_date,
                    "new": new_date,
                    "importance": "high",
                    "source": f"Page {matching_new.get('page', '?')}",
                    "revision_history": {
                        "original": old_date,
                        "current": new_date,
                        "change_count": 1,
                    },
                })
            else:
                old_copy["status"] = "ACTIVE"
        else:
            old_copy["status"] = "ACTIVE"

        updated_older.append(old_copy)

    return updated_older, changes


def compare_documents(
    doc_older: dict[str, Any],
    doc_newer: dict[str, Any],
) -> dict[str, Any]:
    """Compare two documents in a family and return structured changes."""
    older_timeline = doc_older.get("timeline_json") or []
    newer_timeline = doc_newer.get("timeline_json") or []
    if isinstance(older_timeline, str):
        import json
        try: older_timeline = json.loads(older_timeline)
        except Exception: older_timeline = []
    if isinstance(newer_timeline, str):
        import json
        try: newer_timeline = json.loads(newer_timeline)
        except Exception: newer_timeline = []

    older_id = str(doc_older.get("file_id") or "older")
    newer_id = str(doc_newer.get("file_id") or "newer")

    updated_older, deadline_changes = detect_deadline_supersessions(
        older_timeline,
        newer_timeline,
        older_doc_id=older_id,
        newer_doc_id=newer_id,
    )

    all_changes = list(deadline_changes)

    # Check for title / scope changes
    heading_old = doc_older.get("file_heading") or ""
    heading_new = doc_newer.get("file_heading") or ""
    if heading_old and heading_new and heading_old.lower() != heading_new.lower():
        all_changes.append({
            "topic": "heading",
            "old": heading_old,
            "new": heading_new,
            "importance": "medium",
            "source": "Document Header",
        })

    # Compare key points / summaries
    summary_old = doc_older.get("summarization") or ""
    summary_new = doc_newer.get("summarization") or ""
    if summary_old and summary_new and summary_old != summary_new:
        all_changes.append({
            "topic": "summary_revision",
            "old": summary_old[:150] + "..." if len(summary_old) > 150 else summary_old,
            "new": summary_new[:150] + "..." if len(summary_new) > 150 else summary_new,
            "importance": "medium",
            "source": "Document Summary",
        })

    return {
        "older_document_id": older_id,
        "newer_document_id": newer_id,
        "change_count": len(all_changes),
        "changes": all_changes,
        "superseded_older_timeline": updated_older,
    }
