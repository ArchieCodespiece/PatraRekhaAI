"""
PLAN -> RETRIEVE -> COMPARE -> VERIFY -> RESULT orchestration.

This module drives a thorough, offline-style comparison of two selected
documents. It yields a stream of :class:`WorkflowEvent` so the chat
endpoint can surface progress; the final event carries the canonical
:class:`ComparisonResult` plus a rendered markdown chat answer.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

from .config import (
    EVIDENCE_PER_ROW_PER_DOCUMENT,
    COMPARE_MAX_WORKERS,
    COMPARE_MODEL,
    COMPARE_REPAIR_ATTEMPTS,
    FAST_COMPARE_MODEL,
    MAX_WORKFLOW_SECTIONS,
    NEUTRAL_SCAFFOLD_SECTIONS,
    OVERVIEW_MODEL,
    SEEDED_SECTIONS,
    WORKFLOW_MAX_CONTEXT_CHARS,
    WORKFLOW_TOP_K_PER_DOCUMENT,
)
from .llm import chat_json, chat_json_with_retry
from .models import (
    ComparisonResult,
    ComparisonRow,
    ComparisonSection,
    Evidence,
)
from .retrieval import (
    ChunkRecord,
    DocumentCoverage,
    STOPWORDS,
    fetch_document_coverage,
    keyword_scan,
    merge_records,
    overlap_ratio,
    semantic_search_documents,
    tokenize,
)
from .state import WorkflowState
from .verify import verify_result

COMPARER_SYSTEM = (
    "You are a precise document-comparison analyst. Compare the two "
    "selected documents using ONLY the provided context snippets. "
    "Base every value strictly on the snippets; never invent facts. "
    "If a topic is absent from a document write 'Not mentioned'.\n\n"
    'Respond ONLY with JSON matching exactly this schema:\n'
    '{"rows": [{"topic": "short label", ' 
    '"document_a": "value or fact from document A", '
    '"document_b": "value or fact from document B", '
    '"difference": true or false, '
    '"confidence": "high" | "medium" | "low", '
    '"impact": "low" | "medium" | "high" | "unknown"}]}\n\n'
    "- topic: a short, specific heading for the compared item.\n"
    "- document_a/document_b: compact factual values (dates, numbers, "
    "short summaries). Do not paste long quotes.\n"
    "- difference: true when the two documents differ on this topic.\n"
    "- impact: your read of how material a difference is.\n"
    'Keep rows for the requested section ONLY. Return valid JSON only, '
    "no markdown fences, no commentary outside the JSON."
)

PLANNER_SYSTEM = (
    "You plan a thorough, systematic comparison of two documents. "
    "Return ONLY JSON:\n"
    '{"sections": [{"name": "Section title", '
    '"focus": "one-line purpose", '
    '"sub_queries": ["targeted retrieval query 1", "query 2"]}]}\n\n'
    "Rules:\n"
    "- Base your section list on the observed section lists provided in "
    "the request. Observed sections are the real headings in the "
    "documents; they must lead the plan, in the order given.\n"
    "- Never include a topic that is absent from the documents.\n"
    "- The optional 'common sections to consider' list applies ONLY if "
    "the topic appears in the observed lists or the user's request calls "
    "for it.\n"
    "- If no observed sections were detected, plan from the content "
    "preview provided in the request.\n"
    "- Keep the total to at most 8 sections; 1 to 3 sub_queries per "
    "section, each phrased to retrieve evidence about that section from "
    "both documents."
)

TOPIC_PLANNER_SYSTEM = (
    "You identify concrete comparison topics from two documents that do "
    "not have reliable section headings. Return ONLY JSON:\n"
    '{"topics": ["specific topic 1", "specific topic 2"]}\n\n'
    "Rules:\n"
    "- Topics must be factual attributes actually visible in the snippets.\n"
    "- Prefer shared comparable attributes, labels, facts, entities, dates, "
    "numbers, categories, status, places, obligations, or properties.\n"
    "- Do not return generic topics like Overview, Key Findings, Summary, "
    "Facts, Details, Similarities, or Differences.\n"
    "- Keep 3 to 8 short topics. Return valid JSON only."
)

OVERVIEW_SYSTEM = (
    "You summarize a completed document comparison for a chat answer. "
    "Return ONLY JSON:\n"
    '{"overview": "1 to 3 sentences, plain language, highlighting the '
    'most consequential differences and how many were found."}\n'
    "Match the tone and language of the user's original request."
)

REPAIR_HINTS = [
    "Ensure every field is present and has the correct type. "
    "difference must be a JSON boolean, confidence one of high/medium/low, "
    "impact one of low/medium/high/unknown. Output valid JSON only.",
    "Re-check the JSON syntax and schema. Return only "
    '{"rows":[{"topic":..., "document_a":..., "document_b":..., '
    '"difference":..., "confidence":..., "impact":...}]}.',
]

GENERIC_SECTION_NAMES = {
    "full document",
    "overview",
    "key details",
    "key findings",
    "notable differences",
    "facts figures",
    "facts & figures",
    "summary",
    "general",
}

FALLBACK_FACT_SECTION = "Extracted Facts"

FACT_TOPIC_HINTS = [
    "Scientific Name",
    "Classification",
    "Habitat",
    "Range",
    "Diet",
    "Size",
    "Weight",
    "Length",
    "Lifespan",
    "Behavior",
    "Social Structure",
    "Appearance",
    "Population",
    "Conservation Status",
    "Threats",
]

HEADING_PATTERNS = [
    re.compile(r"^#{1,6}\s+(.+?)\s*$"),
    re.compile(r"^(\d+(?:\.\d+)*\.?)\s+(.+?)\s*$"),
    re.compile(
        r"^(?:section|article|clause|part|schedule|exhibit)\s+"
        r"([ivx0-9]+|[a-z]+)[.:]?\s*(.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"^(.{2,60}):\s*$"),
    re.compile(r"^[A-Z][A-Z0-9 &/'.,()\-]{2,80}$"),
]


@dataclass
class WorkflowEvent:
    kind: str  # "progress" | "complete"
    message: str = ""
    section_index: int = 0
    section_total: int = 0
    result: Optional[ComparisonResult] = None
    coverage: Optional[dict] = None
    chat_answer: str = ""


# ============================================================================
# Context formatting
# ============================================================================

def format_records_context(
    records: List[ChunkRecord],
    max_chars: int = WORKFLOW_MAX_CONTEXT_CHARS,
) -> str:
    blocks: List[str] = []
    used_chars = 0

    for record in records:
        text = (record.text or "").strip()

        if not text:
            continue

        document_name = record.document_name or "Unknown document"

        page_label = ""

        if record.page_start is not None:
            page_end = (
                record.page_end
                if record.page_end is not None
                else record.page_start
            )

            if record.page_start != page_end:
                page_label = (
                    f" | Pages: {record.page_start}-{page_end}"
                )
            else:
                page_label = f" | Page: {record.page_start}"

        block = (
            f"[Document: {document_name}{page_label}]\n{text}"
        )

        remaining = max_chars - used_chars

        if remaining <= 0:
            break

        if len(block) > remaining:
            block = block[:remaining].rstrip()

        if not block:
            break

        blocks.append(block)
        used_chars += len(block) + 2

    return "\n\n".join(blocks)


def _clean_section_name(value: Any) -> str:
    name = str(value or "").strip()
    name = re.sub(r"^#{1,6}\s+", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -:\t")
    return name[:120]


def _is_generic_section_name(value: str) -> bool:
    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").lower(),
    ).strip()

    return normalized in GENERIC_SECTION_NAMES


def _looks_like_heading(value: str) -> bool:
    name = _clean_section_name(value)

    if not name or _is_generic_section_name(name):
        return False

    words = name.split()

    if len(words) > 14 or len(name) > 120:
        return False

    if name.endswith((".", ",", ";")):
        return False

    return True


def _valid_heading_form(name: str, raw_line: str) -> bool:
    words = name.split()

    if len(words) > 7:
        return False

    if name.endswith((".", ",", ";")):
        return False

    # Uppercase lines must carry at least two alphabetic tokens, otherwise
    # sentence-fragment OCR noise ("A", "THE") slips through.
    if raw_line == raw_line.upper():
        alphabetic_tokens = [
            token
            for token in raw_line.split()
            if any(char.isalpha() for char in token)
        ]

        if len(alphabetic_tokens) < 2:
            return False

    return True


def _extract_headings_from_text(text: str) -> List[str]:
    headings: List[str] = []

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        candidate = ""

        markdown_match = HEADING_PATTERNS[0].match(line)
        if markdown_match:
            candidate = markdown_match.group(1)
        else:
            numbered_match = HEADING_PATTERNS[1].match(line)
            if numbered_match:
                candidate = (
                    numbered_match.group(1).rstrip(".")
                    + " "
                    + numbered_match.group(2)
                )
            else:
                section_match = HEADING_PATTERNS[2].match(line)
                if section_match:
                    candidate = (
                        section_match.group(2)
                        if section_match.group(2)
                        else line
                    )
                else:
                    colon_match = HEADING_PATTERNS[3].match(line)
                    if colon_match:
                        candidate = colon_match.group(1)
                    else:
                        caps_match = HEADING_PATTERNS[4].match(line)
                        if caps_match:
                            candidate = line

        candidate = _clean_section_name(candidate)

        if (
            _looks_like_heading(candidate)
            and _valid_heading_form(candidate, line)
        ):
            headings.append(candidate)

    return headings


def _append_unique_section(
    sections: List[str],
    section_name: Any,
) -> None:
    cleaned = _clean_section_name(section_name)

    if not _looks_like_heading(cleaned):
        return

    seen = {section.lower() for section in sections}

    if cleaned.lower() not in seen:
        sections.append(cleaned)


def _observed_sections_from_coverages(
    coverages: Dict[str, DocumentCoverage],
) -> List[str]:
    sections: List[str] = []

    for coverage in coverages.values():
        for section_name in coverage.sections:
            _append_unique_section(sections, section_name)

    # Older or weakly parsed vectors can have empty/"Full Document" metadata.
    # Supplement with headings recovered from the chunk text itself; the
    # generic-name filter keeps "Full Document" style junk out of both sources.
    for coverage in coverages.values():
        for record in coverage.records:
            for heading in _extract_headings_from_text(record.text):
                _append_unique_section(sections, heading)

    return sections[:40]


def _plan_from_observed_sections(
    observed_sections: List[str],
) -> List[Dict[str, Any]]:
    return [
        {
            "name": section_name,
            "focus": section_name,
            "sub_queries": [section_name],
        }
        for section_name in observed_sections[:MAX_WORKFLOW_SECTIONS]
    ]


def _fallback_fact_plan() -> List[Dict[str, Any]]:
    return [
        {
            "name": FALLBACK_FACT_SECTION,
            "focus": (
                "Compare concrete facts, attributes, quantities, dates, "
                "entities, and other stated details from the documents."
            ),
            "sub_queries": [
                "facts attributes quantities dates entities details",
            ],
            "use_coverage": True,
        }
    ]


def _keyword_topics_from_preview(preview_text: str) -> List[str]:
    preview_tokens = tokenize(preview_text)
    topics: List[str] = []

    for topic in FACT_TOPIC_HINTS:
        topic_tokens = tokenize(topic) - STOPWORDS

        if topic_tokens and topic_tokens & preview_tokens:
            _append_unique_section(topics, topic)

    return topics


def _plan_from_topics(topics: List[str]) -> List[Dict[str, Any]]:
    return [
        {
            "name": topic,
            "focus": f"Compare the documents' stated facts about {topic}.",
            "sub_queries": [topic],
            "use_coverage": True,
        }
        for topic in topics[:MAX_WORKFLOW_SECTIONS]
    ]


def _infer_topic_plan(
    state: WorkflowState,
    preview_text: str,
) -> List[Dict[str, Any]]:
    preview_tokens = tokenize(preview_text)
    topics: List[str] = []

    try:
        payload = chat_json_with_retry(
            TOPIC_PLANNER_SYSTEM,
            (
                "User request: " + state.query + "\n\n"
                "Documents: "
                + ", ".join(state.display_names())
                + "\n\n"
                "Document snippets:\n"
                + preview_text
            ),
            [
                "Return JSON with a top-level 'topics' array of concrete "
                "topics that appear in the snippets. Do not use generic "
                "overview/summary/findings labels.",
            ],
            attempts=2,
            model=(
                COMPARE_MODEL
                if state.think_mode
                else FAST_COMPARE_MODEL
            ),
        )

        for raw_topic in payload.get("topics") or []:
            topic = _clean_section_name(raw_topic)
            topic_tokens = tokenize(topic) - STOPWORDS

            if not topic_tokens or not (topic_tokens & preview_tokens):
                continue

            _append_unique_section(topics, topic)

    except Exception:
        pass

    for topic in _keyword_topics_from_preview(preview_text):
        _append_unique_section(topics, topic)

    if topics:
        return _plan_from_topics(topics)

    return _fallback_fact_plan()


# ============================================================================
# Evidence attachment
# ============================================================================

def _pick_evidence(
    claim: str,
    records: List[ChunkRecord],
    limit: int = EVIDENCE_PER_ROW_PER_DOCUMENT,
) -> List[ChunkRecord]:
    if not records:
        return []

    scored = [
        (overlap_ratio(claim, record.text), record)
        for record in records
    ]

    scored.sort(key=lambda pair: (-pair[0], -(pair[1].score or 0)))

    chosen: List[ChunkRecord] = []
    seen = set()

    for _, record in scored:
        if record.chunk_id in seen:
            continue
        seen.add(record.chunk_id)
        chosen.append(record)
        if len(chosen) >= limit:
            break

    if not chosen:
        chosen = records[:limit]

    return chosen


def _attach_evidence(
    row: ComparisonRow,
    section_records_by_doc: Dict[str, List[ChunkRecord]],
    display_by_pinecone: dict,
) -> ComparisonRow:
    for role, key in (("A", "document_a"), ("B", "document_b")):
        display_names = [name for name in display_by_pinecone.values()]

        if not display_names:
            continue

        display = display_names[0] if role == "A" else display_names[-1]
        pinecone = _pinecone_for_display(display, display_by_pinecone)
        records = section_records_by_doc.get(pinecone, [])
        claim = getattr(row, key)

        selected = _pick_evidence(claim, records)

        for record in selected:
            evidence = Evidence(
                document=display,
                page_start=record.page_start,
                page_end=record.page_end,
                section=record.section,
                text=record.text,
                strategy=record.strategy,
            )

            if not any(
                item.text == record.text
                for item in row.evidence
            ):
                row.evidence.append(evidence)

    return row


def _pinecone_for_display(
    display: str,
    display_by_pinecone: dict,
) -> str:
    for pinecone, name in display_by_pinecone.items():
        if name == display:
            return pinecone

    return display


# ============================================================================
# Planner
# ============================================================================

def _relevant_seeds(
    observed_sections: List[str],
    query: str,
) -> List[str]:
    """
    Seeds offered to the planner, gated by token overlap with the real
    document headings or the user's own query wording.

    Nothing observed + no query terms -> no seeds at all; the plan must be
    driven by the content preview. Contract sections are never defaulted to.
    """

    pool: set = set(tokenize(query) - STOPWORDS)

    for heading in observed_sections:
        pool |= tokenize(heading)

    if not pool:
        return []

    return [
        seed
        for seed in SEEDED_SECTIONS
        if tokenize(seed) & pool
    ]


def _reorder_plan(
    cleaned: List[Dict[str, Any]],
    observed_sections: List[str],
    query: str,
) -> List[Dict[str, Any]]:
    """
    Deterministic post-processing of the LLM plan: sections that match the
    documents' own headings surface first, and pure seed-echo sections with
    zero overlap with the documents/query are dropped.
    """

    pool: set = set(tokenize(query) - STOPWORDS)

    for heading in observed_sections:
        pool |= tokenize(heading)

    if not pool:
        return cleaned

    def overlap_tokens(entry: Dict[str, Any]) -> set:
        return tokenize(entry.get("name") or "") & pool

    seed_token_sets = {
        frozenset(tokenize(seed))
        for seed in SEEDED_SECTIONS
    }

    ranked = sorted(
        enumerate(cleaned),
        key=lambda pair: (-len(overlap_tokens(pair[1])), pair[0]),
    )

    kept: List[Dict[str, Any]] = []

    for _, entry in ranked:
        name_tokens = tokenize(entry.get("name") or "")

        if overlap_tokens(entry):
            kept.append(entry)
            continue

        if name_tokens and frozenset(name_tokens) in seed_token_sets:
            # Pure seed echo unrelated to the documents -> drop.
            continue

        kept.append(entry)

    return kept or cleaned[:MAX_WORKFLOW_SECTIONS]


def _plan_sections(
    state: WorkflowState,
    observed_sections: List[str],
    preview_text: str = "",
) -> List[Dict[str, Any]]:
    if observed_sections:
        return _plan_from_observed_sections(observed_sections)

    if preview_text:
        return _infer_topic_plan(state, preview_text)

    relevant_seeds = _relevant_seeds(
        observed_sections,
        state.query,
    )

    common_line = (
        ", ".join(relevant_seeds) if relevant_seeds
        else "(none - base the plan on the observed sections only)"
    )

    preview_block = (
        "Content preview from the documents:\n" + preview_text
        if preview_text
        else ""
    )

    try:
        payload = chat_json_with_retry(
            PLANNER_SYSTEM,
            (
                "User request: " + state.query + "\n\n"
                "Documents: "
                + ", ".join(state.display_names())
                + "\n\n"
                "Observed sections in the documents: "
                + (", ".join(observed_sections) or "none detected")
                + "\n\n"
                "Common sections to consider: "
                + common_line
                + "\n\n"
                + preview_block
            ),
            [
                "Return JSON with a top-level 'sections' array; "
                "each entry has name, focus, sub_queries.",
            ],
            attempts=3,
            model=(
                COMPARE_MODEL
                if state.think_mode
                else FAST_COMPARE_MODEL
            ),
        )

        sections = payload.get("sections") or []

        cleaned = []

        for entry in sections:
            if not isinstance(entry, dict):
                continue

            name = str(entry.get("name") or "").strip()

            if not name:
                continue

            sub_queries = entry.get("sub_queries") or []

            if not isinstance(sub_queries, list):
                sub_queries = [str(sub_queries)]

            sub_queries = [
                str(sub_query).strip()
                for sub_query in sub_queries
                if str(sub_query).strip()
            ][:3]

            if not sub_queries:
                sub_queries = [name]

            cleaned.append(
                {
                    "name": name[:80],
                    "focus": str(entry.get("focus") or name)[:160],
                    "sub_queries": sub_queries,
                }
            )

        if cleaned:
            return _reorder_plan(
                cleaned,
                observed_sections,
                state.query,
            )[:MAX_WORKFLOW_SECTIONS]

    except Exception:
        pass

    # Fallback plan: observed-first, seeds fill only the remaining slots.
    fallback: List[Dict[str, Any]] = []

    for name in seeded_fallback(observed_sections):
        fallback.append(
            {
                "name": name,
                "focus": name,
                "sub_queries": ["{name}".format(name=name)],
            }
        )

    if not fallback:
        for name in NEUTRAL_SCAFFOLD_SECTIONS:
            fallback.append(
                {
                    "name": name,
                    "focus": name,
                    "sub_queries": [name],
                }
            )

    return fallback[:MAX_WORKFLOW_SECTIONS]


def seeded_fallback(observed_sections: List[str]) -> List[str]:
    if not observed_sections:
        return list(NEUTRAL_SCAFFOLD_SECTIONS)

    observed_tokens: set = set()

    for heading in observed_sections:
        observed_tokens |= tokenize(heading)

    ordered = [
        "Parties",
        "Dates",
        "Pricing",
        "Responsibilities",
        "Termination",
        "Penalties",
        "Confidentiality",
        "Liability",
        "Governing Law",
    ]

    gaps = [
        seed
        for seed in ordered
        if tokenize(seed) & observed_tokens
    ]

    merged = list(dict.fromkeys(observed_sections + gaps))
    return merged[:MAX_WORKFLOW_SECTIONS]


# ============================================================================
# Compare executor (generator)
# ============================================================================

def _build_section_context(
    section: Dict[str, Any],
    state: WorkflowState,
    coverages: Dict[str, DocumentCoverage],
    embedder: Any,
) -> Dict[str, List[ChunkRecord]]:
    records_by_doc: Dict[str, List[ChunkRecord]] = {}
    display_by_pinecone = state.display_by_pinecone()

    for display, pinecone in state.doc_pairs:
        coverage = coverages.get(pinecone)
        coverage_records = coverage.records if coverage else []

        collected: List[ChunkRecord] = []

        if section.get("use_coverage"):
            records_by_doc[pinecone] = merge_records(
                coverage_records,
                max_records=10,
            )
            continue

        for sub_query in section["sub_queries"]:
            query_embedding = embedder.embed_text(
                section["name"] + " " + sub_query
            )

            collected.extend(
                semantic_search_documents(
                    document_names=[pinecone],
                    query_embedding=query_embedding,
                    namespace=state.namespace,
                    top_k=WORKFLOW_TOP_K_PER_DOCUMENT,
                )
            )

        collected.extend(
            keyword_scan(
                " ".join(section["sub_queries"]),
                list(coverage_records),
                top_k=6,
            )
        )

        # Section-metadata match from the coverage list.
        section_tokens = {
            token
            for token in section["name"].lower().replace("-", " ").split()
            if token
        }

        collected_ids = {item.chunk_id for item in collected}

        for record in coverage_records:
            record_section = (record.section or "").lower()

            if not record_section:
                continue

            forward = any(
                token in record_section
                for token in section_tokens
            )
            reverse = any(
                token in section["name"].lower()
                for token in record_section.split()
            )

            if (forward or reverse) and record.chunk_id not in collected_ids:
                collected.append(record)
                collected_ids.add(record.chunk_id)

        records_by_doc[pinecone] = merge_records(
            collected,
            max_records=10,
        )

    return records_by_doc


def _compare_section(
    section: Dict[str, Any],
    state: WorkflowState,
    records_by_doc: Dict[str, List[ChunkRecord]],
    display_by_pinecone: dict,
) -> List[ComparisonRow]:
    context_parts = [
        format_records_context(
            records_by_doc.get(pinecone, []),
            max_chars=max(
                1000,
                WORKFLOW_MAX_CONTEXT_CHARS // max(1, len(state.doc_pairs)),
            ),
        )
        for _, pinecone in state.doc_pairs
    ]

    names = state.display_names()
    doc_a = names[0] if names else "Document A"
    doc_b = names[-1] if len(names) > 1 else "Document B"
    fallback_instruction = ""

    if section.get("use_coverage") and section["name"] == FALLBACK_FACT_SECTION:
        fallback_instruction = (
            "\nThis document has no reliable section headings. Extract "
            "multiple concrete comparable facts from the provided context "
            "instead of returning a generic overview row. Use concise topics "
            "such as habitat, size, diet, lifespan, range, behavior, status, "
            "or any other facts actually present in the snippets. Do not "
            "return a row where both documents are 'Not mentioned'.\n"
        )
    elif section.get("use_coverage"):
        fallback_instruction = (
            "\nThis topic was inferred from the documents because no "
            "reliable section headings were available. Compare only facts "
            "about this topic. Do not return a row where both documents are "
            "'Not mentioned'.\n"
        )

    user_prompt = (
        "User request: " + state.query + "\n\n"
        "Section being compared: " + section["name"] + "\n"
        "Focus: " + section["focus"] + "\n\n"
        + fallback_instruction
        + "Context for " + doc_a + ":\n"
        + (context_parts[0] if context_parts else "No context")
        + "\n\n"
        + "Context for " + doc_b + ":\n"
        + (context_parts[-1] if len(context_parts) > 1 else "No context")
    )

    payload = chat_json_with_retry(
        COMPARER_SYSTEM,
        user_prompt,
        REPAIR_HINTS,
        attempts=COMPARE_REPAIR_ATTEMPTS,
        model=(
            COMPARE_MODEL
            if state.think_mode
            else FAST_COMPARE_MODEL
        ),
    )

    rows_payload = payload.get("rows") or []

    rows: List[ComparisonRow] = []

    for raw in rows_payload:
        if not isinstance(raw, dict):
            continue

        try:
            document_a = str(raw.get("document_a", ""))
            document_b = str(raw.get("document_b", ""))

            if (
                document_a.strip().lower() == "not mentioned"
                and document_b.strip().lower() == "not mentioned"
            ):
                continue

            row = ComparisonRow.model_validate(
                {
                    "topic": raw.get("topic", ""),
                    "document_a": document_a,
                    "document_b": document_b,
                    "difference": bool(raw.get("difference", False)),
                    "confidence": raw.get("confidence", "medium"),
                    "impact": raw.get("impact", "unknown"),
                }
            )
        except Exception:
            continue

        _attach_evidence(row, records_by_doc, display_by_pinecone)
        rows.append(row)

    return rows


# ============================================================================
# Overview
# ============================================================================

def _build_overview(
    result: ComparisonResult,
    state: WorkflowState,
) -> str:
    sections_ct = len(result.sections)
    rows_ct = result.total_rows()
    diff_ct = len(result.differences())
    high_ct = len(result.high_impact_differences())

    deterministic = (
        f"Analyzed **{sections_ct} sections** across "
        f"**{rows_ct} items**, and found **{diff_ct} difference(s)**, "
        f"**{high_ct} high-impact**."
    )

    try:
        payload = chat_json(
            OVERVIEW_SYSTEM,
            (
                "Original request: " + state.query + "\n\n"
                "Totals: sections=" + str(sections_ct)
                + ", items=" + str(rows_ct)
                + ", differences=" + str(diff_ct)
                + ", high_impact=" + str(high_ct) + "\n"
                "Top high-impact topics: " + ", ".join(
                    row.topic
                    for row in result.high_impact_differences()[:5]
                )
            ),
            temperature=0.2,
            model=OVERVIEW_MODEL,
        )

        overview = str(payload.get("overview") or "").strip()

        if overview:
            return overview + "\n\n" + deterministic

    except Exception:
        pass

    return deterministic


# ============================================================================
# Chat renderer
# ============================================================================

def render_chat_answer(
    result: ComparisonResult,
    overview: str,
    state: WorkflowState,
) -> str:
    names = state.display_names()

    doc_a = names[0] if names else "Document A"
    doc_b = names[-1] if len(names) > 1 else "Document B"

    lines: List[str] = [
        f"### Comparison: {doc_a} vs {doc_b}",
        "",
        overview,
        "",
    ]

    for section in result.sections:
        if not section.rows:
            continue

        lines.append(f"## {section.name}")
        lines.append("")
        lines.append(
            "| Topic | "
            f"{doc_a} | {doc_b} | "
            "Difference | Impact |"
        )
        lines.append("|---|---|---|---|---|")

        for row in section.rows:
            unverified = (
                " ⚠ could not confirm" if row.unverified else ""
            )

            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(row.topic),
                        _cell(row.document_a),
                        _cell(row.document_b),
                        "Yes" if row.difference else "No",
                        (
                            row.impact.capitalize()
                            + unverified
                        ),
                    ]
                )
                + " |"
            )

        lines.append("")

    if result.unverified_rows():
        lines.append(
            "_Some claims could not be fully confirmed from the retrieved "
            "text and are marked ⚠._"
        )
        lines.append("")

    return "\n".join(lines)


def _cell(value) -> str:
    text = str(value or "").replace("|", "/").replace("\n", " ").strip()
    return text or "—"


# ============================================================================
# Orchestrator
# ============================================================================

def _run_section_task(
    index: int,
    section: Dict[str, Any],
    state: WorkflowState,
    embedder: Any,
    coverages: Dict[str, DocumentCoverage],
    display_by_pinecone: dict,
) -> tuple[int, str, List[ComparisonRow]]:
    records_by_doc = _build_section_context(
        section,
        state,
        coverages,
        embedder,
    )
    rows = _compare_section(
        section,
        state,
        records_by_doc,
        display_by_pinecone,
    )
    return index, section["name"], rows

def run_compare(
    state: WorkflowState,
    embedder: Any,
) -> Iterator[WorkflowEvent]:
    """
    Execute the comparison workflow, yielding progress then a complete event.

    Yields
    ------
    WorkflowEvent
        Progress events while planning/analyzing sections, and finally a
        ``complete`` event containing the canonical result + chat answer.
    """

    display_by_pinecone = state.display_by_pinecone()

    yield WorkflowEvent(
        kind="progress",
        message=(
            f"Planning a thorough comparison of "
            f"{state.display_names()[0]} and {state.display_names()[-1]}"
        ),
    )

    # --- RETRIEVE ----------------------------------------------------------
    coverages: Dict[str, DocumentCoverage] = {}

    for display, pinecone in state.doc_pairs:
        coverage = fetch_document_coverage(
            document_name=pinecone,
            embedder=embedder,
            namespace=state.namespace,
        )
        coverages[pinecone] = coverage

        completion = (
            "exhaustive"
            if coverage.complete
            else "selective"
        )

        yield WorkflowEvent(
            kind="progress",
            message=(
                f"Read {len(coverage.records)} passages from {display} "
                f"({completion} coverage)"
            ),
        )

    observed_sections = _observed_sections_from_coverages(coverages)

    yield WorkflowEvent(
        kind="progress",
        message=(
            "Extracted sections from the documents: "
            + (
                ", ".join(observed_sections)
                if observed_sections
                else "no section headings detected - planning from content"
            )
        ),
    )

    # --- PLAN --------------------------------------------------------------
    preview_parts: List[str] = []

    for display, pinecone in state.doc_pairs:
        coverage = coverages.get(pinecone)

        for record in (coverage.records[:10] if coverage else []):
            snippet = (record.text or "").strip()

            if snippet:
                preview_parts.append(f"[{display}]\n{snippet[:500]}")

    preview_text = "\n\n".join(preview_parts)[:6000]

    sections_plan = _plan_sections(
        state,
        observed_sections,
        preview_text=preview_text,
    )

    yield WorkflowEvent(
        kind="progress",
        message=(
            f"Planned {len(sections_plan)} comparison sections"
        ),
        section_total=len(sections_plan),
    )

    # --- COMPARE per section -----------------------------------------------
    result = ComparisonResult(
        schema_version="1.0",
        documents=state.display_names(),
        intent="compare",
        sections=[],
    )

    section_total = len(sections_plan)
    section_results: Dict[int, tuple[str, List[ComparisonRow]]] = {}

    with ThreadPoolExecutor(
        max_workers=max(1, COMPARE_MAX_WORKERS),
    ) as executor:
        futures = {
            executor.submit(
                _run_section_task,
                index,
                section,
                state,
                embedder,
                coverages,
                display_by_pinecone,
            ): index
            for index, section in enumerate(sections_plan)
        }

        for future in as_completed(futures):
            index, name, rows = future.result()
            section_results[index] = (name, rows)
            yield WorkflowEvent(
                kind="progress",
                message=(
                    f"Analyzed section {index + 1}/{section_total} · "
                    f"{name}"
                ),
                section_index=index + 1,
                section_total=section_total,
            )

    for index in range(section_total):
        name, rows = section_results[index]
        result.sections.append(
            ComparisonSection(name=name, rows=rows)
        )

    # --- VERIFY ------------------------------------------------------------
    if state.think_mode:
        yield WorkflowEvent(
            kind="progress",
            message="Verifying claims against retrieved evidence",
        )

        report = verify_result(result)

        if report.re_retrieve:
            yield WorkflowEvent(
                kind="progress",
                message=(
                    f"Re-retrieving evidence for "
                    f"{len(report.re_retrieve)} unsupported claim(s)"
                )
            )

            result.sections = _re_retrieve_claims(
                result,
                report.re_retrieve,
                state,
                embedder,
                coverages,
            )

            verify_result(result, use_llm=False)

    # --- SYNTHESIS ---------------------------------------------------------
    overview = _build_overview(result, state)
    chat_answer = render_chat_answer(result, overview, state)

    coverage_state = {
        "exhaustive": all(
            coverages[pinecone].complete
            for _, pinecone in state.doc_pairs
        ),
        "documents": {
            display: (
                len(coverages[pinecone].records)
                if coverages.get(pinecone)
                else 0
            )
            for display, pinecone in state.doc_pairs
        },
    }

    yield WorkflowEvent(
        kind="complete",
        result=result,
        coverage=coverage_state,
        chat_answer=chat_answer,
        message="Comparison complete",
    )


def _re_retrieve_claims(
    result: ComparisonResult,
    re_retrieve_rows: List[ComparisonRow],
    state: WorkflowState,
    embedder: Any,
    coverages: Dict[str, DocumentCoverage],
) -> List[ComparisonSection]:
    """
    Targeted re-retrieval for rows that failed verification, then a
    focused single re-comparison for only those rows.
    """

    display_by_pinecone = state.display_by_pinecone()

    pool_by_doc: Dict[str, List[ChunkRecord]] = {}

    for display, pinecone in state.doc_pairs:
        extra: List[ChunkRecord] = []
        coverage_records = (
            coverages[pinecone].records
            if coverages.get(pinecone)
            else []
        )

        for row in re_retrieve_rows:
            topic_embedding = embedder.embed_text(row.topic)

            extra.extend(
                semantic_search_documents(
                    document_names=[pinecone],
                    query_embedding=topic_embedding,
                    namespace=state.namespace,
                    top_k=4,
                )
            )
            extra.extend(
                keyword_scan(
                    row.topic,
                    coverage_records,
                    top_k=4,
                )
            )

        pool_by_doc[pinecone] = merge_records(extra, max_records=8)

    # Focused re-run for unsupported topics.
    focused_rows: List[ComparisonRow] = []

    if re_retrieve_rows:
        context_parts: List[str] = []

        for display, pinecone in state.doc_pairs:
            context_parts.append(
                format_records_context(
                    pool_by_doc.get(pinecone, []),
                    max_chars=max(
                        1000,
                        WORKFLOW_MAX_CONTEXT_CHARS // max(
                            1,
                            len(state.doc_pairs),
                        ),
                    ),
                )
            )

        topics = ", ".join(row.topic for row in re_retrieve_rows)

        try:
            payload = chat_json_with_retry(
                COMPARER_SYSTEM,
                (
                    "Re-analyze ONLY these topics with freshly retrieved "
                    "evidence:\n" + topics + "\n\n"
                    "Context for " + state.display_names()[0] + ":\n"
                    + (context_parts[0] if context_parts else "No context")
                    + "\n\n"
                    "Context for " + state.display_names()[-1] + ":\n"
                    + (context_parts[-1] if len(context_parts) > 1 else "No context")
                ),
                REPAIR_HINTS,
                attempts=COMPARE_REPAIR_ATTEMPTS,
                model=(
                    COMPARE_MODEL
                    if state.think_mode
                    else FAST_COMPARE_MODEL
                ),
            )

            for raw in payload.get("rows") or []:
                if not isinstance(raw, dict):
                    continue

                try:
                    row = ComparisonRow.model_validate(
                        {
                            "topic": raw.get("topic", ""),
                            "document_a": raw.get("document_a", ""),
                            "document_b": raw.get("document_b", ""),
                            "difference": bool(raw.get("difference", False)),
                            "confidence": raw.get("confidence", "medium"),
                            "impact": raw.get("impact", "unknown"),
                        }
                    )
                except Exception:
                    continue

                _attach_evidence(row, pool_by_doc, display_by_pinecone)
                focused_rows.append(row)

        except Exception:
            focused_rows = []

    # Rebuild sections, replacing re-retrieved rows that match a topic.
    new_sections: List[ComparisonSection] = []
    focused_by_topic = {
        row.topic.strip().lower(): row
        for row in focused_rows
    }

    for section in result.sections:
        rebuilt_rows: List[ComparisonRow] = []

        for row in section.rows:
            replacement = focused_by_topic.get(
                row.topic.strip().lower()
            )

            if replacement is not None:
                rebuilt_rows.append(replacement)
            else:
                rebuilt_rows.append(row)

        new_sections.append(
            ComparisonSection(name=section.name, rows=rebuilt_rows)
        )

    return new_sections
