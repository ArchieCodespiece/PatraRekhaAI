"""
VectorStore package.

Provides functionality for storing and retrieving vector embeddings
using Pinecone.
"""

from .pinecone_store import PineconeStore
from .pipeline import VectorStorePipeline

__all__ = [
    "PineconeStore",
    "VectorStorePipeline",
]