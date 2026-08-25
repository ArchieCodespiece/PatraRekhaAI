"""Data models for the retrieval package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store."""

    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    chunk_index: int = 0
    page_start: int = 0
    page_end: int = 0
    section: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalConfig:
    """Configuration for a retrieval run."""

    top_k: int = 5
    score_threshold: Optional[float] = None
    deduplicate: bool = True
    rerank: bool = False


@dataclass
class RetrievalResult:
    """Result of a retrieval run."""

    query: str
    chunks: List[RetrievedChunk]
    documents_queried: List[str] = field(default_factory=list)
    total_candidates: int = 0
