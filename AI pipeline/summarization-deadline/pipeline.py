"""Simple PDF summary and deadline extraction pipeline."""

from __future__ import annotations

import json
import os
import re
import sys
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

DEFAULT_MODEL = os.getenv("METADATA_LLM_MODEL", "llama-3.1-8b-instant")
MAX_TEXT_CHARS = int(os.getenv("METADATA_MAX_TEXT_CHARS", "50000"))


def process_pdf_metadata(pdf_path: str | Path, file_id: str) -> dict[str, Any]:
    """
    Read a PDF, ask the LLM for structured metadata, and store it in Supabase.
    """

    text = extract_pdf_text(pdf_path, max_chars=MAX_TEXT_CHARS)
    metadata = extract_metadata_with_llm(text)

    # Imported inside the function so this pipeline can be tested without the
    # backend package on sys.path.
    from db.document_metadata import upsert_document_metadata

    upsert_document_metadata(
        file_id=file_id,
        file_heading=metadata["file_heading"],
        summarization=metadata["summarization"],
        timeline_json=metadata["timeline_json"],
    )

    return metadata


def extract_pdf_text(pdf_path: str | Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = []
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages.append(f"[Page {page_number}]\n{page_text}")

            if sum(len(page_text) for page_text in pages) >= max_chars:
                break

    text = "\n\n".join(pages).strip()
    return text[:max_chars]


def extract_metadata_with_llm(document_text: str) -> dict[str, Any]:
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
    request = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract document metadata. Return only valid JSON with keys: "
                    "file_heading string, summarization string, timeline_json array. "
                    "timeline_json items must be objects with date and event strings. "
                    "Use null or an empty array when information is missing."
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
                {
                    "date": str(date or "").strip(),
                    "event": str(event or "").strip(),
                }
            )

    return {
        "file_heading": str(file_heading).strip() or "Untitled Document",
        "summarization": str(summarization).strip(),
        "timeline_json": normalized_timeline,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract and store PDF metadata.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("file_id", help="Supabase files.file_id for this PDF.")
    args = parser.parse_args()

    print(json.dumps(process_pdf_metadata(args.pdf_path, args.file_id), indent=2))
