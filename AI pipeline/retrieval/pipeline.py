"""
Main retrieval pipeline.

Flow:

User Query
    ↓
Query Embedding
    ↓
Selected Document Filter
    ↓
Vector Retrieval
    ↓
Retrieved Chunks
"""

from __future__ import annotations

from typing import List

from embedding.embedder import GeminiEmbedder

from .filters import build_document_filter
from .models import RetrievalConfig, RetrievalResult
from .retriever import Retriever


class RetrievalPipeline:
    """
    End-to-end retrieval pipeline.

    The pipeline coordinates query embedding, document filtering,
    and vector retrieval.
    """

    def __init__(self):
        self.embedder = GeminiEmbedder()
        self.retriever = Retriever()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        document_ids: List[str],
        config: RetrievalConfig | None = None,
    ) -> RetrievalResult:
        """
        Retrieve relevant chunks from the currently selected documents.

        Parameters
        ----------
        query : str
            User's search question.

        document_ids : List[str]
            IDs of the documents currently selected by the user.

        config : RetrievalConfig | None
            Optional retrieval configuration.

        Returns
        -------
        RetrievalResult
            Normalized retrieval result.
        """

        config = config or RetrievalConfig()

        query_embedding = self.embedder.embed_text(query)

        document_filter = build_document_filter(
            document_ids
        )

        chunks = self.retriever.retrieve(
            embedding=query_embedding,
            top_k=config.top_k,
            metadata_filter=document_filter,
        )

        if config.score_threshold is not None:
            chunks = [
                chunk
                for chunk in chunks
                if chunk.score >= config.score_threshold
            ]

        return RetrievalResult(
            query=query,
            chunks=chunks,
            documents_queried=list(
                dict.fromkeys(document_ids)
            ),
            total_candidates=len(chunks),
        )