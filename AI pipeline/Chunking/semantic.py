"""
Semantic document parser.

Builds semantic sections from a Document.
"""

import re

from .models import Document, Section


class SemanticBuilder:
    """Convert a Document into semantic Sections."""

    HEADING_PATTERNS = [
        (re.compile(r"^(#{1,6})\s+(.+)$"), "markdown"),
        (re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$"), "numbered"),
        (
            re.compile(
                r"^(?:section|article|clause|part|schedule|exhibit)\s+"
                r"([ivx0-9]+|[a-z]+)[.:]?\s*(.+)$",
                re.IGNORECASE,
            ),
            "section",
        ),
        (re.compile(r"^(.{2,60}):\s*$"), "colon"),
    ]

    NON_HEADING_PREFIXES = (
        "in witness whereof",
        "now therefore",
        "it is hereby",
        "this agreement",
        "the parties agree",
        "subject to",
        "whereas",
    )

    def build(self, document: Document) -> list[Section]:
        sections: list[Section] = []
        current: Section | None = None

        for page in document.pages:

            for line in page.text.splitlines():
                line = line.strip()

                if not line:
                    continue

                heading = self._parse_heading(line)

                if not heading:
                    heading = self._parse_uppercase_heading(line)

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

        for pattern, label in self.HEADING_PATTERNS:
            match = pattern.match(line)

            if not match:
                continue

            if label == "markdown":
                hashes, title = match.groups()
                return len(hashes), title.strip()

            if label == "numbered":
                number, title = match.groups()
                level = number.count(".") + 1
                return level, title.strip()

            if label == "section":
                title = match.group(2)

                if not (title or "").strip():
                    return None

                return 2, title.strip()

            if label == "colon":
                title = match.group(1).strip()

                if not title or len(title.split()) > 7:
                    return None

                return 3, title

        return None

    def _parse_uppercase_heading(
        self,
        line: str,
    ) -> tuple[int, str] | None:
        if not line or len(line) > 80:
            return None

        if line != line.upper():
            return None

        if line.rstrip().endswith("."):
            return None

        tokens = [token for token in line.split() if token.isalpha()]

        if not (2 <= len(tokens) <= 7):
            return None

        if line.lower().startswith(self.NON_HEADING_PREFIXES):
            return None

        return 2, line.strip()