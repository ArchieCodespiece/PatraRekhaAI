"""Sentence segmentation with page attribution.

Segments page-annotated OCR/text output into sentences so extractive
components (date extraction, summarization ranking) can reference exact
source spans with page numbers.

Tolerant of OCR noise: falls back to paragraph-based segmentation when a
page yields too few recognisable sentence boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


# Sentence enders: Latin punctuation + Devanagari danda (।), Bengali danda,
# Arabic question mark, full-width full stop.
_SENTENCE_END = re.compile(
    r"(?<=[.!?\u0964\u0965\u3002\u2026؟۔])\s*"
)

SENTENCE_TEXT_LEN = 600


@dataclass
class Sentence:
    page: int | None
    text: str
    start: int
    end: int


def segment_text(text: str) -> list[tuple[int, int, str]]:
    """Split a page's text into (start, end, text) spans.

    Preserves original offsets so downstream spans can be wired back to the
    page text. Only splits on real sentence enders; untouched input returns
    a single span.
    """
    if not text:
        return []

    spans: list[tuple[int, int, str]] = []

    matches = list(_SENTENCE_END.finditer(text))
    if not matches:
        return [(0, len(text), text)]

    cursor = 0
    for m in matches:
        end = m.end()
        if end <= cursor:
            continue
        chunk = text[cursor:end].strip()
        if chunk:
            # Recompute offset inside the stripped chunk.
            stripped = text[cursor:end]
            leading = len(stripped) - len(stripped.lstrip())
            start = cursor + leading
            spans.append((start, cursor + end, chunk))
        cursor = end

    tail = text[cursor:].strip()
    if tail:
        stripped = text[cursor:]
        leading = len(stripped) - len(stripped.lstrip())
        spans.append((cursor + leading, len(text), tail))

    return spans


def index_pages(
    pages: Iterable[dict[str, Any]] | Iterable[Sentence],
) -> list[Sentence]:
    """Convert page-annotated input to a flat, ordered sentence list.

    Accepts either ``[{"page": n, "text": "..."}]`` dicts or already-indexed
    ``Sentence`` objects.
    """
    sentences: list[Sentence] = []

    for page in pages:
        if isinstance(page, Sentence):
            sentences.append(page)
            continue

        page_no = page.get("page")
        raw_text = page.get("text") or ""

        spans = segment_text(raw_text)
        if len(spans) == 1 and len(spans[0][2]) > SENTENCE_TEXT_LEN:
            # No natural sentence boundaries on a long page — fall back to
            # paragraph segmentation so ranking still has granular units.
            spans = _segment_paragraphs(raw_text)

        for start, end, text in spans:
            sentences.append(
                Sentence(
                    page=page_no,
                    text=text,
                    start=start,
                    end=end,
                )
            )

    return sentences


def _segment_paragraphs(text: str) -> list[tuple[int, int, str]]:
    """Fallback segmentation on double-newline paragraph boundaries."""
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    for m in re.finditer(r"(?:\n\s*){2,}", text):
        end = m.start()
        para = text[cursor:end].strip()
        if para:
            stripped = text[cursor:end]
            leading = len(stripped) - len(stripped.lstrip())
            spans.append((cursor + leading, end, para))
        cursor = m.end()

    tail = text[cursor:].strip()
    if tail:
        stripped = text[cursor:]
        leading = len(stripped) - len(stripped.lstrip())
        spans.append((cursor + leading, len(text), tail))

    if not spans:
        return [(0, len(text), text.strip() or "")]

    return spans


def find_sentence(
    sentences: list[Sentence],
    page: int | None,
    char_offset: int,
) -> Sentence | None:
    """Return the sentence containing ``char_offset`` on ``page``."""
    for sent in sentences:
        if sent.page != page:
            continue
        if sent.start <= char_offset <= sent.end:
            return sent
    return None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\S+", text or "")


def word_context(
    page_text: str,
    start: int,
    end: int,
    words: int = 15,
) -> dict[str, str]:
    """Extract ``words`` tokens before and after a span within a page.

    Context is word-based (not character-based) so OCR spacing noise has
    less impact than padding a fixed character window.
    """
    before = page_text[:start]
    after = page_text[end:]

    before_tokens = _tokenize(before)
    after_tokens = _tokenize(after)

    before_window = " ".join(before_tokens[-words:])
    after_window = " ".join(after_tokens[:words])

    return {
        "before": before_window,
        "after": after_window,
    }