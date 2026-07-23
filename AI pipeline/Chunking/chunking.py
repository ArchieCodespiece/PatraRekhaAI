"""
chunking.py

Semantic chunking pipeline.

Document
    ↓
Semantic Sections
    ↓
Chunks
"""

from .models import Document
from .semantic import SemanticBuilder
from .splitter2 import SemanticSplitter


class ChunkingPipeline:
    """
    Pipeline that converts a Document into semantic chunks.
    """

    def __init__(
        self,
        max_tokens: int = 500,
        overlap_tokens: int = 50,
    ):
        self.semantic_builder = SemanticBuilder()

        self.splitter = SemanticSplitter(
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )

    def process(self, document: Document):
        """
        Parameters
        ----------
        document : Document

        Returns
        -------
        list[Chunk]
        """

        # Build semantic sections
        sections = self.semantic_builder.build(document)

        # Split sections into chunks
        chunks = self.splitter.split(
            document,
            sections,
        )

        return chunks
