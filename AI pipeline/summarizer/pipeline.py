"""
pipeline.py

Main orchestration pipeline for document summarization.

Pipeline

Semantic Chunks
      │
      ▼
Document Processor
      │
      ├── Executive Summary
      └── Action Item Extraction
              │
              ▼
        SummaryResult
"""

from .models import SummaryResult
from .document_summarizer import process_document


def summarize_document(
    document_id: str,
    document_name: str,
    chunks: list[str],
) -> SummaryResult:
    """
    Generate an executive summary and extract actionable items.

    Parameters
    ----------
    document_id : str
        Unique document identifier.

    document_name : str
        Original document name.

    chunks : list[str]
        Semantic chunk texts.

    Returns
    -------
    SummaryResult
        Combined summarization output.
    """

    executive_summary, action_items = process_document(
        document_id=document_id,
        document_name=document_name,
        chunks=chunks,
    )

    return SummaryResult(
        executive_summary=executive_summary,
        action_items=action_items,
    )