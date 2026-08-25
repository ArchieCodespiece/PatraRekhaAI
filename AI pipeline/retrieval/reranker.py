"""
Utilities for ranking retrieved chunks.

The initial implementation uses the vector similarity score
returned by Pinecone. A dedicated reranking model can be added
later without changing the retrieval pipeline interface.
"""

from typing import List

from .models import RetrievedChunk


def rerank_chunks(
    chunks: List[RetrievedChunk],
    top_k: int | None = None,
) -> List[RetrievedChunk]:
    """
    Rank retrieved chunks by their relevance score.

    Parameters
    ----------
    chunks : List[RetrievedChunk]
        Retrieved chunks containing vector similarity scores.

    top_k : int | None
        Optional number of highest-scoring chunks to return.

    Returns
    -------
    List[RetrievedChunk]
        Chunks ordered from highest to lowest relevance score.
    """

    if not chunks:
        return []

    ranked_chunks = sorted(
        chunks,
        key=lambda chunk: chunk.score,
        reverse=True,
    )

    if top_k is not None:
        return ranked_chunks[:top_k]

    return ranked_chunks