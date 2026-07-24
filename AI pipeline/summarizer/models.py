"""
models.py

Data models for the summarization pipeline.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class SummaryResult:
    """
    Container for summarization outputs.

    Attributes
    ----------
    executive_summary : str
        Raw JSON string returned by the executive summarizer.

    action_items : str
        Raw JSON string containing all extracted actionable items.
    """

    executive_summary: str
    action_items: str