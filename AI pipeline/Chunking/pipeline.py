"""
Main chunking pipeline.

Pipeline Flow:
OCR JSON
    ↓
Document
    ↓
Semantic Builder
    ↓
Sections
    ↓
Chunk Splitter
    ↓
Chunks
    ↓
Metadata Builder
    ↓
Final Chunks
"""

import json
from pathlib import Path

from models import Document, Page, Table
from semantic import SemanticBuilder
from splitter import ChunkSplitter
from metadata import MetadataBuilder


class ChunkPipeline:
    """End-to-end document chunking pipeline."""

    def __init__(self):
        self.semantic = SemanticBuilder()
        self.splitter = ChunkSplitter()
        self.metadata = MetadataBuilder()

    def process(
        self,
        json_path: str | Path,
        **metadata,
    ):
        """Convert OCR JSON into metadata-enriched chunks."""

        document = self._load_document(json_path)

        sections = self.semantic.build(document)

        chunks = self.splitter.split(sections)

        chunks = self.metadata.attach(
            chunks=chunks,
            document=document,
            **metadata,
        )

        return chunks

    @staticmethod
    def _load_document(json_path: str | Path) -> Document:
        """Load OCR JSON into Document model."""

        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        pages = []

        for page in raw:

            tables = [
                Table(rows=t.get("rows", []))
                for t in page.get("tables", [])
            ]

            pages.append(
                Page(
                    page_number=page["page_number"],
                    text=page.get("text", ""),
                    tables=tables,
                )
            )

        return Document(
            document_id=Path(json_path).stem,
            document_name=Path(json_path).stem,
            pages=pages,
        )