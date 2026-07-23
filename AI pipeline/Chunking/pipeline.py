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

from .chunking import ChunkingPipeline
from .models import Document, Page, Table


class ChunkPipeline:
    """End-to-end document chunking pipeline."""

    def __init__(self):
        self.chunking = ChunkingPipeline()

    def process(
        self,
        json_path: str | Path,
        **metadata,
    ):
        """Convert OCR JSON into metadata-enriched chunks."""

        document = self._load_document(json_path)

        return self.chunking.process(document)

    @staticmethod
    def _load_document(json_path: str | Path) -> Document:
        """Load OCR JSON into Document model."""

        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        pages = []

        for page in raw:

            tables = [
                Table(
                    rows=t.get("rows", []),
                    caption=t.get("caption", ""),
                    page_number=page["page_number"],
                )
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
