"""
document_summarizer.py

Hierarchical document processing.

Workflow

Semantic Chunks
        │
        ▼
Batch Processing
        │
        ├── Summary
        └── Action Items
                │
                ▼
Executive Summary + Action Item Consolidation

Each semantic chunk is processed only once.
"""

from __future__ import annotations

import json

from .llm import generate
from .prompts import (
    BATCH_PROCESS_SYSTEM_PROMPT,
    BATCH_PROCESS_USER_PROMPT,
    EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
    EXECUTIVE_SUMMARY_USER_PROMPT,
    ACTION_ITEM_CONSOLIDATION_SYSTEM_PROMPT,
    ACTION_ITEM_CONSOLIDATION_USER_PROMPT,
)
from .utils import (
    combine_chunks,
    deduplicate_action_items,
    parse_json_string,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

BATCH_SIZE = 4


# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------

def _process_batch(batch: list[str]) -> tuple[str, list[dict]]:
    """
    Process one batch of semantic chunks.

    Parameters
    ----------
    batch : list[str]
        Semantic chunk texts.

    Returns
    -------
    tuple[str, list[dict]]
        Batch summary and extracted action items.
    """

    document = combine_chunks(batch)

    response = generate(
        system_prompt=BATCH_PROCESS_SYSTEM_PROMPT,
        user_prompt=BATCH_PROCESS_USER_PROMPT.format(
            document=document,
        ),
        temperature=0.2,
        max_tokens=2048,
    )

    try:
        result = parse_json_string(response)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "LLM returned invalid JSON during batch processing."
        ) from exc

    summary = result.get("summary", "").strip()
    action_items = result.get("action_items", [])

    if not isinstance(action_items, list):
        action_items = []

    return summary, action_items


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def process_document(
    document_id: str,
    document_name: str,
    chunks: list[str],
) -> tuple[str, str]:
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
    tuple[str, str]

        executive_summary
            JSON string containing the executive summary.

        action_items
            JSON string containing consolidated actionable items.
    """

    if not chunks:
        raise ValueError("No semantic chunks supplied.")

    partial_summaries: list[str] = []
    extracted_action_items: list[dict] = []

    # -------------------------------------------------------------------------
    # First Pass
    # -------------------------------------------------------------------------

    for i in range(0, len(chunks), BATCH_SIZE):

        batch = chunks[i:i + BATCH_SIZE]

        summary, action_items = _process_batch(batch)

        if summary:
            partial_summaries.append(summary)

        extracted_action_items.extend(action_items)

    # -------------------------------------------------------------------------
    # Executive Summary
    # -------------------------------------------------------------------------

    condensed_document = combine_chunks(partial_summaries)

    executive_summary = generate(
        system_prompt=EXECUTIVE_SUMMARY_SYSTEM_PROMPT,
        user_prompt=EXECUTIVE_SUMMARY_USER_PROMPT.format(
            document_id=document_id,
            document_name=document_name,
            document=condensed_document,
        ),
        temperature=0.2,
        max_tokens=2048,
    )

    # -------------------------------------------------------------------------
    # Action Item Consolidation
    # -------------------------------------------------------------------------

    unique_action_items = deduplicate_action_items(
        extracted_action_items
    )

    consolidated_action_items = generate(
        system_prompt=ACTION_ITEM_CONSOLIDATION_SYSTEM_PROMPT,
        user_prompt=ACTION_ITEM_CONSOLIDATION_USER_PROMPT.format(
            document_id=document_id,
            document_name=document_name,
            action_items=json.dumps(unique_action_items, indent=2),
        ),
        temperature=0.0,
        max_tokens=2048,
    )

    return executive_summary, consolidated_action_items