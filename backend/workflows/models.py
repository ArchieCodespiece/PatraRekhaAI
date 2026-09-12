"""
Canonical, versioned result models for the workflow layer.

These objects are the single source of truth that every output format
(chat markdown, PDF, XLSX, future interactive UI) renders from. Bump the
``schema_version`` whenever the shape changes so down-stream renderers
can migrate explicitly.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

COMPARISON_SCHEMA_VERSION = "1.0"
REPORT_SCHEMA_VERSION = "1.0"

Impact = Literal["low", "medium", "high", "unknown"]
Confidence = Literal["high", "medium", "low"]


# ============================================================================
# COMPARISON RESULT
# ============================================================================

class Evidence(BaseModel):
    """A retrievable snippet backing a single comparison claim."""

    document: str = Field(..., description="Human-readable document name")
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    text: str = ""
    strategy: str = "semantic"


class ComparisonRow(BaseModel):
    topic: str
    document_a: str = ""
    document_b: str = ""
    difference: bool = False
    confidence: Confidence = "medium"
    impact: Impact = "unknown"
    evidence: List[Evidence] = Field(default_factory=list)
    unverified: bool = False


class ComparisonSection(BaseModel):
    name: str
    rows: List[ComparisonRow] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    schema_version: str = COMPARISON_SCHEMA_VERSION
    documents: List[str] = Field(default_factory=list)
    intent: str = "compare"
    sections: List[ComparisonSection] = Field(default_factory=list)

    def total_rows(self) -> int:
        return sum(len(section.rows) for section in self.sections)

    def differences(self) -> List[ComparisonRow]:
        return [
            row
            for section in self.sections
            for row in section.rows
            if row.difference
        ]

    def high_impact_differences(self) -> List[ComparisonRow]:
        return [
            row
            for row in self.differences()
            if row.impact == "high"
        ]

    def unverified_rows(self) -> List[ComparisonRow]:
        return [
            row
            for section in self.sections
            for row in section.rows
            if row.unverified
        ]

    def collect_evidence(self) -> List[Evidence]:
        seen = set()
        evidence = []

        for section in self.sections:
            for row in section.rows:
                for item in row.evidence:
                    key = (
                        item.document,
                        item.page_start,
                        item.text[:200],
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    evidence.append(item)

        return evidence


# ============================================================================
# REPORT RESULT (direct report / extraction export)
# ============================================================================

class ReportTable(BaseModel):
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class ReportSection(BaseModel):
    heading: str
    content: str = ""
    table: Optional[ReportTable] = None


class ReportDocument(BaseModel):
    schema_version: str = REPORT_SCHEMA_VERSION
    title: str
    sections: List[ReportSection] = Field(default_factory=list)

    def collect_evidence(self) -> List[Evidence]:
        return []


# ============================================================================
# CITATION HELPER
# ============================================================================

def citations_from_evidence(
    evidence_items: List[Evidence],
    file_id_by_document: dict,
) -> List[dict]:
    """
    Convert a flat list of Evidence into the chat response citation shape
    used by ``api.chat`` (document_name, file_id, page, section, text).
    """

    citations: List[dict] = []
    seen_texts = set()

    for item in evidence_items:
        text = str(item.text or "").strip()

        if not text or text in seen_texts:
            continue

        seen_texts.add(text)

        citations.append(
            {
                "document_name": item.document,
                "file_id": file_id_by_document.get(
                    item.document,
                    "",
                ),
                "page_start": item.page_start,
                "page_end": item.page_end,
                "section": item.section,
                "text": text,
                "score": 1.0,
            }
        )

    return citations