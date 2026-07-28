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
from .models import Section


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

        # Small or plain-text PDFs may not contain any detectable headings.
        # In that case, preserve the full document as a single fallback section
        # so embedding/vectorization can still proceed.
        if not sections:
            fallback_blocks = []
            fallback_tables = []

            for page in document.pages:
                page_text = (page.text or "").strip()
                if page_text:
                    fallback_blocks.append(page_text)
                if page.tables:
                    fallback_tables.extend(page.tables)

            fallback_text = "\n\n".join(fallback_blocks).strip()
            if fallback_text or fallback_tables:
                sections = [
                    Section(
                        title="Full Document",
                        level=1,
                        page_start=document.pages[0].page_number if document.pages else 1,
                        page_end=document.pages[-1].page_number if document.pages else 1,
                        blocks=[fallback_text] if fallback_text else [],
                        tables=fallback_tables,
                    )
                ]

        # Split sections into chunks
        chunks = self.splitter.split(
            document,
            sections,
        )

        return chunks
