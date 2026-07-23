"""
Semantic document parser.

Builds semantic sections from a Document.
"""

import re

from models import Document, Section


class SemanticBuilder:
    """Convert a Document into semantic Sections."""

    HEADING_PATTERNS = [
        (re.compile(r"^(#{1,6})\s+(.+)$"), "markdown"),
        (re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$"), "numbered"),
    ]

    def build(self, document: Document) -> list[Section]:
        sections: list[Section] = []
        current: Section | None = None

        for page in document.pages:

            for line in page.text.splitlines():
                line = line.strip()

                if not line:
                    continue

                heading = self._parse_heading(line)

                if heading:

                    if current:
                        current.page_end = page.page_number
                        sections.append(current)

                    level, title = heading

                    current = Section(
                        title=title,
                        level=level,
                        page_start=page.page_number,
                        page_end=page.page_number,
                    )

                elif current:
                    current.blocks.append(line)

            if current:
                current.page_end = page.page_number
                current.tables.extend(page.tables)

        if current:
            sections.append(current)

        return sections

    def _parse_heading(
        self,
        line: str,
    ) -> tuple[int, str] | None:

        # Markdown headings
        match = self.HEADING_PATTERNS[0][0].match(line)

        if match:
            hashes, title = match.groups()
            return len(hashes), title.strip()

        # Numbered headings
        match = self.HEADING_PATTERNS[1][0].match(line)

        if match:
            number, title = match.groups()
            level = number.count(".") + 1
            return level, title.strip()

        return None