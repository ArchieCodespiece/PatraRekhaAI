"""Document family management and lineage tracking.

Groups related documents (original tender/notice, amendments, corrigenda,
extensions) into families using multiple signals:
- Gmail thread ID
- Subject similarity (token overlap / Jaccard / sequence matching)
- Extracted reference numbers / identifiers
- Document title similarity
"""

from __future__ import annotations

import difflib
import re
from typing import Any


_AMENDMENT_INDICATORS = [
    re.compile(r"\b(corrigendum|amendment|addendum|extension|errata|revised|revision)\b", re.IGNORECASE),
]

_IDENTIFIER_PATTERNS = [
    re.compile(r"\b((?:NIT|RFP|EOI|TENDER|REF)[\s\/:#.-]+[A-Za-z0-9\/-]+)\b", re.IGNORECASE),
    re.compile(r"\b(?:no|number|ref)[\s\/:#.-]+([A-Za-z0-9\/-]+)\b", re.IGNORECASE),
]

_COMMON_WORDS = frozenset({"inviting", "notice", "tender", "document", "online", "portal", "dated"})


def clean_title_for_comparison(title: str) -> str:
    """Normalize title by stripping amendment keywords, dates, and non-alphanumerics."""
    t = title.lower()
    for p in _AMENDMENT_INDICATORS:
        t = p.sub(" ", t)
    t = re.sub(r"\b\d{4}\b", " ", t) # strip standalone years
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return " ".join(t.split())


def compute_title_similarity(title_a: str, title_b: str) -> float:
    """Compute normalized similarity score (0.0 to 1.0) between two document titles."""
    clean_a = clean_title_for_comparison(title_a)
    clean_b = clean_title_for_comparison(title_b)
    if not clean_a or not clean_b:
        return 0.0

    # Token overlap (Jaccard)
    tokens_a = set(clean_a.split())
    tokens_b = set(clean_b.split())
    jaccard = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)

    # Sequence matcher ratio
    seq_ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio()

    return round(0.5 * jaccard + 0.5 * seq_ratio, 3)


def extract_document_identifiers(text: str) -> set[str]:
    """Extract reference/tender/RFP identifiers from text."""
    ids = set()
    for p in _IDENTIFIER_PATTERNS:
        for m in p.finditer(text):
            ident = m.group(1).strip("/- :")
            cleaned_ident = ident.upper()
            if len(cleaned_ident) >= 4 and cleaned_ident.lower() not in _COMMON_WORDS:
                ids.add(cleaned_ident)
    return ids


def detect_document_role(title: str, text: str = "") -> str:
    """Classify the document's role in the family: ORIGINAL, AMENDMENT, CORRIGENDUM, EXTENSION."""
    combined = f"{title}\n{text}".lower()
    if "corrigendum" in combined:
        return "CORRIGENDUM"
    if "extension" in combined:
        return "EXTENSION"
    if "amendment" in combined or "addendum" in combined or "revised" in combined:
        return "AMENDMENT"
    return "ORIGINAL"


def are_documents_in_same_family(
    doc_a: dict[str, Any],
    doc_b: dict[str, Any],
    threshold: float = 0.65,
) -> tuple[bool, str]:
    """Determine whether two documents belong to the same document family.
    
    Signals tested:
    1. Matching Gmail thread_id
    2. Shared extracted reference identifiers
    3. High title/subject similarity
    """
    # 1. Thread ID match
    thread_a = doc_a.get("thread_id")
    thread_b = doc_b.get("thread_id")
    if thread_a and thread_b and thread_a == thread_b:
        return True, "gmail_thread_id"

    # 2. Content hash match
    hash_a = doc_a.get("content_hash")
    hash_b = doc_b.get("content_hash")
    if hash_a and hash_b and hash_a == hash_b:
        return True, "exact_hash"

    # 3. Document reference identifier match
    text_a = f"{doc_a.get('file_heading', '')} {doc_a.get('filename', '')}"
    text_b = f"{doc_b.get('file_heading', '')} {doc_b.get('filename', '')}"
    ids_a = extract_document_identifiers(text_a)
    ids_b = extract_document_identifiers(text_b)
    if ids_a and ids_b and (ids_a & ids_b):
        return True, f"identifier_match: {list(ids_a & ids_b)[0]}"

    # 4. Title / subject similarity
    title_a = doc_a.get("file_heading") or doc_a.get("filename") or ""
    title_b = doc_b.get("file_heading") or doc_b.get("filename") or ""
    sim = compute_title_similarity(title_a, title_b)
    if sim >= threshold:
        return True, f"title_similarity: {sim:.2f}"

    return False, "no_match"


def build_document_family(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cluster documents into families and determine supersession order."""
    families: list[dict[str, Any]] = []
    assigned: set[str] = set()

    # Sort chronologically by created_at or uploaded_at
    sorted_docs = sorted(
        documents,
        key=lambda d: str(d.get("created_at") or d.get("uploaded_at") or ""),
    )

    for i, doc in enumerate(sorted_docs):
        doc_id = str(doc.get("file_id") or i)
        if doc_id in assigned:
            continue

        family_members = [doc]
        assigned.add(doc_id)

        for j in range(i + 1, len(sorted_docs)):
            candidate = sorted_docs[j]
            cand_id = str(candidate.get("file_id") or j)
            if cand_id in assigned:
                continue

            matched, reason = are_documents_in_same_family(doc, candidate)
            if matched:
                family_members.append(candidate)
                assigned.add(cand_id)

        # Build family lineage
        lineage = []
        for idx, member in enumerate(family_members):
            role = detect_document_role(
                member.get("file_heading") or member.get("filename") or ""
            )
            # If later in list and role was classified as ORIGINAL, adjust to AMENDMENT
            if idx > 0 and role == "ORIGINAL":
                role = "AMENDMENT"

            lineage.append({
                "file_id": member.get("file_id"),
                "filename": member.get("filename"),
                "file_heading": member.get("file_heading"),
                "role": role,
                "supersedes": family_members[idx - 1].get("file_id") if idx > 0 else None,
                "created_at": member.get("created_at") or member.get("uploaded_at"),
            })

        families.append({
            "family_id": f"fam_{family_members[0].get('file_id', i)}",
            "root_document_id": family_members[0].get("file_id"),
            "member_count": len(family_members),
            "lineage": lineage,
        })

    return families
