"""Document metadata extraction pipeline.

Hybrid extractive + abstractive architecture:
  1. Deterministic date extraction (ground truth, zero cost).
  2. Deterministic extractive sentence ranking (TF-IDF, zero cost).
  3. LLM polishing — only over the ranked sentences, never the full document.

``process_pdf_metadata(document_path, file_id)`` is the single public entry
point used by the webhook processor, email ingestion module, and CLI.  Its
signature and return shape (``{file_heading, summarization, timeline_json}``)
are unchanged.

Set EXTRACTIVE_METADATA=false to revert to the legacy single-LLM-call path.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(ROOT / "backend" / ".env")
    load_dotenv(ROOT / "AI pipeline" / ".env")

DEFAULT_MODEL = os.getenv("METADATA_LLM_MODEL", "openai/gpt-oss-120b")
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
EXTRACTIVE_METADATA = os.getenv("EXTRACTIVE_METADATA", "true").lower() in ("1", "true", "yes")
LARGE_DOCUMENT_PAGES = int(os.getenv("LARGE_DOCUMENT_PAGES", "100"))
LARGE_DOCUMENT_CHARS = int(os.getenv("LARGE_DOCUMENT_CHARS", "50000"))
MAX_TEXT_CHARS = int(os.getenv("METADATA_MAX_TEXT_CHARS", "50000"))
TOP_K_NORMAL = int(os.getenv("TOP_K_NORMAL", "20"))
TOP_K_LARGE = int(os.getenv("TOP_K_LARGE", "40"))
DATE_CLASSIFY_LLM = os.getenv("DATE_CLASSIFY_LLM", "false").lower() in ("1", "true", "yes")

# Reuse the existing default model for the polishing step.
DEFAULT_MODEL = os.getenv("METADATA_LLM_MODEL", "openai/gpt-oss-20b")

# High-priority / medium-priority keywords mirrored from calendar.py
_HIGH_KEYWORDS = frozenset({"deadline", "submission", "award", "closes", "due", "submit", "last date", "antim", "aakhri"})
_MEDIUM_KEYWORDS = frozenset({"opens", "begins", "notification", "visit", "presentation", "commence", "commences"})


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_pdf_metadata(
    document_path: str | Path,
    file_id: str,
) -> dict[str, Any]:
    """
    Read a document, extract structured metadata, store in Supabase.

    Supported formats: PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS, TXT, CSV.
    Non-PDF documents are converted to PDF before text extraction.

    Returns
    -------
    dict with keys file_heading, summarization, timeline_json
    (backward-compatible shape).
    """
    from document_preprocessing.converter import (
        convert_to_pdf,
        is_supported_document,
    )

    document_path = Path(document_path)

    if not is_supported_document(document_path):
        raise ValueError(
            f"Unsupported file type: {document_path.suffix}. "
            f"Supported: .pdf, .docx, .doc, .pptx, .ppt, "
            f".xlsx, .xls, .txt, .csv"
        )

    temp_pdf = None
    processing_path = document_path

    if document_path.suffix.lower() != ".pdf":
        temp_dir = (
            Path(tempfile.gettempdir())
            / "patrarekha-summarization"
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_pdf = temp_dir / f"{document_path.stem}.pdf"
        convert_to_pdf(document_path, temp_pdf)
        processing_path = temp_pdf

    try:
        pages = extract_pdf_text(processing_path, max_chars=MAX_TEXT_CHARS)
        joined_text = _join_pages(pages)
        from services.language_detection import detect_language
        lang_result = detect_language(joined_text)

        if EXTRACTIVE_METADATA:
            metadata = _extractive_pipeline(pages, lang_result)
        else:
            metadata = extract_metadata_with_llm(
                joined_text, lang_result=lang_result
            )

        from db.document_metadata import upsert_document_metadata
        from db.files import mark_file_summarized

        upsert_document_metadata(
            file_id=file_id,
            file_heading=metadata["file_heading"],
            summarization=metadata["summarization"],
            timeline_json=metadata["timeline_json"],
            language=getattr(lang_result, "language", None),
            languages=getattr(lang_result, "languages", None),
            script=getattr(lang_result, "script", None),
            scripts=getattr(lang_result, "scripts", None),
            language_confidence=getattr(lang_result, "confidence", None),
            is_romanized=getattr(lang_result, "romanized", None),
            is_code_switched=getattr(lang_result, "code_switched", None),
            dates_json=metadata.get("_dates_json"),
            summary_key_points=metadata.get("_key_points"),
            summary_source_sentences=metadata.get("_source_sentences"),
            pipeline_method=metadata.get("_pipeline_method", "legacy_llm"),
            actions_json=metadata.get("_actions_json"),
        )
        mark_file_summarized(file_id)
        return metadata
    finally:
        if temp_pdf and temp_pdf.exists():
            for attempt in range(3):
                try:
                    temp_pdf.unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.5)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: str | Path, max_chars: int = MAX_TEXT_CHARS) -> list[dict[str, Any]]:
    """Extract page-annotated text from a PDF.

    Returns
    -------
    list of {"page": int, "text": str}, capped at ``max_chars`` total text.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Document not found: {pdf_path}")

    pages: list[dict[str, Any]] = []
    total_len = 0

    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append({"page": page_number, "text": text})
            total_len += len(text)
            if total_len >= max_chars:
                break

    return pages


