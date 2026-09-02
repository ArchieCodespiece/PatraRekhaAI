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

    def __init__(self, namespace: str | None = None):
        self.store = PineconeStore(namespace=namespace)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(
        self,
        embedding_result: EmbeddingResult,
        namespace: str | None = None,
    ) -> None:
        """
        Upload all embedded chunks to Pinecone.

        Parameters
        ----------
        embedding_result : EmbeddingResult
        namespace : str | None
            Per-user namespace. Overrides the namespace set at construction
            time.  When ``None`` and no namespace was set on the store, the
            vectors are upserted to the default (empty) namespace.
        """

        self.store.upsert(
            embedding_result.embedded_chunks,
            namespace=namespace,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        embedding: List[float],
        top_k: int = 5,
        namespace: str | None = None,
        filter: dict | None = None,
    ):
        """
        Search for similar vectors.

        Parameters
        ----------
        embedding : List[float]
            Query embedding.
        top_k : int
            Number of nearest neighbours.
        namespace : str | None
            Per-user namespace to restrict the search.
        filter : dict | None
            Optional Pinecone metadata filter expression.

        Returns
        -------
        Pinecone query response.
        """

        return self.store.query(
            embedding=embedding,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(
        self,
        document_id: str,
        namespace: str | None = None,
    ) -> None:
        """
        Delete all vectors belonging to a document.
        """

        self.store.delete_document(document_id, namespace=namespace)

    def delete(
        self,
        ids: List[str],
        namespace: str | None = None,
    ) -> None:
        """
        Delete vectors by IDs.
        """

        self.store.delete(ids, namespace=namespace)

    # ------------------------------------------------------------------
    # Information
    # ------------------------------------------------------------------

    def describe(self):
        """
        Return Pinecone index statistics.
        """

        return self.store.describe()
