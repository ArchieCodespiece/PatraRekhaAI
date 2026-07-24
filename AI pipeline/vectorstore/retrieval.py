"""
Retrieval helpers for Pinecone-backed vector search.

Supports:
1. Global semantic search.
2. Semantic search restricted to one or more selected documents.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .pinecone_store import PineconeStore


def get_chunks(
    query_embedding: List[float],
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Search across the entire vector database.
    """

    store = PineconeStore()

    return store.query(
        embedding=query_embedding,
        top_k=top_k,
    )


def get_chunks_from_documents(
    document_names: List[str],
    query_embedding: List[float],
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Search only inside the selected documents.

    Parameters
    ----------
    document_names : List[str]
        List of document_name values stored in Pinecone metadata.

    query_embedding : List[float]
        Query embedding.

    top_k : int
        Number of chunks to retrieve.
    """

    store = PineconeStore()

    unique_document_names = list(dict.fromkeys(document_names))
    matches_by_document = []

    for document_name in unique_document_names:
        result = store.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter={
                "document_name": document_name,
            },
        )

        matches = result.get("matches", []) if isinstance(result, dict) else getattr(result, "matches", [])
        matches_by_document.append(list(matches))

    def match_score(match: Any) -> float:
        if isinstance(match, dict):
            return float(match.get("score") or 0)
        return float(getattr(match, "score", 0) or 0)

    for matches in matches_by_document:
        matches.sort(key=match_score, reverse=True)

    balanced_matches = []
    for index in range(top_k):
        for matches in matches_by_document:
            if index < len(matches):
                balanced_matches.append(matches[index])

    return {
        "matches": balanced_matches,
        "documents_queried": unique_document_names,
    }
