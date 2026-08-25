"""
Helpers for building LLM-ready context from retrieved chunks.
"""

import re
from typing import List

from .models import RetrievedChunk


DEFAULT_MAX_CONTEXT_TOKENS = 5000

FULL_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

SHORT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{12}-"
)


def _clean_document_name(name: str) -> str:
    if not name:
        return name

    cleaned = str(name)

    while True:
        new = FULL_UUID_PATTERN.sub(
            "",
            cleaned,
        ).lstrip("-_")

        new = SHORT_ID_PATTERN.sub(
            "",
            new,
        ).lstrip("-_")

        if new == cleaned:
            break

        cleaned = new

    return cleaned


def build_context(
    chunks: List[RetrievedChunk],
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
) -> str:
    """
    Build an LLM-ready context from retrieved chunks.

    Chunks are expected to already be deduplicated and ordered
    by relevance before reaching this function.

    Parameters
    ----------
    chunks : List[RetrievedChunk]
        Final retrieved chunks.

    max_context_tokens : int
        Maximum approximate number of tokens allowed in the
        generated context.

    Returns
    -------
    str
        Structured context suitable for answer generation.
    """

    if not chunks or max_context_tokens <= 0:
        return ""

    sections = []
    estimated_tokens = 0

    for rank, chunk in enumerate(chunks, start=1):
        section = _format_chunk(
            chunk=chunk,
            rank=rank,
        )

        section_tokens = _estimate_tokens(section)

        if estimated_tokens + section_tokens > max_context_tokens:
            break

        sections.append(section)
        estimated_tokens += section_tokens

    return "\n\n".join(sections)


def _format_chunk(
    chunk: RetrievedChunk,
    rank: int,
) -> str:
    """
    Format a retrieved chunk with its source information.
    """

    source = _format_source(chunk)

    return (
        f"[Source {rank}]\n"
        f"{source}\n"
        f"Content:\n"
        f"{chunk.text.strip()}"
    )


def _format_source(
    chunk: RetrievedChunk,
) -> str:
    """
    Format source metadata for a retrieved chunk.
    """

    lines = [
        f"Document: {_clean_document_name(chunk.document_name)}",
        f"Pages: {chunk.page_start}-{chunk.page_end}",
    ]

    if chunk.section:
        lines.append(
            f"Section: {chunk.section}"
        )

    return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """
    Estimate token count using a lightweight heuristic.

    This provides a conservative context limit without adding
    a tokenizer dependency to the retrieval module.
    """

    if not text:
        return 0

    return max(1, len(text) // 4)