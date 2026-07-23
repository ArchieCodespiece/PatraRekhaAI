"""
Main VectorStore pipeline.

Pipeline Flow:
Embedding Result
        ↓
Pinecone Store
        ↓
Vector Database
"""

from __future__ import annotations

from typing import List

from embedding.models import EmbeddingResult

from .pinecone_store import PineconeStore


class VectorStorePipeline:
    """
    End-to-end vector store pipeline.
    """

    def __init__(self):
        self.store = PineconeStore()

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(
        self,
        embedding_result: EmbeddingResult,
    ) -> None:
        """
        Upload all embedded chunks to Pinecone.

        Parameters
        ----------
        embedding_result : EmbeddingResult
        """

        self.store.upsert(
            embedding_result.embedded_chunks
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        embedding: List[float],
        top_k: int = 5,
    ):
        """
        Search for similar vectors.

        Parameters
        ----------
        embedding : List[float]
            Query embedding.

        top_k : int
            Number of nearest neighbours.

        Returns
        -------
        Pinecone query response.
        """

        return self.store.query(
            embedding=embedding,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(
        self,
        document_id: str,
    ) -> None:
        """
        Delete all vectors belonging to a document.
        """

        self.store.delete_document(document_id)

    def delete(
        self,
        ids: List[str],
    ) -> None:
        """
        Delete vectors by IDs.
        """

        self.store.delete(ids)

    # ------------------------------------------------------------------
    # Information
    # ------------------------------------------------------------------

    def describe(self):
        """
        Return Pinecone index statistics.
        """

        return self.store.describe()
