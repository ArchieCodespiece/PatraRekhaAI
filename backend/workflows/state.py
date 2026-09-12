"""Shared workflow state passed between orchestrator and steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class WorkflowState:
    user_id: str
    owner_email: str
    effective_email: Optional[str]
    query: str
    conversation_id: str

    # Human-readable document names as shown in the chat panel.
    selected_documents: List[str] = field(default_factory=list)

    # (display_name, pinecone_name) pairs, order preserved.
    doc_pairs: List[Tuple[str, str]] = field(default_factory=list)

    namespace: Optional[str] = None

    target_format: Optional[str] = None

    # When enabled, run claim verification and unsupported-claim recovery.
    think_mode: bool = False

    def display_names(self) -> List[str]:
        return [display for display, _ in self.doc_pairs]

    def pinecone_names(self) -> List[str]:
        return [pinecone for _, pinecone in self.doc_pairs]

    def display_by_pinecone(self) -> dict:
        return {
            pinecone: display
            for display, pinecone in self.doc_pairs
        }