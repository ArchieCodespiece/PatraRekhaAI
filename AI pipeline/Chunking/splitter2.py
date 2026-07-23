"""
splitter2.py

Chunk generation and metadata creation.
"""

from __future__ import annotations

import uuid

from .models import (
    Chunk,
    ChunkMetadata,
    Document,
    Section,
)

from .splitter1 import SemanticSplitter


class SemanticSplitter(SemanticSplitter):
    """
    Extends splitter1.SemanticSplitter
    with chunk generation.
    """

    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------

    def split(
        self,
        document: Document,
        sections: list[Section],
    ) -> list[Chunk]:

        chunks: list[Chunk] = []

        for section in sections:

            chunks.extend(
                self._split_section(
                    document,
                    section,
                )
            )

        return chunks

    # -------------------------------------------------------------
    # Section Splitter
    # -------------------------------------------------------------

    def _split_section(
        self,
        document: Document,
        section: Section,
    ) -> list[Chunk]:

        # ---------------------------------------------------------
        # Build text from semantic blocks
        # ---------------------------------------------------------

        text = "\n\n".join(
            block.strip()
            for block in section.blocks
            if block.strip()
        ).strip()

        pieces: list[str] = []

        # Only split if text exists
        if text:
            pieces = [
                piece.strip()
                for piece in self.split_text(text)
                if piece.strip()
            ]

        # ---------------------------------------------------------
        # Preserve tables
        # ---------------------------------------------------------

        if section.tables:

            table_text = "\n\n".join(
                self.table_to_text(table)
                for table in section.tables
            ).strip()

            if table_text:

                if pieces:

                    candidate = (
                        pieces[-1]
                        + "\n\n"
                        + table_text
                    )

                    if self.token_count(candidate) <= self.max_tokens:
                        pieces[-1] = candidate
                    else:
                        pieces.append(table_text)

                else:
                    # Table-only section
                    pieces.append(table_text)

        # ---------------------------------------------------------
        # Nothing to store
        # ---------------------------------------------------------

        if not pieces:
            return []

        # ---------------------------------------------------------
        # Create chunks
        # ---------------------------------------------------------

        chunks: list[Chunk] = []

        for index, piece in enumerate(pieces, start=1):

            metadata = ChunkMetadata(
                chunk_id=str(uuid.uuid4()),
                chunk_index=index,
                document_id=document.document_id,
                document_name=document.document_name,
                page_start=section.page_start,
                page_end=section.page_end,
                section=section.title,
            )

            chunks.append(
                Chunk(
                    text=piece,
                    metadata=metadata,
                )
            )

        return chunks