"""Document category catalog and classification signal registry.

This module is pure configuration DATA for the intake gatekeeper:

* ``DEFAULT_CATEGORIES`` — supplier of document categories that policies
  (``allowed_categories`` / ``blocked_categories`` / ``review_categories``)
  reference.  Companies are NOT forced into these; they are sensible
  defaults an administrator can extend by editing a policy directly.
* ``SIGNAL_PATTERNS`` — deterministic keyword/regex signals mapped to
  categories.  These seed the cheap classifier only; the LLM path is
  optional and gated.
* ``SENSITIVE_MARKERS`` — regexes that detect sensitive markers such as
  PAN / IFSC / account numbers.  Detecting a sensitive marker NEVER blocks
  a document by itself: the marker is recorded as a signal and the
  workspace policy decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ============================================================================
# Document categories
# ============================================================================

DEFAULT_CATEGORIES = (
    "bank_statement",
    "identity_document",
    "salary_slip",
    "tax_document",
    "invoice",
    "contract",
    "legal_notice",
    "purchase_order",
    "quotation",
    "resume",
    "policy",
    "technical_document",
    "other",
)

CATEGORY_LABELS = {
    "bank_statement": "Bank statement",
    "identity_document": "Identity document",
    "salary_slip": "Salary slip",
    "tax_document": "Tax document",
    "invoice": "Invoice",
    "contract": "Contract",
    "legal_notice": "Legal notice",
    "purchase_order": "Purchase order",
    "quotation": "Quotation",
    "resume": "Resume",
    "policy": "Policy",
    "technical_document": "Technical document",
    "other": "Other",
}


# ============================================================================
# Signal registry
# ============================================================================

@dataclass(frozen=True)
class SignalDefinition:
    category: str
    patterns: tuple[str, ...]
    weight: float = 1.0


SIGNAL_PATTERNS: tuple[SignalDefinition, ...] = (
    SignalDefinition(
        "invoice",
        (
            r"tax invoice",
            r"\binvoice\b",
            r"\bbill no\.?\b",
            r"gstin?",
            r"credit note",
            r"debit note",
            r"amount payable",
            r"due date",
            r"vendor invoice",
        ),
        weight=2.0,
    ),
    SignalDefinition(
        "bank_statement",
        (
            r"bank statement",
            r"statement of account",
            r"account statement",
            r"e-?statement",
            r"mini statement",
            r"micr",
            r"closing balance",
            r"opening balance",
            r"rnbc",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "identity_document",
        (
            r"aadhaar",
            r"\baadhar\b",
            r"pan card",
            r"\bpassport\b",
            r"driving licence",
            r"driver'?s license",
            r"voter id",
            r"election commission",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "salary_slip",
        (
            r"salary slip",
            r"salary statement",
            r"pay ?slip",
            r"paystub",
            r"pay stub",
            r"payslip",
            r"earnings statement",
            r"net pay",
            r"gross pay",
            r"dearness allowance",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "tax_document",
        (
            r"income tax",
            r"tax return",
            r"\btds\b",
            r"form 16",
            r"gst return",
            r"tax invoice",
            r"deduction at source",
            r"tax deducted",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "contract",
        (
            r"\bcontract\b",
            r"\bagreement\b",
            r"\bnda\b",
            r"non[- ]disclosure",
            r"terms and conditions",
            r"witnesseth",
            r"\bindemnity\b",
            r"termination clause",
            r"force majeure",
            r"entire agreement",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "legal_notice",
        (
            r"legal notice",
            r"notice of legal",
            r"lawyer'?s notice",
            r"advocate notice",
            r"legal action",
            r"court summons",
            r"arbitration notice",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "purchase_order",
        (
            r"purchase order",
            r"\bpo number\b",
            r"\bpo no\.?\b",
            r"order reference",
            r"delivery schedule",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "quotation",
        (
            r"quotation",
            r"\bquote\b",
            r"price estimate",
            r"cost estimate",
            r"proposal",
            r"rate card",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "resume",
        (
            r"curriculum vitae",
            r"\bcv\b",
            r"resume",
            r"job application",
            r"work experience",
            r"academic qualifications",
        ),
        weight=1.5,
    ),
    SignalDefinition(
        "policy",
        (
            r"\bpolicy\b",
            r"standard operating procedure",
            r"\bsop\b",
            r"guideline",
            r"\bmanual\b",
            r"code of conduct",
            r"hr policy",
        ),
        weight=1.0,
    ),
    SignalDefinition(
        "technical_document",
        (
            r"technical specification",
            r"design document",
            r"engineering drawing",
            r"\bspec\b",
            r"architecture",
            r"api reference",
            r"installation guide",
            r"user manual",
            r"maintenance manual",
        ),
        weight=1.0,
    ),
)


# Document-type hints usually found only in filenames.
FILENAME_HINTS = {
    "invoice": (
        r"invoice",
        r"bill",
        r"receipt",
    ),
    "bank_statement": (
        r"statement",
        r"bank",
    ),
    "salary_slip": (
        r"salary",
        r"pay ?slip",
        r"payslip",
        r"paystub",
    ),
    "identity_document": (
        r"aadhaar",
        r"\bpan\b",
        r"passport",
        r"\baadhar\b",
    ),
    "tax_document": (
        r"(?:income|gst).?tax",
        r"tax return",
        r"form[ _-]?16",
    ),
    "contract": (
        r"contract",
        r"agreement",
        r"\bnda\b",
    ),
    "resume": (
        r"resume",
        r"\bcv\b",
        r"curriculum",
    ),
    "purchase_order": (
        r"purchase[ _-]?order",
        r"\bpo\b",
    ),
    "quotation": (
        r"quot",
        r"estimate",
    ),
    "policy": (
        r"policy",
        r"\bsop\b",
        r"manual",
    ),
    "legal_notice": (
        r"legal[ _-]?notice",
        r"notice",
    ),
}


# ============================================================================
# Sensitive markers
#
# Detected markers are recorded as signals for the audit trail.  They are
# NEVER used to block a document straight away — classification + workspace
# policy decides.  An invoice or contract can legitimately contain a PAN or
# account number.
# ============================================================================

SENSITIVE_MARKERS = (
    # Indian PAN (AAAAA0000A)
    re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    # Indian IFSC (4 alpha + 7 digits)
    re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    # GSTIN (15 chars: 2/1/2/4/3/2/1/1)
    re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z]{1}[A-Z\d]{1}\b"),
    # Account numbers: 9-18 consecutive digits, optionally dashed.
    re.compile(r"\b\d{9,18}\b"),
    # Aadhaar style 12-digit numbers.
    re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"),
)


def signal_for_category(category: str) -> SignalDefinition | None:
    for signal in SIGNAL_PATTERNS:
        if signal.category == category:
            return signal
    return None


def compile_signal_patterns(category: str) -> list[re.Pattern]:
    signal = signal_for_category(category)
    if not signal:
        return []
    return [re.compile(p, re.IGNORECASE) for p in signal.patterns]


def compile_all_signal_patterns() -> dict[str, list[re.Pattern]]:
    return {
        signal.category: [
            re.compile(pattern, re.IGNORECASE)
            for pattern in signal.patterns
        ]
        for signal in SIGNAL_PATTERNS
    }


def compile_filename_hints() -> dict[str, list[re.Pattern]]:
    return {
        category: [
            re.compile(pattern, re.IGNORECASE)
            for pattern in patterns
        ]
        for category, patterns in FILENAME_HINTS.items()
    }