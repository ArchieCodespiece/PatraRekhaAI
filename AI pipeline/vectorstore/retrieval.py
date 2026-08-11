"""
Retrieval helpers for Pinecone-backed vector search.

Supports:
1. Global semantic search.
2. Semantic search restricted to one or more selected documents.

Both functions accept an optional ``namespace`` parameter that restricts
the search to a per-user Pinecone namespace when ``USE_PINECONE_NAMESPACES``
is enabled.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .pinecone_store import PineconeStore
from .config import USE_NAMESPACES


def get_chunks(
    query_embedding: List[float],
    top_k: int = 5,
    namespace: str | None = None,
) -> Dict[str, Any]:
    """
    Search across the entire vector database (or within a namespace).
    """

    ns = namespace if (USE_NAMESPACES and namespace) else None
    store = PineconeStore(namespace=ns)

    return store.query(
        embedding=query_embedding,
        top_k=top_k,
    )


def get_chunks_from_documents(
    document_names: List[str],
    query_embedding: List[float],
    top_k: int = 5,
    namespace: str | None = None,
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
        Number of chunks to retrieve per document.

    namespace : str | None
        Per-user Pinecone namespace to scope the query.
    """

    ns = namespace if (USE_NAMESPACES and namespace) else None
    store = PineconeStore(namespace=ns)

    unique_document_names = list(dict.fromkeys(document_names))
    matches_by_document = []

    for document_name in unique_document_names:
        result = store.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            namespace=ns,
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