def _join_pages(pages: list[dict[str, Any]]) -> str:
    """Combine pages into a single text with [Page N] markers."""
    parts: list[str] = []
    for p in pages:
        text = p.get("text") or ""
        if text:
            parts.append(f"[Page {p.get('page', '?')}]\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Keyword heuristic date classification (deterministic, free)
# ---------------------------------------------------------------------------

_TEXT_TOKENIZE = re.compile(r"[\w\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF"
                           r"\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF"
                           r"\u0D00-\u0D7F\u0600-\u06FF]+", re.UNICODE)


_SUBMISSION_KEYWORDS = frozenset({"deadline", "submission", "bid submission", "tender submit", "closes", "due", "submit", "last date", "antim", "aakhri"})
_PAYMENT_KEYWORDS = frozenset({"payment", "fee", "emd", "earnest money", "deposit", "bank guarantee", "security deposit", "tender fee", "installment", "penalty"})
_AGREEMENT_START_KEYWORDS = frozenset({"commence", "commences", "commencement", "agreement start", "agreement begins", "valid from", "starts on", "start date"})
_AGREEMENT_END_KEYWORDS = frozenset({"expires", "expiration", "valid till", "valid up to", "termination", "tenure ends", "period of", "agreement ends"})
_EFFECTIVE_DATE_KEYWORDS = frozenset({"effective from", "in force", "with effect from", "wef", "w.e.f."})
_MEETING_KEYWORDS = frozenset({"meeting", "pre-bid", "conference", "presentation", "hearing", "site visit", "visit"})
_APPLICATION_KEYWORDS = frozenset({"application deadline", "apply by", "registration closes", "application form", "enrolment"})
_NOTICE_KEYWORDS = frozenset({"notice period", "prior notice", "within 15 days", "within 30 days"})


def _classify_keywords(text: str) -> tuple[str, str, str]:
    """Return (event_type, event_label_fragment, semantic_type) from surrounding text."""
    lower = text.lower()

    if any(kw in lower for kw in _SUBMISSION_KEYWORDS):
        return "DEADLINE", "Deadline for submission", "SUBMISSION_DEADLINE"
    if any(kw in lower for kw in _PAYMENT_KEYWORDS):
        return "PAYMENT", "Payment deadline", "PAYMENT_DEADLINE"
    if any(kw in lower for kw in _EFFECTIVE_DATE_KEYWORDS):
        return "START", "Effective date", "EFFECTIVE_DATE"
    if any(kw in lower for kw in _AGREEMENT_START_KEYWORDS):
        return "START", "Agreement begins", "AGREEMENT_START"
    if any(kw in lower for kw in _AGREEMENT_END_KEYWORDS):
        return "END", "Agreement ends", "AGREEMENT_END"
    if any(kw in lower for kw in _MEETING_KEYWORDS):
        return "MEETING", "Meeting date", "MEETING_DATE"
    if any(kw in lower for kw in _APPLICATION_KEYWORDS):
        return "DEADLINE", "Application deadline", "APPLICATION_DEADLINE"
    if any(kw in lower for kw in _NOTICE_KEYWORDS):
        return "NOTIFICATION", "Notice period", "NOTICE_PERIOD"
    if any(kw in lower for kw in _HIGH_KEYWORDS):
        return "DEADLINE", "Deadline", "SUBMISSION_DEADLINE"
    if any(kw in lower for kw in _MEDIUM_KEYWORDS):
        return "START", "Event begins", "AGREEMENT_START"
    return "OTHER", "Important date", "UNKNOWN"


def _window_around_date(context_before: str, context_after: str, raw: str, window: int = 5) -> str:
    before_tokens = _TEXT_TOKENIZE.findall(context_before or "")
    after_tokens = _TEXT_TOKENIZE.findall(context_after or "")
    left = " ".join(before_tokens[-window:])
    right = " ".join(after_tokens[:window])
    parts = [t for t in [left, raw, right] if t.strip()]
    label = " ".join(parts)
    return label.strip()[:160]


def _keyword_classify_entity(entity: dict[str, Any]) -> dict[str, Any]:
    # Classify from the sentence that actually contains the date first;
    # only fall back to the wider context window when the sentence is empty.
    event_type, default_label, semantic_type = _classify_keywords(
        entity.get("sentence") or ""
    )
    if event_type == "OTHER":
        context = " ".join(
            str(entity.get(k) or "")
            for k in ("context_before", "context_after")
        )
        event_type, default_label, semantic_type = _classify_keywords(context)
    event_label = _window_around_date(
        entity.get("context_before") or "",
        entity.get("context_after") or "",
        entity.get("raw") or default_label,
    )
    if not event_label:
        event_label = default_label
    entity["event_type"] = event_type
    entity["semantic_type"] = semantic_type
    entity["event_label"] = event_label
    return entity


def _classify_keywords_all(dates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_keyword_classify_entity(e) for e in dates]


def _build_timeline_json(dates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the backward-compatible [{date, event, ...}] array from classified entities."""
    timeline: list[dict[str, Any]] = []
    for ent in dates:
        normalized = ent.get("date") or ent.get("normalized") or ""
        event = ent.get("event_label") or ent.get("sentence") or "Important date"
        if normalized:
            item = {
                "date": normalized,
                "event": event[:200],
                "event_type": ent.get("event_type") or "UNKNOWN",
                "page": ent.get("page"),
                "raw": ent.get("raw"),
                "iso_date": ent.get("normalized"),
            }
            timeline.append(item)
    return timeline


# ---------------------------------------------------------------------------
# Heading heuristic
# ---------------------------------------------------------------------------

def _extractive_heading(pages: list[dict[str, Any]]) -> str | None:
    """First non-empty line of the first page, truncated to a heading size."""
    for page in pages[:1]:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines[:3]:
            cleaned = re.sub(r"\s+", " ", line).strip()
            if 3 < len(cleaned) <= 200:
                return cleaned
    return None


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

def _llm_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Summary polish (LLM, abstractive, strict contract)
# ---------------------------------------------------------------------------

def _summary_polish(
    client,
    sentences: list[str],
    language_name: str,
) -> dict[str, Any]:
    if not client or not sentences:
        return {}
    from prompts import build_summary_polish_messages, normalize_summary_response, parse_json_object

    messages = build_summary_polish_messages(sentences, language_name)
    request = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_completion_tokens": 1200,
        "top_p": 1,
        "stream": False,
    }
    try:
        completion = client.chat.completions.create(
            **request,
            response_format={"type": "json_object"},
        )
    except Exception:
        try:
            completion = client.chat.completions.create(**request)
        except Exception:
            return {}
    content = completion.choices[0].message.content or "{}"
    return normalize_summary_response(parse_json_object(content))


# ---------------------------------------------------------------------------
# Date classification (LLM, strict contract, optional)
# ---------------------------------------------------------------------------

def _classify_dates_llm(
    client,
    entities: list[dict[str, Any]],
    language_name: str,
) -> dict[int, dict[str, Any]]:
    if not client or not entities:
        return {}
    from prompts import (
        build_date_classify_messages,
        normalize_date_classification,
        parse_json_object,
    )

    messages = build_date_classify_messages(entities, language_name)
    request = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0,
        "max_completion_tokens": 800,
        "top_p": 1,
        "stream": False,
    }
    try:
        completion = client.chat.completions.create(
            **request,
            response_format={"type": "json_object"},
        )
    except Exception:
        try:
            completion = client.chat.completions.create(**request)
        except Exception:
            return {}
    content = completion.choices[0].message.content or "{}"
    data = parse_json_object(content)
    return normalize_date_classification(data, entities).get("dates", {})


# ---------------------------------------------------------------------------
# Extractive pipeline orchestrator
# ---------------------------------------------------------------------------

def _language_name(lang_code: str | None) -> str:
    _MAP = {
        "hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu",
        "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
        "pa": "Punjabi", "or": "Odia", "as": "Assamese", "ur": "Urdu",
    }
    return _MAP.get(lang_code, "English")


def _extractive_pipeline(
    pages: list[dict[str, Any]],
    lang_result,
) -> dict[str, Any]:
    from date_extractor import extract_dates
    from extractive_rank import rank_sentences

    lang_code = getattr(lang_result, "language", None) or "en"
    lang_name = _language_name(lang_code)

    # --- 1. Deterministic date extraction -----------------------------------
    llm_for_dates = _llm_client()
    dates = extract_dates(pages, llm_client=llm_for_dates)

    # --- 2. Deterministic sentence ranking ----------------------------------
    pages_total = len(pages)
    total_chars = sum(len(p.get("text") or "") for p in pages)
    is_large = (
        pages_total >= LARGE_DOCUMENT_PAGES
        or total_chars >= LARGE_DOCUMENT_CHARS
    )
    top_k = TOP_K_LARGE if is_large else TOP_K_NORMAL
    ranked = rank_sentences(pages=pages, top_k=top_k)

    # --- 3. File heading (heuristic + fallback LLM) ------------------------
    heading = _extractive_heading(pages)

    client = _llm_client()
    if heading is None and client and ranked:
        ranked_texts = [r.text for r in ranked if r.text.strip()][:10]
        polish_result = _summary_polish(client, ranked_texts, lang_name)
        heading = polish_result.get("summary", "")[:120] or None

    if heading is None:
        heading = "Untitled Document"

    # --- 4. Date classification --------------------------------------------
    if DATE_CLASSIFY_LLM:
        classification_map = _classify_dates_llm(client, dates, lang_name)
        for idx, ent in enumerate(dates):
            cls = classification_map.get(idx)
            if cls:
                ent["event_type"] = cls.get("event_type") or "OTHER"
                ent["event_label"] = cls.get("event_label") or "Important date"
    dates = _classify_keywords_all(dates)

    # --- 5. Summary polish (LLM, abstractive) ------------------------------
    source_text = [r.text for r in ranked if r.text.strip()]
    if client and source_text:
        polish_result = _summary_polish(client, source_text, lang_name)
        summary_text = polish_result.get("summary") or ""
        key_points = polish_result.get("key_points") or []
    elif source_text:
        # No LLM available — fall back to the top sentences as a plain summary.
        summary_text = " ".join(source_text[:8])[:2000]
        key_points = []
    else:
        summary_text = "No readable text was extracted from this document."
        key_points = []

    if not summary_text:
        summary_text = "No readable text was extracted from this document."

    # --- 6. Action and obligation extraction --------------------------------
    from action_extractor import extract_actions
    actions = extract_actions(
        sentences=ranked,
        verified_dates=dates,
        llm_client=client,
        language_name=lang_name,
    )

    # --- 7. Assemble backward-compatible + rich outputs --------------------
    timeline_json = _build_timeline_json(dates)

    source_sentences = [
        {"page": r.page, "text": r.text}
        for r in ranked
        if r.text.strip()
    ]

    return {
        "file_heading": heading,
        "summarization": summary_text,
        "timeline_json": timeline_json,
        "_dates_json": dates or [],
        "_actions_json": actions or [],
        "_key_points": key_points or [],
        "_source_sentences": source_sentences or [],
        "_pipeline_method": "extractive_large" if is_large else "extractive_small",
    }


# ---------------------------------------------------------------------------
# Legacy LLM-only pipeline (preserved for EXTRACTIVE_METADATA=false)
# ---------------------------------------------------------------------------

def extract_metadata_with_llm(document_text: str, lang_result=None) -> dict[str, Any]:
    """Legacy single-call LLM extraction.  Used when EXTRACTIVE_METADATA=false."""
    if not document_text:
        return {
            "file_heading": "Untitled Document",
            "summarization": "No readable text was extracted from this PDF.",
            "timeline_json": [],
        }

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from the environment.")

    from groq import Groq
    client = Groq(api_key=api_key)

    doc_language = "English"
    if lang_result and getattr(lang_result, "language", None) != "en":
        doc_language = _language_name(getattr(lang_result, "language", None))

    request = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract document metadata. Return only valid JSON with keys: "
                    "file_heading string, summarization string, timeline_json array. "
                    "timeline_json items must be objects with date and event strings convert date into dd/mm/yyyy format. "
                    "Use null or an empty array when information is missing. "
                    f"The document is in {doc_language}. "
                    f"Write the file_heading and summarization in {doc_language} "
                    f"(use the same script as the document). "
                    f"If the document is in a Romanized form, use that form for the output. "
                    f"If the document is mixed-language, use the primary language."
                ),
            },
            {
                "role": "user",
                "content": f"PDF text:\n{document_text}",
            },
        ],
        "temperature": 0,
        "max_completion_tokens": 1200,
        "top_p": 1,
        "stream": False,
    }

    try:
        completion = client.chat.completions.create(
            **request,
            response_format={"type": "json_object"},
        )
    except Exception:
        completion = client.chat.completions.create(**request)

    content = completion.choices[0].message.content or "{}"
    return normalize_metadata_json(parse_json_object(content))


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_metadata_json(data: dict[str, Any]) -> dict[str, Any]:
    file_heading = data.get("file_heading") or data.get("heading") or "Untitled Document"
    summarization = data.get("summarization") or data.get("summary") or ""
    timeline_json = data.get("timeline_json") or data.get("important_dates") or []

    if not isinstance(timeline_json, list):
        timeline_json = []

    normalized_timeline = []
    for item in timeline_json:
        if not isinstance(item, dict):
            continue
        date = item.get("date") or item.get("deadline") or item.get("when")
        event = item.get("event") or item.get("description") or item.get("what")
        if date or event:
            normalized_timeline.append(
                {"date": str(date or "").strip(), "event": str(event or "").strip()}
            )

    return {
        "file_heading": str(file_heading).strip() or "Untitled Document",
        "summarization": str(summarization).strip(),
        "timeline_json": normalized_timeline,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract and store document metadata.")
    parser.add_argument("document_path", help="Path to the document file.")
    parser.add_argument("file_id", help="Supabase files.file_id for this document.")
    args = parser.parse_args()

    print(json.dumps(process_pdf_metadata(args.document_path, args.file_id), indent=2))