"""
Utility functions for the embedding pipeline.
"""

from __future__ import annotations

from typing import Iterable, List, TypeVar

T = TypeVar("T")


def batch_iterator(items: List[T], batch_size: int) -> Iterable[List[T]]:
    """
    Yield successive batches from a list.

    Parameters
    ----------
    items : List[T]
        Input list.
    batch_size : int
        Size of each batch.

    Yields
    ------
    List[T]
        A batch of items.
    """

    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


def chunk_count(chunks: List) -> int:
    """
    Return the number of chunks.

    Useful for logging and testing.
    """

    return len(chunks)