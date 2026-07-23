from __future__ import annotations

import re
import uuid
from typing import List
import tiktoken

from .models import (
    Chunk,
    ChunkMetadata,
    Document,
    Section,
    Table,
)


class SemanticSplitter:
    """
    Split semantic Sections into embedding-ready chunks.

    Splitting priority:

        Paragraph
            ↓
        Sentence
            ↓
        Token

    Tables are always preserved.
    """

    SENTENCE_PATTERN = re.compile(
        r"(?<=[.!?])\s+"
    )

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        max_tokens: int = 500,
        overlap_tokens: int = 50,
    ):

        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

        self.encoding = tiktoken.encoding_for_model(model)

    # ---------------------------------------------------------
    # Token Helpers
    # ---------------------------------------------------------

    def token_count(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def last_tokens(self, text: str) -> str:

        tokens = self.encoding.encode(text)

        if len(tokens) <= self.overlap_tokens:
            return text

        return self.encoding.decode(
            tokens[-self.overlap_tokens :]
        )

    # ---------------------------------------------------------
    # Recursive Text Splitter
    # ---------------------------------------------------------

    def split_text(self, text: str) -> List[str]:
        """
        Recursively split text.

        Paragraph
            ↓
        Sentence
            ↓
        Token
        """


        text = text.strip()

        if not text:
            return []

        if self.token_count(text) <= self.max_tokens:
            return [text]

        paragraphs = [
            p.strip()
            for p in text.split("\n\n")
            if p.strip()
        ]

        if len(paragraphs) > 1:
            return self._split_paragraphs(paragraphs)

        sentences = [
            s.strip()
            for s in self.SENTENCE_PATTERN.split(text)
            if s.strip()
        ]

        if len(sentences) > 1:
            return self._split_sentences(sentences)

        return self._split_tokens(text)

    # ---------------------------------------------------------

    def _split_paragraphs(
        self,
        paragraphs: List[str],
    ) -> List[str]:

        chunks = []
        current = ""

        for para in paragraphs:

            candidate = (
                para
                if not current
                else current + "\n\n" + para
            )

            if self.token_count(candidate) <= self.max_tokens:

                current = candidate

            else:

                if current:
                    chunks.append(current)

                current = para

        if current:
            chunks.append(current)

        return chunks

    # ---------------------------------------------------------

    def _split_sentences(
        self,
        sentences: List[str],
    ) -> List[str]:

        chunks = []
        current = ""

        for sentence in sentences:

            candidate = (
                sentence
                if not current
                else current + " " + sentence
            )

            if self.token_count(candidate) <= self.max_tokens:

                current = candidate

            else:

                if current:
                    chunks.append(current)

                current = sentence

        if current:
            chunks.append(current)

        return chunks

    # ---------------------------------------------------------

    def _split_tokens(
        self,
        text: str,
    ) -> List[str]:

        tokens = self.encoding.encode(text)

        chunks = []

        start = 0

        while start < len(tokens):

            end = min(
                start + self.max_tokens,
                len(tokens),
            )

            chunk = self.encoding.decode(
                tokens[start:end]
            )

            chunks.append(chunk)

            start = end - self.overlap_tokens

            if start < 0:
                start = 0

        return chunks

    # ---------------------------------------------------------
    # Table Utilities
    # ---------------------------------------------------------

    @staticmethod
    def table_to_text(table: Table) -> str:

        lines = []

        if getattr(table, "caption", ""):
            lines.append(table.caption)

        for row in table.rows:

            lines.append(
                " | ".join(
                    str(cell).strip()
                    for cell in row
                )
            )

        return "\n".join(lines)
