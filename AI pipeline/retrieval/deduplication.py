"""
Utilities for removing duplicate retrieval results.
"""

from typing import List

from .models import RetrievedChunk


def deduplicate_chunks(
    chunks: List[RetrievedChunk],
) -> List[RetrievedChunk]:
    """
    Remove duplicate retrieved chunks using chunk_id.

    The original relevance ordering is preserved.

    Parameters
    ----------
    chunks : List[RetrievedChunk]
        Retrieved chunks ordered by relevance.

    Returns
    -------
    List[RetrievedChunk]
        Deduplicated chunks with original ordering preserved.
    """

    if not chunks:
        return []

    seen_chunk_ids = set()
    unique_chunks = []

    for chunk in chunks:
        if chunk.chunk_id in seen_chunk_ids:
            continue

        seen_chunk_ids.add(chunk.chunk_id)
        unique_chunks.append(chunk)

    return unique_chunks