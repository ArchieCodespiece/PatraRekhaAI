"""Deterministic extractive sentence ranking (TF-IDF on numpy).

Ranks page-annotated sentences so a small set of high-value sentences — and
nothing else — is forwarded to the LLM for polishing. Run entirely with
stdlib + numpy: no model downloads, no API cost, deterministic for a given
input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

from sentence_indexer import Sentence, index_pages

_TOKEN = re.compile(r"[\w\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF"
                    r"\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF"
                    r"\u0D00-\u0D7F\u0600-\u06FF]+", re.UNICODE)

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "by", "from", "at", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "his", "her",
    "their", "our", "your", "we", "you", "they", "i", "he", "she", "not",
    "will", "shall", "may", "must", "can", "could", "would", "should",
    "has", "have", "had", "having", "but", "if", "then", "than", "also",
    "per", "all", "any", "each", "other", "more", "most", "etc", "per",
    "एवं", "तथा", "और", "का", "के", "की", "को", "में", "के", "है", "हैं",
}


@dataclass
class RankedSentence:
    page: int | None
    text: str
    score: float
    source_index: int


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def _tf_idf_matrix(sentences: list[Sentence]) -> tuple[np.ndarray, list[str]]:
    """Build the TF-IDF feature matrix over sentence tokens.

    Returns (matrix, vocabulary). Each row is normalised to unit length so
    long sentences do not automatically dominate.
    """
    raw_rows: list[list[str]] = []
    doc_corpus: list[list[str]] = []

    for sent in sentences:
        terms = tokenize(sent.text)
        significant = [t for t in terms if t not in _STOPWORDS]
        raw_rows.append(terms)
        if set(significant):
            doc_corpus.append(significant)

    vocab: list[str] = []
    vocab_index: dict[str, int] = {}
    for row in doc_corpus:
        for token in row:
            if token not in vocab_index:
                vocab_index[token] = len(vocab)
                vocab.append(token)

    if not vocab:
        empty = np.zeros((len(sentences), 1), dtype=np.float64)
        return empty, ["<empty>"]

    # Document frequency per term.
    doc_freq = np.zeros(len(vocab), dtype=np.float64)
    for row in doc_corpus:
        uniq = set(row)
        for token in uniq:
            doc_freq[vocab_index[token]] += 1.0

    num_docs = max(1, len(doc_corpus))
    idf = np.log(1.0 + num_docs / (1.0 + doc_freq))

    matrix = np.zeros((len(sentences), len(vocab)), dtype=np.float64)
    for row_idx, terms in enumerate(raw_rows):
        tf: dict[str, int] = {}
        for token in terms:
            if token in vocab_index:
                tf[token] = tf.get(token, 0) + 1.0
        row = matrix[row_idx]
        for token, count in tf.items():
            row[vocab_index[token]] = count * idf[vocab_index[token]]

    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    matrix = matrix / norms[:, None]

    return matrix, vocab


def rank_sentences(
    sentences: list[Sentence] | None = None,
    pages: list[dict] | None = None,
    top_k: int = 20,
) -> list[RankedSentence]:
    """Rank sentences by TF-IDF salience, returning the top-k.

    Accepts either indexed ``Sentence`` objects or page dicts
    (``{"page": n, "text": "..."}``).

    A small position bonus keeps early sentences (often statement-of-purpose
    or preambles) competitive, and a length penalty suppresses one-word OCR
    fragments.
    """
    if np is None:
        raise ImportError("numpy is required for extractive_rank")

    if sentences is None:
        sentences = index_pages(pages or [])

    if not sentences:
        return []

    matrix, _ = _tf_idf_matrix(sentences)
    scores = matrix.sum(axis=1)

    # Position bonus: linear decay from the first sentence.
    if len(sentences) > 1:
        pos_bonus = np.linspace(0.15, 0.0, num=len(sentences))
        scores = scores + pos_bonus

    # Length penalty: very short fragments are usually OCR noise.
    lengths = np.array(
        [max(1, len(tokenize(sent.text))) for sent in sentences],
        dtype=np.float64,
    )
    scores = scores * np.minimum(1.0, lengths / 5.0)

    ranked_indices = np.argsort(-scores)

    chosen = ranked_indices[:top_k]
    chosen_sorted = sorted(chosen.tolist())

    return [
        RankedSentence(
            page=sentences[idx].page,
            text=sentences[idx].text,
            score=float(scores[idx]),
            source_index=idx,
        )
        for idx in chosen_sorted
    ]