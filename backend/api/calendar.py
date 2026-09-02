from __future__ import annotations

import json
from datetime import date
from typing import Any, List

from fastapi import (
    APIRouter,
    Depends,
)

from api.dependencies import (
    get_authenticated_identity,
    verify_requested_email,
)

from db.files import (
    list_documents,
)

from db.document_metadata import (
    list_document_metadata_by_file_ids,
)


router = APIRouter()


# ============================================================================
# TIMELINE HELPERS
# ============================================================================

def parse_timeline_json(
    value: Any,
):
    if not value:
        return []

    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, list):
            return [
                item
                for item in parsed
                if isinstance(item, dict)
            ]

    return []


def parse_dd_mm_yyyy(
    value: str,
):
    import re

    match = re.search(
        r"\b(\d{1,2})/"
        r"(\d{1,2})/"
        r"(\d{4})\b",
        value or "",
    )

    if not match:
        return None

    day, month, year = (
        int(part)
        for part in match.groups()
    )

    try:
        return date(
            year,
            month,
            day,
        )
    except ValueError:
        return None


def event_priority(
    event_text: str,
):
    text = (
        event_text or ""
    ).lower()

    if any(
        word in text
        for word in (
            "deadline",
            "submission",
            "award",
            "closes",
            "due",
        )
    ):
        return "high"

    if any(
        word in text
        for word in (
            "opens",
            "begins",
            "notification",
            "visit",
            "presentation",
        )
    ):
        return "medium"

    return "normal"


# ============================================================================
# CALENDAR
# ============================================================================

@router.get("/calendar-events")
def get_calendar_events(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    documents = list_documents(
        owner_email=effective_email
    )

    allowed_file_ids = {
        str(document.get("file_id"))
        for document in documents
        if document.get("file_id")
    }

    metadata_rows = list_document_metadata_by_file_ids(
        list(allowed_file_ids)
    )

    events = []

    for metadata in metadata_rows:
        file_id = str(
            metadata.get("file_id")
            or ""
        )

        if (
            allowed_file_ids
            and file_id not in allowed_file_ids
        ):
            continue

        file_heading = (
            metadata.get("file_heading")
            or "Untitled Document"
        )

        timeline_items = parse_timeline_json(
            metadata.get("timeline_json")
        )

        for index, item in enumerate(
            timeline_items
        ):
            event_date = parse_dd_mm_yyyy(
                str(
                    item.get("date")
                    or ""
                )
            )

            if not event_date:
                continue

            event_text = (
                str(
                    item.get("event")
                    or ""
                ).strip()
                or "Important date"
            )

            events.append(
                {
                    "id": f"{file_id}-{index}",
                    "file_id": file_id,
                    "file_heading": file_heading,
                    "date": event_date.isoformat(),
                    "display_date": item.get("date"),
                    "title": event_text,
                    "time": "All Day",
                    "category": "Document",
                    "priority": event_priority(
                        event_text
                    ),
                    "completed": False,
                }
            )

    events.sort(
        key=lambda event:
            event["date"]
    )

    return {
        "events": events
    }
