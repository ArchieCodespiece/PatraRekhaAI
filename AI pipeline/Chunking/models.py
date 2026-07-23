"""
Core data models used throughout the chunking pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# =============================================================================
# Document Models
# =============================================================================

@dataclass(slots=True)
class Table:
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ""
    page_number: int = 0


@dataclass(slots=True)
class Page:
    page_number: int
    text: str
    tables: List[Table] = field(default_factory=list)


@dataclass(slots=True)
class Document:
    document_id: str
    document_name: str
    pages: List[Page]


# =============================================================================
# Semantic Models
# =============================================================================

@dataclass(slots=True)
class Section:
    title: str
    level: int

    page_start: int
    page_end: int

    blocks: List[str] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)

    object_type: str = "text"


# =============================================================================
# Chunk Metadata
# =============================================================================

@dataclass(slots=True)
class ChunkMetadata:
    """
    Minimal metadata attached to every chunk.
    """

    chunk_id: str
    chunk_index: int

    document_id: str
    document_name: str

    page_start: int
    page_end: int

    section: Optional[str] = None


# =============================================================================
# Chunk Model
# =============================================================================

@dataclass(slots=True)
class Chunk:
    text: str
    metadata: ChunkMetadata


# =============================================================================
# Pipeline Model
# =============================================================================

@dataclass(slots=True)
class ProcessedDocument:
    """
    Represents a document as it moves through the ingestion pipeline.
    """

    document: Document

    sections: List[Section] = field(default_factory=list)

    chunks: List[Chunk] = field(default_factory=list)

    metadata_path: Optional[str] = None