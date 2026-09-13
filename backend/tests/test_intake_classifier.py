"""Tests for the deterministic intake classifier."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from gatekeeper import classify
from gatekeeper.classifier import ClassificationResult


def _doc(filename, subject="", sender="", intent=None):
    return {
        "filename": filename,
        "file_type": "application/pdf",
        "provenance": {
            "sender": sender,
            "subject": subject,
            "email_intent": intent,
        },
    }


class TestInvoiceClassification:
    def test_vendor_invoice_by_text(self):
        text = (
            "VENDOR INVOICE\nTax Invoice No. INV-2024-1\n"
            "Amount payable: Rs 12,000\nDue date: 30 days\n"
            "GSTIN: 32ABCDE1234F1Z5"
        )
        result = classify(_doc("invoice2024.pdf", subject="Invoice"), text=text)
        assert isinstance(result, ClassificationResult)
        assert result.category == "invoice"
        assert result.confidence >= 0.8

    def test_invoice_with_bank_details_is_still_an_invoice(self):
        text = (
            "Tax Invoice INV-0099\nVendor: Acme Supplies\n"
            "Amount payable: Rs 40,000\nDue date: 15/06/2026\n"
            "Our bank: SBI IFSC SBIN0001234 A/c 999988887777\n"
            "GSTIN: 29AABCC1234B1ZD"
        )
        result = classify(_doc("invoice0099.pdf", subject="Tax Invoice"), text=text)
        assert result.category == "invoice"
        markers = [
            signal["category"]
            for signal in result.signals
            if signal.get("type") == "sensitive"
        ]
        assert "ifsc" in markers or "account_number" in markers
        assert not hasattr(result, "decision")  # classifier carries no decision

    def test_invoice_by_filename_only(self):
        result = classify(_doc("Invoice-0042-vendor.pdf"))
        assert result.category == "invoice"
        assert result.confidence >= 0.5


class TestBankStatementClassification:
    def test_bank_statement_by_text(self):
        text = (
            "Axis Bank\nAccount Statement for Feb 2026\n"
            "IFSC UTIB0001234\nMICR 400211123\n"
            "Opening balance 1000.00\nClosing balance 45000.00"
        )
        result = classify(_doc("statement-feb.pdf", subject="Account statement"), text=text)
        assert result.category == "bank_statement"
        assert result.confidence >= 0.8

    def test_filename_hint(self):
        result = classify(_doc("bank-statement-q1.pdf"))
        assert result.category == "bank_statement"


class TestOtherCategories:
    def test_salary_slip(self):
        text = (
            "SALARY SLIP - Feb 2026\nEmployee: Anu Das\n"
            "Gross pay: 85000\nNet pay: 72340\nDearness allowance: 12000"
        )
        result = classify(_doc("salary-feb2026.pdf", subject="Payslip"), text=text)
        assert result.category == "salary_slip"

    def test_resume(self):
        text = (
            "CURRICULUM VITAE\nName: Ravi Kumar\nWork experience\n"
            "Academic qualifications\nSkills and certifications"
        )
        result = classify(_doc("resume-ravi.pdf", subject="Job application"), text=text)
        assert result.category == "resume"

    def test_contract(self):
        text = (
            "SERVICE AGREEMENT dated 1 March 2026 between KMRL and Acme.\n"
            "Terms and conditions. Termination clause. Force majeure. "
            "Entire agreement."
        )
        result = classify(_doc("agreement-2026.pdf", subject="Contract"), text=text)
        assert result.category == "contract"


class TestAmbiguity:
    def test_other_when_no_signals(self):
        result = classify(_doc("misc-scanned-001.pdf"))
        assert result.category == "other"
        assert result.confidence < 0.5

    def test_sensitive_markers_never_force_category(self):
        text = "PAN ABCDE1234F and IFSC SBIN0001234 and account 123456789012"
        result = classify(_doc("random.txt"), text=text)
        assert result.category == "other"
        assert result.confidence < 0.5