"""
Core data models used throughout the chunking pipeline.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# =============================================================================
# Document Models
# =============================================================================

@dataclass(slots=True)
class Table:
    rows: List[List[str]] = field(default_factory=list)


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
    # Chunk Identity
    chunk_id: str
    chunk_index: int

    # Document Identity
    document_id: str
    document_name: str

    # Source
    source: Optional[str] = None

    # Collection
    collection: Optional[str] = None
    subject: Optional[str] = None
    category: Optional[str] = None

    # Ownership
    uploaded_by: Optional[str] = None
    upload_date: Optional[str] = None

    # Location
    page_start: int = 0
    page_end: int = 0

    # Hierarchy
    section: Optional[str] = None
    subsection: Optional[str] = None
    heading_path: List[str] = field(default_factory=list)

    # Retrieval
    object_type: str = "text"
    language: str = "en"

    # Extensible metadata
    extra: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Chunk Model
# =============================================================================

@dataclass(slots=True)
class Chunk:
    text: str
    metadata: ChunkMetadata

@dataclass(slots=True)
class Table:
    rows: List[List[str]] = field(default_factory=list)
    caption: str = ""
    page_number: int = 0