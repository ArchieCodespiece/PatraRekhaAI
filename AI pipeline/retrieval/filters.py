"""
Helpers for building vector-store metadata filters.
"""

from typing import Dict, List, Optional


def build_document_filter(
    document_ids: List[str],
) -> Optional[Dict]:
    """
    Build a Pinecone metadata filter for selected documents.

    Parameters
    ----------
    document_ids : List[str]
        IDs of the documents currently selected by the user.

    Returns
    -------
    Optional[Dict]
        Pinecone metadata filter restricting retrieval to the
        supplied document IDs.
    """

    unique_document_ids = list(dict.fromkeys(document_ids))

    if not unique_document_ids:
        return None

    return {
        "document_id": {
            "$in": unique_document_ids,
        }
    }