"""
Core vector retrieval logic.

Responsible for querying the vector store and converting
vector-store matches into application-level RetrievedChunk objects.
"""

from typing import Any, Dict, List, Optional

from vectorstore.pipeline import VectorStorePipeline

from .models import RetrievedChunk


class Retriever:
    """
    Low-level retrieval component.

    Queries the vector store using a query embedding and optional
    metadata filter, then normalizes the returned matches.
    """

    def __init__(self):
        self.vector_store = VectorStorePipeline()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        embedding: List[float],
        top_k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve the most relevant chunks for an embedding.

        Parameters
        ----------
        embedding : List[float]
            Query embedding vector.

        top_k : int
            Number of chunks to retrieve.

        metadata_filter : Optional[Dict[str, Any]]
            Optional Pinecone metadata filter.

        Returns
        -------
        List[RetrievedChunk]
            Normalized retrieved chunks.
        """

        response = self.vector_store.search(
            embedding=embedding,
            top_k=top_k,
            filter=metadata_filter,
        )

        matches = self._extract_matches(response)

        return [
            self._convert_match(match)
            for match in matches
        ]

    # ------------------------------------------------------------------
    # Response handling
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_matches(response: Any) -> List[Any]:
        """
        Extract matches from a Pinecone response.

        Supports both dictionary-style and object-style responses.
        """

        if isinstance(response, dict):
            return list(response.get("matches", []))

        return list(getattr(response, "matches", []) or [])

    # ------------------------------------------------------------------
    # Match conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_match(match: Any) -> RetrievedChunk:
        """
        Convert a Pinecone match into a RetrievedChunk.
        """

        if isinstance(match, dict):
            match_id = match.get("id", "")
            score = float(match.get("score") or 0.0)
            metadata = match.get("metadata") or {}
        else:
            match_id = getattr(match, "id", "")
            score = float(getattr(match, "score", 0.0) or 0.0)
            metadata = getattr(match, "metadata", {}) or {}

        return RetrievedChunk(
            chunk_id=str(match_id),
            document_id=str(metadata.get("document_id", "")),
            document_name=str(metadata.get("document_name", "")),
            text=str(metadata.get("text", "")),
            score=score,
            chunk_index=int(metadata.get("chunk_index", 0)),
            page_start=int(metadata.get("page_start", 0)),
            page_end=int(metadata.get("page_end", 0)),
            section=metadata.get("section"),
            metadata=dict(metadata),
        )