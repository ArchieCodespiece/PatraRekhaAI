"""
Multi-strategy retrieval for the workflow layer.

Strategies (all scoped to the authenticated user's Pinecone namespace):

1. Coverage fetch  - enumerate every chunk of a document (bounded).
2. Semantic search - per-section embeddings over each selected document.
3. Keyword pass    - plain term-overlap scan over the coverage chunk list.

Results are normalized to :class:`ChunkRecord` and deduplicated by vector id
so the comparison synthesizer never sees duplicate evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import (
    MAX_COVERAGE_CHUNKS,
    NEUTRAL_COVERAGE_QUERY,
    WORKFLOW_TOP_K_PER_DOCUMENT,
)

STOPWORDS = {
    "the","a","an","and","or","but","of","to","in","is","are","was","were",
    "for","with","on","at","by","from","as","that","this","which","will",
    "shall","not","be","been","being","shall","may","must","has","have",
    "had","it","its","their","them","they","he","she","we","you","who",
    "whom","whose","party","parties","document","documents","agreement",
    "clause","clauses","section","does","do","did","should","would","can",
    "could","also","than","then","there","here","about","between","per",
    "each","both","including","such","whether","after","before","unless",
}


@dataclass
class ChunkRecord:
    chunk_id: str = ""
    document_name: str = ""
    document_id: str = ""
    text: str = ""
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    section: Optional[str] = None
    chunk_index: Optional[int] = None
    score: float = 0.0
    strategy: str = "semantic"


@dataclass
class DocumentCoverage:
    records: List[ChunkRecord] = field(default_factory=list)
    complete: bool = True
    sections: List[str] = field(default_factory=list)

    def section_map(self) -> Dict[str, List[ChunkRecord]]:
        grouped: Dict[str, List[ChunkRecord]] = {}

        for record in self.records:
            label = record.section or "General"
            grouped.setdefault(label, []).append(record)

        return grouped


# ============================================================================
# Normalization
# ============================================================================

def _match_meta(match: Any) -> Dict[str, Any]:
    if isinstance(match, dict):
        metadata = match.get("metadata") or {}
    else:
        metadata = getattr(match, "metadata", {}) or {}

    return metadata if isinstance(metadata, dict) else {}


def _match_id(match: Any) -> str:
    if isinstance(match, dict):
        return str(match.get("id") or "")
    return str(getattr(match, "id", "") or "")


def _match_score(match: Any) -> float:
    if isinstance(match, dict):
        return float(match.get("score") or 0)
    return float(getattr(match, "score", 0) or 0)


def record_from_match(
    match: Any,
    strategy: str = "semantic",
) -> Optional[ChunkRecord]:
    metadata = _match_meta(match)
    text = str(metadata.get("text") or "").strip()

    if not text:
        return None

    def _int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return ChunkRecord(
        chunk_id=_match_id(match),
        document_name=str(metadata.get("document_name") or ""),
        document_id=str(metadata.get("document_id") or ""),
        text=text,
        page_start=_int(metadata.get("page_start")),
        page_end=_int(metadata.get("page_end")),
        section=metadata.get("section"),
        chunk_index=_int(metadata.get("chunk_index")),
        score=_match_score(match),
        strategy=strategy,
    )


def matches_from_result(result: Any) -> List[Any]:
    if isinstance(result, dict):
        return result.get("matches", []) or []
    return list(getattr(result, "matches", []) or [])


# ============================================================================
# Strategy 1 - exhaustive coverage
# ============================================================================

def fetch_document_coverage(
    document_name: str,
    embedder: Any,
    namespace: Optional[str] = None,
    max_chunks: int = MAX_COVERAGE_CHUNKS,
) -> DocumentCoverage:
    """
    Enumerate all chunks of a single document via a Pinecone metadata filter.

    Completeness is limited by ``max_chunks``; when fewer chunks are
    returned, the coverage is exhaustive.
    """

    from vectorstore.config import USE_NAMESPACES
    from vectorstore.pinecone_store import PineconeStore

    ns = namespace if (USE_NAMESPACES and namespace) else None

    store = PineconeStore(namespace=ns)
    neutral_embedding = embedder.embed_text(
        NEUTRAL_COVERAGE_QUERY
    )

    result = store.index.query(
        vector=neutral_embedding,
        top_k=max_chunks,
        include_metadata=True,
        namespace=ns,
        filter={"document_name": document_name},
    )

    matches = matches_from_result(result)

    records = [
        record
        for record in (
            record_from_match(match, strategy="coverage")
            for match in matches
        )
        if record is not None
    ]

    records.sort(
        key=lambda record:
            (record.chunk_index if record.chunk_index is not None else 0)
    )

    sections: List[str] = []
    for record in records:
        if record.section and record.section not in sections:
            sections.append(record.section)

    return DocumentCoverage(
        records=records,
        complete=len(matches) < max_chunks,
        sections=sections,
    )


# ============================================================================
# Document-name resolution
# ============================================================================
#
# Document names stored in the index are not consistent: older ingestions
# used "{file_id}-{stem}", newer ones use a stripped "{stem}" (also without
# any ".pdf" extension). Before querying, resolve the name that actually
# exists in the index so coverage and semantic searches can agree on it.

FILE_ID_PREFIX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}[-_]?"
)

SHORT_ID_PREFIX = re.compile(
    r"^[0-9a-fA-F]{12}[-_]?"
)


def alternate_document_names(
    document_name: str,
) -> List[str]:
    """
    Ordered list of plausible Pinecone document_name values for a single
    logical document: the name as given, without its file extension, and
    with any leading file_id/short-id prefixes stripped.
    """

    from pathlib import Path

    candidates: List[str] = []
    seen: set = set()

    def add(value: Optional[str]) -> None:
        value = str(value or "").strip()

        if value and value not in seen:
            seen.add(value)
            candidates.append(value)

    add(document_name)
    add(Path(document_name).stem)

    stripped = str(document_name or "")
    changed = True

    while changed:
        changed = False

        for pattern in (FILE_ID_PREFIX, SHORT_ID_PREFIX):
            new_value = pattern.sub("", stripped).lstrip("-_")

            if new_value != stripped:
                stripped = new_value
                changed = True

    add(stripped)
    add(Path(stripped).stem)

    return candidates


def fetch_document_coverage_with_fallback(
    document_name: str,
    embedder: Any,
    namespace: Optional[str] = None,
    max_chunks: int = MAX_COVERAGE_CHUNKS,
) -> tuple[DocumentCoverage, str]:
    """
    Like :func:`fetch_document_coverage`, but retries alternative name
    forms (extension / file_id prefix) when the exact name returns nothing.

    Returns ``(coverage, actual_name)`` where ``actual_name`` is the index
    name that produced records (falling back to the requested name).
    """

    actual_name = document_name
    coverage = fetch_document_coverage(
        document_name=document_name,
        embedder=embedder,
        namespace=namespace,
        max_chunks=max_chunks,
    )

    if coverage.records:
        return coverage, actual_name

    for candidate in alternate_document_names(document_name):
        if candidate == document_name:
            continue

        coverage = fetch_document_coverage(
            document_name=candidate,
            embedder=embedder,
            namespace=namespace,
            max_chunks=max_chunks,
        )

        if coverage.records:
            actual_name = candidate
            return coverage, actual_name

    # Namespace blindspot: namespaced vectors may be missing from the user
    # namespace but present in the default namespace for pre-namespace data.
    if namespace:
        coverage, actual_name = fetch_document_coverage_with_fallback(
            document_name=document_name,
            embedder=embedder,
            namespace=None,
            max_chunks=max_chunks,
        )

        if coverage.records:
            return coverage, actual_name

    return DocumentCoverage(), document_name


def resolve_document_name(
    document_name: str,
    embedder: Any,
    namespace: Optional[str] = None,
) -> str:
    """
    Return the document_name value that actually returns chunks from the
    index, or the requested name when nothing matches.
    """

    _, actual_name = fetch_document_coverage_with_fallback(
        document_name=document_name,
        embedder=embedder,
        namespace=namespace,
        max_chunks=5,
    )

    return actual_name


# ============================================================================
# Strategy 2 - semantic sub-queries
# ============================================================================

def semantic_search_documents(
    document_names: List[str],
    query_embedding: List[float],
    namespace: Optional[str],
    top_k: int = WORKFLOW_TOP_K_PER_DOCUMENT,
) -> List[ChunkRecord]:
    from vectorstore.retrieval import get_chunks_from_documents

    result = get_chunks_from_documents(
        document_names=document_names,
        query_embedding=query_embedding,
        top_k=top_k,
        namespace=namespace,
    )

    return [
        record
        for record in (
            record_from_match(match, strategy="semantic")
            for match in matches_from_result(result)
        )
        if record is not None
    ]


# ============================================================================
# Strategy 3 - keyword scan (no vector index)
# ============================================================================

def tokenize(text: str) -> set:
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))


def keyword_scan(
    query: str,
    records: List[ChunkRecord],
    top_k: int = 6,
) -> List[ChunkRecord]:
    query_terms = tokenize(query) - STOPWORDS

    if not query_terms or not records:
        return []

    ranked: List[ChunkRecord] = []
    seen = set()

    for record in records:
        record_terms = tokenize(record.text)
        overlap = len(query_terms & record_terms)

        if overlap <= 0 or record.chunk_id in seen:
            continue

        seen.add(record.chunk_id)
        record.score = float(overlap) / max(1, len(query_terms))
        record.strategy = "keyword"
        ranked.append(record)

    ranked.sort(key=lambda record: -record.score)

    return ranked[:top_k]


# ============================================================================
# Dedupe / merge
# ============================================================================

def merge_records(
    *record_lists: List[ChunkRecord],
    max_records: int = 10,
) -> List[ChunkRecord]:
    """
    Merge several strategy results, deduplicating by vector id.
    Priority: semantic > keyword > coverage.
    """

    by_id: Dict[str, ChunkRecord] = {}
    priority = {"semantic": 0, "keyword": 1, "coverage": 2}

    for records in record_lists:
        for record in records:
            if not record.chunk_id:
                continue

            existing = by_id.get(record.chunk_id)

            if existing is None:
                by_id[record.chunk_id] = record
                continue

            if priority.get(record.strategy, 9) < priority.get(
                existing.strategy, 9
            ):
                by_id[record.chunk_id] = record

    merged = sorted(
        by_id.values(),
        key=lambda record: (
            -record.score,
            (record.chunk_index if record.chunk_index is not None else 0),
        ),
    )

    return merged[:max_records]


def group_records_by_document(
    records: List[ChunkRecord],
) -> Dict[str, List[ChunkRecord]]:
    grouped: Dict[str, List[ChunkRecord]] = {}

    for record in records:
        grouped.setdefault(record.document_name, []).append(record)

    return grouped


def overlap_ratio(a_text: str, b_text: str) -> float:
    a_terms = tokenize(a_text) - STOPWORDS
    b_terms = tokenize(b_text) - STOPWORDS

    if not a_terms or not b_terms:
        return 0.0

    return len(a_terms & b_terms) / max(1, min(len(a_terms), len(b_terms)))