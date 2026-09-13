"""Supabase helpers for document intake gatekeeper policies.

Table: intake_policies
Brief:
    Per-workspace configuration controlling how incoming documents are
    classified and routed (ALLOW / REVIEW / BLOCK) before they enter the
    RAG pipeline.

Workspace resolution:
    workspace_id = document user_id -> owner_email -> reserved 'default'.
    A policy only takes effect when ``enabled`` is true.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from postgrest.exceptions import APIError

from db.supabase_client import supabase


TABLE = "intake_policies"

SELECT_COLUMNS = (
    "id,"
    "workspace_id,"
    "name,"
    "allowed_categories,"
    "blocked_categories,"
    "review_categories,"
    "sender_rules,"
    "keyword_rules,"
    "min_confidence,"
    "default_decision,"
    "enabled,"
    "policy_version,"
    "created_at,"
    "updated_at"
)


# Reserved workspace key used for a global fallback policy.
DEFAULT_WORKSPACE = "default"


def _today() -> datetime:
    return datetime.now(timezone.utc)


def normalize_policy_row(row: dict | None) -> dict | None:
    """Normalize a raw policy row into the dict the gatekeeper engine uses."""
    if not row:
        return None

    return {
        "id": str(row.get("id") or ""),
        "workspace_id": row.get("workspace_id"),
        "name": row.get("name") or "Intake policy",
        "allowed_categories": list(row.get("allowed_categories") or []),
        "blocked_categories": list(row.get("blocked_categories") or []),
        "review_categories": list(row.get("review_categories") or []),
        "sender_rules": row.get("sender_rules") or [],
        "keyword_rules": row.get("keyword_rules") or [],
        "min_confidence": float(row.get("min_confidence") or 0),
        "default_decision": row.get("default_decision") or "REVIEW",
        "enabled": bool(row.get("enabled", False)),
        "policy_version": int(row.get("policy_version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_policy_for_workspace(workspace_id: str | None) -> dict | None:
    """
    Return the enabled (or existing) policy for a workspace.

    Lookup order:
        1. exact enabled policy for the workspace
        2. enabled 'default' policy
        3. exact existing (disabled) policy (so admins see config to enable)
        4. 'default' existing policy

    A disabled policy is returned with ``enabled=False`` so callers can
    fall back to ALLOW (existing behavior) while still honoring an explicit
    admin override recorded on the audit row.
    """

    candidates = [workspace_id, DEFAULT_WORKSPACE]

    for key in candidates:
        if not key:
            continue
        try:
            response = (
                supabase.table(TABLE)
                .select(SELECT_COLUMNS)
                .eq("workspace_id", key)
                .limit(1)
                .execute()
            )
            if response.data:
                return normalize_policy_row(response.data[0])
        except APIError:
            return None

    return None


def list_policies(workspace_ids: list[str] | None = None) -> list[dict]:
    """List policies, optionally restricted to the given workspace ids."""
    try:
        query = supabase.table(TABLE).select(SELECT_COLUMNS).order("updated_at", desc=True)
        if workspace_ids:
            query = query.in_("workspace_id", [w for w in workspace_ids if w])
        response = query.execute()
        return [normalize_policy_row(row) for row in (response.data or [])]
    except APIError:
        return []


def upsert_policy(
    workspace_id: str,
    name: str | None = None,
    allowed_categories: list[str] | None = None,
    blocked_categories: list[str] | None = None,
    review_categories: list[str] | None = None,
    sender_rules: list[dict] | None = None,
    keyword_rules: list[dict] | None = None,
    min_confidence: float | None = None,
    default_decision: str | None = None,
    enabled: bool | None = None,
) -> dict | None:
    """
    Create or replace the policy for a workspace.

    Upserting bumps ``policy_version`` instead of inserting a second row,
    keeping exactly one policy per workspace (see the table's unique
    constraint on workspace_id).
    """

    if not workspace_id:
        raise ValueError("workspace_id is required for an intake policy.")

    workspace_id = workspace_id.strip()

    existing = get_policy_for_workspace(workspace_id)

    row: dict = {"workspace_id": workspace_id}

    if name is not None:
        row["name"] = name.strip() or "Intake policy"

    if allowed_categories is not None:
        row["allowed_categories"] = [str(c) for c in allowed_categories]
    if blocked_categories is not None:
        row["blocked_categories"] = [str(c) for c in blocked_categories]
    if review_categories is not None:
        row["review_categories"] = [str(c) for c in review_categories]

    if sender_rules is not None:
        row["sender_rules"] = _normalize_json_rules(sender_rules, "sender")
    if keyword_rules is not None:
        row["keyword_rules"] = _normalize_json_rules(keyword_rules, "keyword")

    if min_confidence is not None:
        try:
            row["min_confidence"] = float(min_confidence)
        except (TypeError, ValueError):
            row["min_confidence"] = 0

    if default_decision is not None:
        decision = str(default_decision).strip().upper()
        if decision not in {"ALLOW", "REVIEW", "BLOCK"}:
            raise ValueError(
                "default_decision must be ALLOW, REVIEW or BLOCK."
            )
        row["default_decision"] = decision

    if enabled is not None:
        row["enabled"] = bool(enabled)

    if row:
        row["updated_at"] = _today().isoformat()
        row["policy_version"] = (
            int(existing.get("policy_version") or 1) + 1
            if existing
            else 1
        )

    try:

        response = (
            supabase.table(TABLE)
            .upsert(row, on_conflict="workspace_id")
            .execute()
        )

    except APIError as exc:

        # Fall back to separate insert / update. Some deployments gate
        # upsert-on-conflict the way others do not.
        if existing:
            response = (
                supabase.table(TABLE)
                .update(row)
                .eq("workspace_id", workspace_id)
                .execute()
            )
        else:
            if "name" not in row:
                row["name"] = "Intake policy"
            if "default_decision" not in row:
                row["default_decision"] = "REVIEW"
            row["enabled"] = bool(row.get("enabled", False))
            row["policy_version"] = int(row.get("policy_version") or 1)
            response = (
                supabase.table(TABLE)
                .insert(row)
                .execute()
            )

    return (
        normalize_policy_row(response.data[0])
        if response and response.data
        else None
    )


def delete_policy(workspace_id: str) -> dict | None:
    """Delete the policy for a workspace (idempotent)."""
    try:
        response = (
            supabase.table(TABLE)
            .delete()
            .eq("workspace_id", workspace_id)
            .execute()
        )
        return response.data[0] if response.data else None
    except APIError:
        return None


def _normalize_json_rules(rules, kind: str) -> list[dict]:
    """Validate and normalize sender/keyword rule dicts."""
    normalized = []
    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        match = str(rule.get("match") or "").strip().lower()
        value = str(rule.get("value") or "").strip()
        action = str(rule.get("action") or "").strip().lower()

        if not value:
            continue
        if action not in {"allow", "block"}:
            action = "block"

        entry = {
            "match": match if match in {"domain", "email", "regex"} else "regex",
            "value": value,
            "action": action,
        }
        normalized.append(entry)

    # Deterministic serialization for stable row comparison.
    try:
        json.dumps(normalized)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid {kind} rules: rules must be JSON-serializable."
        ) from exc

    return normalized