"""Tests for the pure intake policy decision engine.

These run fully offline: they compose classification results + hand-built
policies, and assert ALLOW / REVIEW / BLOCK routing for different corporate
workspaces.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from gatekeeper import (
    DECISION_ALLOW,
    DECISION_REVIEW,
    DECISION_BLOCK,
    evaluate,
    evaluate_classification,
)
from gatekeeper.classifier import ClassificationResult


def _policy(
    workspace_id="default",
    name="Policy",
    allowed=(),
    blocked=(),
    review=(),
    sender_rules=(),
    keyword_rules=(),
    min_confidence=0,
    default_decision="REVIEW",
    enabled=True,
    policy_version=1,
):
    return {
        "workspace_id": workspace_id,
        "name": name,
        "allowed_categories": list(allowed),
        "blocked_categories": list(blocked),
        "review_categories": list(review),
        "sender_rules": list(sender_rules),
        "keyword_rules": list(keyword_rules),
        "min_confidence": min_confidence,
        "default_decision": default_decision,
        "enabled": enabled,
        "policy_version": policy_version,
    }


def _classification(category="other", confidence=0.9, signals=None):
    return ClassificationResult(
        category=category,
        confidence=confidence,
        signals=signals or [],
        reason=f"Matched {category}",
    )


LEGAL = _policy(
    "legal",
    "Legal",
    allowed=("contract", "legal_notice", "purchase_order", "policy"),
    blocked=("bank_statement", "identity_document"),
    review=("tax_document", "salary_slip"),
    policy_version=3,
)

FINANCE = _policy(
    "finance",
    "Finance",
    allowed=("invoice", "purchase_order", "tax_document", "bank_statement", "quotation"),
    blocked=("identity_document", "resume"),
)

HR = _policy(
    "hr",
    "HR",
    allowed=("resume", "salary_slip", "policy", "identity_document"),
    blocked=("invoice", "bank_statement", "tax_document"),
    review=("contract", "technical_document"),
)

PROCUREMENT = _policy(
    "procurement",
    "Procurement",
    allowed=("contract", "quotation", "purchase_order", "invoice", "legal_notice"),
    blocked=("identity_document",),
)


class TestNoPolicyPreservesBehavior:
    def test_no_policy_allows(self):
        result = evaluate({"filename": "any.pdf"}, None)
        assert result.decision == DECISION_ALLOW
        assert "preserved" in result.reason

    def test_disabled_policy_allows(self):
        disabled = dict(LEGAL, enabled=False)
        result = evaluate({"filename": "any.pdf"}, disabled)
        assert result.decision == DECISION_ALLOW
        assert result.policy_version == disabled["policy_version"]


class TestDepartmentalRouting:
    def test_legal_allows_contracts(self):
        result = evaluate({"filename": "contract.pdf"}, LEGAL)
        assert result.decision == DECISION_ALLOW

    def test_legal_blocks_bank_statement(self):
        result = evaluate({"filename": "statement.pdf"}, LEGAL, text="bank statement")
        assert result.decision == DECISION_BLOCK

    def test_legal_blocks_identity_document(self):
        result = evaluate({"filename": "pan-card.jpg.pdf"}, LEGAL, text="pan card aadhaar")
        assert result.decision == DECISION_BLOCK

    def test_legal_reviews_salary_slip(self):
        result = evaluate({"filename": "salary.pdf"}, LEGAL, text="salary slip")
        assert result.decision == DECISION_REVIEW

    def test_finance_allows_invoice(self):
        result = evaluate({"filename": "invoice.pdf"}, FINANCE)
        assert result.decision == DECISION_ALLOW

    def test_finance_allows_bank_statement(self):
        result = evaluate({"filename": "statement.pdf"}, FINANCE, text="bank statement")
        assert result.decision == DECISION_ALLOW

    def test_hr_blocks_unrelated_invoice(self):
        result = evaluate({"filename": "invoice.pdf"}, HR)
        assert result.decision == DECISION_BLOCK

    def test_hr_allows_resume(self):
        result = evaluate({"filename": "resume.pdf"}, HR)
        assert result.decision == DECISION_ALLOW

    def test_procurement_allows_quotation(self):
        result = evaluate({"filename": "quotation.pdf"}, PROCUREMENT)
        assert result.decision == DECISION_ALLOW


class TestSensitiveDocumentsArePolicyRouted:
    def test_invoice_with_bank_details_allowed_when_policy_allows_invoices(self):
        """Bank account/PAN/IFSC inside an invoice must NOT auto-block."""

        text = (
            "Tax Invoice INV-0099 - Acme Supplies\nAmount payable 40000\n"
            "IFSC SBIN0001234 Account 999988887777 PAN ABCDE1234F"
        )
        result = evaluate(
            {"filename": "invoice0099.pdf", "provenance": {"subject": "Invoice"}},
            FINANCE,
            text=text,
        )
        assert result.decision == DECISION_ALLOW
        assert result.category == "invoice"

    def test_actual_bank_statement_blocked_when_policy_blocks_it(self):
        text = (
            "HDFC Bank Account Statement\nIFSC HDFC0001234\n"
            "Opening balance 1000 Closing balance 45000"
        )
        result = evaluate(
            {"filename": "statement-mar-2026.pdf", "provenance": {"subject": "Statement"}},
            LEGAL,
            text=text,
        )
        assert result.decision == DECISION_BLOCK
        assert result.category == "bank_statement"


class TestReviewOnAmbiguity:
    def test_unknown_category_defaults_to_review(self):
        result = evaluate({"filename": "random-001.pdf"}, LEGAL)
        assert result.decision == DECISION_REVIEW

    def test_confidence_below_threshold_reviews(self):
        low = classify_with_confidence(0.3)
        policy = _policy(default_decision="ALLOW", min_confidence=0.8)
        result = evaluate_classification(low, {"filename": "x.pdf"}, policy)
        assert result.decision == DECISION_REVIEW


class TestRuleOverrides:
    def test_sender_domain_rule_blocks(self):
        policy = _policy(
            allowed=("invoice",),
            sender_rules=[
                {"match": "domain", "value": "vendor-suspicious.com", "action": "block"}
            ],
        )
        document = {
            "filename": "invoice.pdf",
            "provenance": {"sender": "sale@vendor-suspicious.com"},
        }
        result = evaluate(document, policy, text="invoice")
        assert result.decision == DECISION_BLOCK

    def test_sender_email_rule_allows(self):
        policy = _policy(
            allowed=(),
            default_decision="BLOCK",
            sender_rules=[
                {"match": "email", "value": "trusted@court.gov", "action": "allow"}
            ],
        )
        document = {
            "filename": "notice.pdf",
            "provenance": {"sender": "Trusted@court.gov"},
        }
        result = evaluate(document, policy)
        assert result.decision == DECISION_ALLOW

    def test_keyword_rule_blocks(self):
        policy = _policy(
            allowed=("contract",),
            keyword_rules=[
                {"match": "regex", "value": r"\bsecret\b", "action": "block"}
            ],
        )
        result = evaluate(
            {"filename": "contract.pdf"},
            policy,
            text="This contract contains secret pricing schedules",
        )
        assert result.decision == DECISION_BLOCK


class TestManualOverride:
    def test_override_allow_releases_blocked(self):
        result = evaluate(
            {"filename": "statement.pdf"},
            LEGAL,
            text="bank statement",
            override=DECISION_ALLOW,
        )
        assert result.decision == DECISION_ALLOW
        assert result.overridden is True

    def test_override_block_holds_allowed(self):
        result = evaluate(
            {"filename": "invoice.pdf"},
            FINANCE,
            override=DECISION_BLOCK,
        )
        assert result.decision == DECISION_BLOCK
        assert result.overridden is True


def classify_with_confidence(confidence):
    return ClassificationResult(
        category="other",
        confidence=confidence,
        signals=[],
        reason="ambiguous",
    )