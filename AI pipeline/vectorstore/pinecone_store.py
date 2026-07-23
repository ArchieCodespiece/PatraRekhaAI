"""
Pinecone vector store implementation.
"""

from __future__ import annotations

from typing import List

from pinecone import Pinecone, ServerlessSpec

from embedding.models import EmbeddedChunk

from .config import (
    DISTANCE_METRIC,
    PINECONE_API_KEY,
    PINECONE_CLOUD,
    PINECONE_INDEX_NAME,
    PINECONE_REGION,
    UPSERT_BATCH_SIZE,
    VECTOR_DIMENSION,
)


class PineconeStore:
    """
    Wrapper around the Pinecone vector database.
    """

    def __init__(self):

        self.pc = Pinecone(api_key=PINECONE_API_KEY)

        self._create_index_if_missing()

        self.index = self.pc.Index(PINECONE_INDEX_NAME)

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _create_index_if_missing(self) -> None:
        """
        Create the Pinecone index if it does not already exist.
        """

        existing = self.pc.list_indexes().names()

        if PINECONE_INDEX_NAME in existing:
            return

        self.pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=VECTOR_DIMENSION,
            metric=DISTANCE_METRIC,
            spec=ServerlessSpec(
                cloud=PINECONE_CLOUD,
                region=PINECONE_REGION,
            ),
        )

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(
        self,
        embedded_chunks: List[EmbeddedChunk],
    ) -> None:
        """
        Upload embedded chunks into Pinecone.
        """

        vectors = []

        for embedded in embedded_chunks:

            metadata = {
                "chunk_index": embedded.chunk.metadata.chunk_index,
                "document_id": embedded.chunk.metadata.document_id,
                "document_name": embedded.chunk.metadata.document_name,
                "page_start": embedded.chunk.metadata.page_start,
                "page_end": embedded.chunk.metadata.page_end,
                "section": embedded.chunk.metadata.section,
                "text": embedded.chunk.text,
            }

            vectors.append(
                {
                    "id": embedded.chunk.metadata.chunk_id,
                    "values": embedded.embedding,
                    "metadata": metadata,
                }
            )

        for i in range(0, len(vectors), UPSERT_BATCH_SIZE):

            batch = vectors[i : i + UPSERT_BATCH_SIZE]

            self.index.upsert(vectors=batch)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        embedding: List[float],
        top_k: int = 5,
    ):
        """
        Search similar vectors.
        """

        return self.index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(
        self,
        ids: List[str],
    ) -> None:
        """
        Delete vectors by ID.
        """

        self.index.delete(ids=ids)

    def delete_document(
        self,
        document_id: str,
    ) -> None:
        """
        Delete all vectors belonging to a document.
        """

        self.index.delete(
            filter={
                "document_id": document_id,
            }
        )

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def describe(self):
        """
        Return index statistics.
        """

        return self.index.describe_index_stats()
