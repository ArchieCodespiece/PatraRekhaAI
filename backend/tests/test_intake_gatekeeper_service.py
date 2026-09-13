"""Tests for the webhook-facing intake gatekeeper service.

The Supabase-backed lookups are mocked so these run fully offline.  The
service is exercised with documents shaped like those produced by the
Gmail poller and by the webhook payload normalizer to prove a SINGLE
gatekeeper serves every source.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from gatekeeper import service


# ============================================================================
# Fixtures / helpers
# ============================================================================

def _enabled_policy(workspace_id, allowed=(), blocked=(), review=(), version=1):
    return {
        "workspace_id": workspace_id,
        "name": "Test policy",
        "allowed_categories": list(allowed),
        "blocked_categories": list(blocked),
        "review_categories": list(review),
        "sender_rules": [],
        "keyword_rules": [],
        "min_confidence": 0,
        "default_decision": "REVIEW",
        "enabled": True,
        "policy_version": version,
    }


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Keep every DB/network touchpoint offline for the service tests."""
    monkeypatch.setattr(
        service,
        "get_policy_for_workspace",
        lambda workspace_id: None,
    )
    monkeypatch.setattr(
        service,
        "get_override_for_file",
        lambda file_id: None,
    )
    monkeypatch.setattr(
        service,
        "record_decision",
        lambda **kwargs: {"id": "fake-id"},
    )
    # Never run heavy pdf extraction in unit tests.
    monkeypatch.setattr(service, "extract_text", lambda filename, content: "")


def _poller_document():
    """Shape produced by the Gmail poller path (files record + provenance)."""
    return {
        "file_id": "11111111-1111-1111-1111-111111111111",
        "filename": "INV-2026-0042-acme.pdf",
        "file_type": "application/pdf",
        "content_hash": "abc",
        "owner_email": "owner@company.com",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "source_email_id": "msg-1",
        "source_sender": "billing@acme.com",
        "source_subject": "Tax Invoice INV-2026-0042",
        "email_intent": "INFORMATIONAL",
    }


def _webhook_document():
    """Shape produced by the Supabase webhook payload normalizer."""
    return {
        "file_id": "11111111-1111-1111-1111-111111111111",
        "filename": "INV-2026-0042-acme.pdf",
        "file_url": "https://supabase/file_storage/documents/...",
        "file_type": "application/pdf",
        "owner_email": "owner@company.com",
        "user_id": "00000000-0000-0000-0000-000000000000",
        "source_sender": "billing@acme.com",
        "source_subject": "Tax Invoice INV-2026-0042",
        "email_intent": "INFORMATIONAL",
    }


class TestPreservesExistingBehavior:
    def test_no_policy_allows_without_audit(self, _offline):
        decisions = []
        service.record_decision = lambda **kwargs: decisions.append(kwargs)

        result = service.evaluate_intake(_poller_document(), b"pdf-bytes")

        assert result["decision"] == "ALLOW"
        assert "preserved" in result["reason"]
        assert decisions == []

    def test_no_policy_allows_for_poller_and_webhook(self, _offline):
        poller = service.evaluate_intake(_poller_document(), b"bytes")
        webhook = service.evaluate_intake(_webhook_document(), b"bytes")
        assert poller["decision"] == "ALLOW"
        assert webhook["decision"] == "ALLOW"

    def test_missing_record_fails_open(self, _offline):
        result = service.evaluate_intake(None)
        assert result["decision"] == "ALLOW"


class TestPolicyRoutingThroughService:
    def test_allowed_invoice_ingest(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_policy_for_workspace",
            lambda workspace_id: _enabled_policy(
                workspace_id,
                allowed=("invoice",),
            ),
        )
        records = []
        monkeypatch.setattr(
            service,
            "record_decision",
            lambda **kwargs: records.append(kwargs),
        )

        result = service.evaluate_intake(_poller_document(), b"bytes")

        assert result["decision"] == "ALLOW"
        assert result["category"] == "invoice"
        assert result["policy_version"] == 1
        assert records, "audit record expected while policy is active"

    def test_blocked_bank_statement_quarantined(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_policy_for_workspace",
            lambda workspace_id: _enabled_policy(
                workspace_id,
                blocked=("bank_statement",),
            ),
        )
        monkeypatch.setattr(
            service,
            "extract_text",
            lambda filename, content: (
                "HDFC BANK ACCOUNT STATEMENT IFSC HDFC0001234 "
                "closing balance 45000"
            ),
        )

        document = dict(_webhook_document())
        document["filename"] = "acct-statement-2026.pdf"

        result = service.evaluate_intake(document, b"bytes")

        assert result["decision"] == "BLOCK"
        assert result["category"] == "bank_statement"

    def test_ambiguous_document_reviewed(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_policy_for_workspace",
            lambda workspace_id: _enabled_policy(workspace_id),
        )

        result = service.evaluate_intake(
            {
                **_poller_document(),
                "filename": "scan-001.pdf",
                "source_subject": "",
                "source_sender": "",
            },
            b"bytes",
        )

        assert result["decision"] == "REVIEW"
        assert result["category"] == "other"


class TestFailOpenAndOverrides:
    def test_policy_lookup_error_falls_back_to_allow(self, _offline, monkeypatch):
        def boom(workspace_id):
            raise RuntimeError("supabase down")

        monkeypatch.setattr(service, "get_policy_for_workspace", boom)

        result = service.evaluate_intake(_poller_document(), b"bytes")

        assert result["decision"] == "ALLOW"

    def test_manual_override_allow_releases_blocked(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_policy_for_workspace",
            lambda workspace_id: _enabled_policy(
                workspace_id,
                blocked=("bank_statement",),
            ),
        )
        monkeypatch.setattr(
            service,
            "get_override_for_file",
            lambda file_id: {"decision": "ALLOW", "reason": "Manual override (ALLOW)"},
        )

        result = service.evaluate_intake(_webhook_document(), b"bytes")

        assert result["decision"] == "ALLOW"
        assert result["overridden"] is True

    def test_manual_override_block_holds(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_policy_for_workspace",
            lambda workspace_id: _enabled_policy(workspace_id, allowed=("invoice",)),
        )
        monkeypatch.setattr(
            service,
            "get_override_for_file",
            lambda file_id: {"decision": "BLOCK", "reason": "Manual override (BLOCK)"},
        )

        result = service.evaluate_intake(_poller_document(), b"bytes")

        assert result["decision"] == "BLOCK"
        assert result["overridden"] is True

    def test_override_alone_allows_when_no_policy(self, _offline, monkeypatch):
        monkeypatch.setattr(
            service,
            "get_override_for_file",
            lambda file_id: {"decision": "ALLOW", "reason": "Manual override (ALLOW)"},
        )

        result = service.evaluate_intake(_webhook_document(), b"bytes")

        assert result["decision"] == "ALLOW"
        assert result["overridden"] is True


class TestWorkspaceResolution:
    def test_uses_user_id_then_owner_email_then_default(self, _offline):
        assert (
            service.resolve_workspace_id(
                {"user_id": "u-1", "owner_email": "a@b.com"}
            )
            == "u-1"
        )
        assert (
            service.resolve_workspace_id(
                {"owner_email": "A@B.com"}
            )
            == "a@b.com"
        )
        assert service.resolve_workspace_id({}) == "default"