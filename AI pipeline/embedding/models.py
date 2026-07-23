"""
Core data models used throughout the embedding pipeline.
"""

from dataclasses import dataclass
from typing import List

from Chunking.models import Chunk


# =============================================================================
# Embedded Chunk Model
# =============================================================================

@dataclass(slots=True)
class EmbeddedChunk:
    """
    Represents a semantic chunk along with its embedding vector.
    """

    chunk: Chunk

    embedding: List[float]


# =============================================================================
# Embedding Result
# =============================================================================

@dataclass(slots=True)
class EmbeddingResult:
    """
    Collection of embedded chunks returned by the embedding pipeline.
    """

    embedded_chunks: List[EmbeddedChunk]