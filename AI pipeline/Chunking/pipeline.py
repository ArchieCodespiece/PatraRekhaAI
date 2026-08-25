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
import re
from pathlib import Path

from .chunking import ChunkingPipeline
from .models import Document, Page, Table

FILE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

SHORT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{12}-"
)


def _clean_stem(stem: str) -> str:
    cleaned = stem

    while True:
        new = FILE_ID_PATTERN.sub(
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

        raw_stem = Path(json_path).stem
        document_id = raw_stem
        document_name = _clean_stem(raw_stem)

        return Document(
            document_id=document_id,
            document_name=document_name,
            pages=pages,
        )
