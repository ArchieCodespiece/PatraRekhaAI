"""Supabase helpers for document intake decision audit / quarantine records.

Table: intake_decisions
Brief:
    Records every gatekeeper ALLOW/REVIEW/BLOCK decision, including a
    manual ``override_decision`` an admin can set to release (ALLOW) or
    keep (BLOCK) a quarantined document.

    Sensitive extracted content is never stored.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from postgrest.exceptions import APIError

from db.supabase_client import supabase


TABLE = "intake_decisions"

SELECT_COLUMNS = (
    "id,"
    "file_id,"
    "source_email_id,"
    "workspace_id,"
    "decision,"
    "category,"
    "confidence,"
    "signals,"
    "reason,"
    "policy_version,"
    "classifier,"
    "override_decision,"
    "created_at"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_file_id(file_id: str | None) -> str | None:
    if not file_id:
        return None
    try:
        return str(UUID(str(file_id)))
    except (ValueError, TypeError, AttributeError):
        return None


def record_decision(
    workspace_id: str | None,
    decision: str,
    category: str | None = None,
    confidence: float | None = None,
    signals: list | None = None,
    reason: str | None = None,
    policy_version: int | None = None,
    classifier: str | None = None,
    file_id: str | None = None,
    source_email_id: str | None = None,
    override_decision: str | None = None,
) -> dict | None:
    """
    Insert one gatekeeper audit record.  Fail-silent: audit problems must
    never break the ingestion flow.
    """

    decision = str(decision or "ALLOW").strip().upper()
    if decision not in {"ALLOW", "REVIEW", "BLOCK"}:
        decision = "ALLOW"

    row = {
        "workspace_id": workspace_id or "default",
        "decision": decision,
        "signals": signals or [],
        "created_at": _now(),
    }

    validated_file_id = _validate_file_id(file_id)
    if validated_file_id:
        row["file_id"] = validated_file_id

    if source_email_id is not None:
        row["source_email_id"] = source_email_id
    if category is not None:
        row["category"] = category
    if confidence is not None:
        try:
            row["confidence"] = float(confidence)
        except (TypeError, ValueError):
            pass
    if reason is not None:
        row["reason"] = reason
    if policy_version is not None:
        row["policy_version"] = policy_version
    if classifier is not None:
        row["classifier"] = classifier
    if override_decision is not None:
        normalized = str(override_decision).strip().upper()
        if normalized in {"ALLOW", "BLOCK"}:
            row["override_decision"] = normalized

    try:
        response = (
            supabase.table(TABLE)
            .insert(row)
            .execute()
        )
        return response.data[0] if response.data else None
    except APIError as exc:
        print(
            f"Warning: could not record intake decision "
            f"for {validated_file_id or 'unknown'}: {exc}"
        )
        return None


def get_override_for_file(file_id: str | None) -> dict | None:
    """
    Return the most recent manual override (ALLOW/BLOCK) for a document,
    or None when no override has been set.
    """
    validated_file_id = _validate_file_id(file_id)
    if not validated_file_id:
        return None

    try:
        response = (
            supabase.table(TABLE)
            .select(SELECT_COLUMNS)
            .eq("file_id", validated_file_id)
            .not_.is_("override_decision", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError:
        return None

    row = response.data[0] if response.data else None
    if not row:
        return None

    override = str(row.get("override_decision") or "").strip().upper()
    if override not in {"ALLOW", "BLOCK"}:
        return None

    return {
        "decision": override,
        "reason": f"Manual override ({override})",
        "policy_version": row.get("policy_version"),
        "created_at": row.get("created_at"),
    }


def set_override(file_id: str, decision: str, workspace_id: str | None) -> dict | None:
    """Set (or update) the manual override on the latest decision for a file."""
    validated_file_id = _validate_file_id(file_id)
    if not validated_file_id:
        return None

    normalized = str(decision or "").strip().upper()
    if normalized not in {"ALLOW", "BLOCK"}:
        raise ValueError("Override decision must be ALLOW or BLOCK.")

    try:
        response = (
            supabase.table(TABLE)
            .select("id")
            .eq("file_id", validated_file_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except APIError:
        return None

    if not response.data:
        # No prior decision row — create an audit row carrying the override.
        return record_decision(
            workspace_id=workspace_id,
            decision=normalized,
            file_id=validated_file_id,
            override_decision=normalized,
            reason=f"Manual override ({normalized}) without prior decision.",
        )

    row_id = response.data[0]["id"]

    try:
        update = (
            supabase.table(TABLE)
            .update({"override_decision": normalized})
            .eq("id", row_id)
            .execute()
        )
        return update.data[0] if update.data else None
    except APIError as exc:
        print(
            f"Warning: could not set intake override for "
            f"{validated_file_id}: {exc}"
        )
        return None


def list_decisions(
    workspace_id: str | None = None,
    decision: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """List decision audit rows, optionally filtered by workspace/decision."""
    try:
        query = supabase.table(TABLE).select(SELECT_COLUMNS)
        if workspace_id:
            query = query.eq("workspace_id", workspace_id)
        if decision:
            query = query.eq("decision", decision)
        response = (
            query.order("created_at", desc=True).limit(limit).execute()
        )
        return response.data or []
    except APIError:
        return []