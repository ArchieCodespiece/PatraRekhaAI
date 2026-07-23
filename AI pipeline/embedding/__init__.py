"""
Embedding package.

Provides:
- GeminiEmbedder: Generates embeddings using the Gemini API.
- EmbeddedChunk: Chunk with its embedding vector.
- EmbeddingResult: Collection of embedded chunks.
- EmbeddingPipeline: End-to-end embedding pipeline.
"""

from .embedder import GeminiEmbedder
from .models import EmbeddedChunk, EmbeddingResult
from .pipeline import EmbeddingPipeline

__all__ = [
    "GeminiEmbedder",
    "EmbeddedChunk",
    "EmbeddingResult",
    "EmbeddingPipeline",
]