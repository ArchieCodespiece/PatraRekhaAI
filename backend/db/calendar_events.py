"""
Calendar Events persistence module.
Supports Supabase table user_calendar_events with local JSON fallback.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from db.supabase_client import supabase

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
FALLBACK_FILE = DATA_DIR / "user_calendar_events.json"


def _ensure_fallback_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not FALLBACK_FILE.exists():
        FALLBACK_FILE.write_text(json.dumps({"custom_events": [], "overrides": {}}))


def _read_fallback() -> dict:
    _ensure_fallback_file()
    try:
        data = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"custom_events": [], "overrides": {}}
        return data
    except Exception:
        return {"custom_events": [], "overrides": {}}


def _write_fallback(data: dict):
    _ensure_fallback_file()
    FALLBACK_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_user_events_and_overrides(user_identifier: str) -> tuple[List[dict], Dict[str, dict]]:
    """
    Returns (custom_events_list, overrides_dict) for user.
    overrides_dict maps event_id -> {"completed": bool, "is_deleted": bool}
    """
    try:
        res = (
            supabase.table("user_calendar_events")
            .select("*")
            .eq("user_identifier", user_identifier)
            .execute()
        )
        records = res.data or []
        custom_events = []
        overrides = {}

        for rec in records:
            if rec.get("is_custom"):
                custom_events.append({
                    "id": rec["id"],
                    "date": rec.get("event_date"),
                    "title": rec.get("title"),
                    "time": rec.get("event_time", "All Day"),
                    "category": rec.get("category", "Meeting"),
                    "priority": rec.get("priority", "normal"),
                    "completed": bool(rec.get("completed", False)),
                    "fileHeading": None,
                    "is_custom": True,
                })
            else:
                overrides[rec["id"]] = {
                    "completed": bool(rec.get("completed", False)),
                    "is_deleted": bool(rec.get("is_deleted", False)),
                }

        return custom_events, overrides

    except Exception:
        data = _read_fallback()
        user_key = str(user_identifier)
        custom_events = [
            e for e in data.get("custom_events", [])
            if e.get("user_identifier") == user_key and not e.get("is_deleted")
        ]
        overrides = data.get("overrides", {}).get(user_key, {})
        return custom_events, overrides


def add_custom_event(user_identifier: str, event_data: dict) -> dict:
    event_id = event_data.get("id") or f"custom-{uuid.uuid4().hex[:8]}"
    record = {
        "id": event_id,
        "user_identifier": user_identifier,
        "event_date": str(event_data.get("date")),
        "title": str(event_data.get("title", "New Event")),
        "event_time": str(event_data.get("time", "All Day")),
        "category": str(event_data.get("category", "Meeting")),
        "priority": str(event_data.get("priority", "normal")),
        "completed": bool(event_data.get("completed", False)),
        "is_custom": True,
        "is_deleted": False,
    }

    try:
        supabase.table("user_calendar_events").upsert(record).execute()
    except Exception:
        data = _read_fallback()
        customs = data.get("custom_events", [])
        # Remove existing if any
        customs = [e for e in customs if e.get("id") != event_id]
        customs.append(record)
        data["custom_events"] = customs
        _write_fallback(data)

    return {
        "id": event_id,
        "date": record["event_date"],
        "title": record["title"],
        "time": record["event_time"],
        "category": record["category"],
        "priority": record["priority"],
        "completed": record["completed"],
        "fileHeading": None,
        "is_custom": True,
    }


def update_event_status(user_identifier: str, event_id: str, completed: Optional[bool] = None, is_deleted: Optional[bool] = None) -> dict:
    try:
        # Check if custom event in Supabase
        existing = (
            supabase.table("user_calendar_events")
            .select("*")
            .eq("id", event_id)
            .eq("user_identifier", user_identifier)
            .execute()
        )
        if existing.data:
            updates = {}
            if completed is not None:
                updates["completed"] = completed
            if is_deleted is not None:
                updates["is_deleted"] = is_deleted
            supabase.table("user_calendar_events").update(updates).eq("id", event_id).execute()
        else:
            # Create override row for document event
            row = {
                "id": event_id,
                "user_identifier": user_identifier,
                "is_custom": False,
                "completed": bool(completed) if completed is not None else False,
                "is_deleted": bool(is_deleted) if is_deleted is not None else False,
            }
            supabase.table("user_calendar_events").upsert(row).execute()

    except Exception:
        data = _read_fallback()
        user_key = str(user_identifier)
        
        # Check if in custom_events
        found_custom = False
        for c in data.get("custom_events", []):
            if c.get("id") == event_id and c.get("user_identifier") == user_key:
                found_custom = True
                if completed is not None:
                    c["completed"] = completed
                if is_deleted is not None:
                    c["is_deleted"] = is_deleted
                break
        
        if not found_custom:
            if "overrides" not in data:
                data["overrides"] = {}
            if user_key not in data["overrides"]:
                data["overrides"][user_key] = {}
            
            cur = data["overrides"][user_key].get(event_id, {"completed": False, "is_deleted": False})
            if completed is not None:
                cur["completed"] = completed
            if is_deleted is not None:
                cur["is_deleted"] = is_deleted
            data["overrides"][user_key][event_id] = cur

        _write_fallback(data)

    return {"id": event_id, "completed": completed, "is_deleted": is_deleted}
