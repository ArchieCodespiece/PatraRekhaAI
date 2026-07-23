"""
Post-processing for semantic chunks.

This module cleans the output produced by semantic.py.

Responsibilities
----------------
1. Remove false headings created by OCR.
2. Merge tiny/noisy sections into their previous section.
3. Prevent table rows from becoming standalone chunks.
4. Preserve page ranges and content.
"""

from __future__ import annotations

from typing import List

from models import Section


# --------------------------------------------------------------------
# OCR junk that should never become a section
# --------------------------------------------------------------------

INVALID_TITLES = {
    "YES",
    "NO",
    "YES/NO",
    "Y/N",
    "PG",
    "Graduate",
    "Higher",
    "Higher Secondary",
    "Matriculation",
    "Other",
}


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

def _paragraph_count(section: Section) -> int:
    return len(section.paragraphs)


def _table_count(section: Section) -> int:
    return len(section.tables)


def _is_empty(section: Section) -> bool:
    return (
        _paragraph_count(section) == 0
        and _table_count(section) == 0
    )


def _looks_like_table_row(title: str) -> bool:
    """
    Detect headings that are actually table rows.
    """

    title = title.strip()

    if title in INVALID_TITLES:
        return True

    if len(title.split()) == 1 and len(title) < 20:
        return True

    if title.startswith("("):
        return True

    return False


def _should_merge(section: Section) -> bool:
    """
    Decide whether a chunk is probably OCR noise.
    """

    title = section.title.strip()

    if not title:
        return True

    if title in INVALID_TITLES:
        return True

    if _looks_like_table_row(title):
        return True

    if _is_empty(section):
        return True

    if len(title) > 100:
        return True

    return False


# --------------------------------------------------------------------
# Merge logic
# --------------------------------------------------------------------

def _merge_sections(previous: Section, current: Section) -> None:
    """
    Merge current section into previous section.
    """

    previous.paragraphs.extend(current.paragraphs)
    previous.tables.extend(current.tables)

    previous.children.extend(current.children)

    previous.end_page = max(previous.end_page, current.end_page)


# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------

def clean_chunks(sections: List[Section]) -> List[Section]:
    """
    Clean semantic chunks.

    Parameters
    ----------
    sections
        Output from semantic.py

    Returns
    -------
    List[Section]
    """

    if not sections:
        return sections

    cleaned: List[Section] = [sections[0]]

    for section in sections[1:]:

        if _should_merge(section):
            _merge_sections(cleaned[-1], section)
        else:
            cleaned.append(section)

    return cleaned