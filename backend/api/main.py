"""FastAPI entrypoint for document APIs."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_PIPELINE_DIR = REPO_ROOT / "AI pipeline"

if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))

from db.document_metadata import list_document_metadata, list_document_metadata_by_file_ids
from db.files import get_document_file_url, list_documents, list_ready_documents
from embedding.embedder import GeminiEmbedder
from vectorstore.retrieval import get_chunks_from_documents
from webhooks.router import router as webhooks_router
from webhooks.service.document_queue import document_queue

MAX_SELECTED_DOCUMENTS = 5
TOP_K_PER_DOCUMENT = 4
MAX_CONTEXT_CHARS = 16_000


@asynccontextmanager
async def lifespan(_app):
    await document_queue.start()
    try:
        yield
    finally:
        await document_queue.stop()


app = FastAPI(title="PatraRekha API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)


class ChatRequest(BaseModel):
    query: str
    selected_documents: List[str]


_llm_module: Any | None = None


def load_llm_module() -> Any:
    """Load the LLM helper from the file path without relying on a hyphenated import."""

    global _llm_module

    if _llm_module is not None:
        return _llm_module

    llm_file = AI_PIPELINE_DIR / "vectorstore" / "llm-response.py"

    spec = importlib.util.spec_from_file_location("llm_response_module", llm_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load llm-response module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _llm_module = module
    return _llm_module


def get_match_field(match: Any, field: str, default: Any = None) -> Any:
    if isinstance(match, dict):
        return match.get(field, default)
    return getattr(match, field, default)


def get_match_metadata(match: Any) -> Dict[str, Any]:
    metadata = get_match_field(match, "metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def build_context_from_matches(matches: List[Any], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Build LLM context with source labels while keeping the prompt bounded.
    """

    blocks = []
    used_chars = 0

    for match in matches:
        metadata = get_match_metadata(match)
        text = str(metadata.get("text") or "").strip()
        if not text:
            continue

        document_name = metadata.get("document_name") or metadata.get("document_id") or "Unknown document"
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        chunk_id = get_match_field(match, "id") or metadata.get("chunk_id") or "unknown"

        page_label = ""
        if page_start and page_end:
            page_label = f" | Pages: {page_start}-{page_end}" if page_start != page_end else f" | Page: {page_start}"

        header = f"[Document: {document_name}{page_label} | Chunk: {chunk_id}]"
        block = f"{header}\n{text}"

        remaining_chars = max_chars - used_chars
        if remaining_chars <= 0:
            break

        if len(block) > remaining_chars:
            block = block[:remaining_chars].rstrip()

        blocks.append(block)
        used_chars += len(block) + 2

    return "\n\n".join(blocks)


def clean_document_key(value: str) -> str:
    return Path(value).stem.strip()


def resolve_pinecone_document_names(selected_documents: List[str]) -> List[str]:
    """
    Temporary bridge for already-indexed chunks whose Pinecone document_name is
    built from the webhook temp filename: <file_id>-<filename_stem>.
    """

    selected_keys = {clean_document_key(name): name for name in selected_documents}
    resolved_names = []

    try:
        documents = list_documents()
    except Exception:
        documents = []

    for document in documents:
        file_id = str(document.get("file_id") or "").strip()
        filename = str(document.get("filename") or "").strip()
        filename_stem = clean_document_key(filename)

        if not file_id or not filename_stem:
            continue

        matched = False
        for selected_key in selected_keys:
            if filename_stem == selected_key or filename_stem.endswith(f"-{selected_key}"):
                matched = True
                break

        if matched:
            resolved_names.append(f"{file_id}-{filename_stem}")

    # Keep exact selected values too, so old clean/manual Pinecone document names
    # like EJ1172284 continue to work while already-indexed prefixed names work.
    resolved_names.extend(selected_documents)

    return list(dict.fromkeys(resolved_names))


def parse_timeline_json(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []

    return []


def parse_dd_mm_yyyy(value: str) -> date | None:
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", value or "")
    if not match:
        return None

    day, month, year = (int(part) for part in match.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def event_priority(event_text: str) -> str:
    text = (event_text or "").lower()
    if any(word in text for word in ("deadline", "submission", "award", "closes", "due")):
        return "high"
    if any(word in text for word in ("opens", "begins", "notification", "visit", "presentation")):
        return "medium"
    return "normal"


@app.get("/get-documents")
def get_documents():
    documents = list_ready_documents()
    file_ids = [str(document["file_id"]) for document in documents if document.get("file_id")]
    metadata_rows = list_document_metadata_by_file_ids(file_ids)
    metadata_by_file_id = {
        str(metadata["file_id"]): metadata
        for metadata in metadata_rows
        if metadata.get("file_id")
    }

    enriched_documents = []
    for document in documents:
        file_id = str(document.get("file_id") or "")
        metadata = metadata_by_file_id.get(file_id, {})
        enriched_documents.append(
            {
                **document,
                "file_heading": metadata.get("file_heading"),
                "summarization": metadata.get("summarization"),
                "timeline_json": metadata.get("timeline_json"),
                "metadata_created_at": metadata.get("created_at"),
                "metadata_updated_at": metadata.get("updated_at"),
            }
        )

    return {"documents": enriched_documents}


@app.get("/calender-events")
def get_calender_events():
    metadata_rows = list_document_metadata()
    events = []

    for metadata in metadata_rows:
        file_id = str(metadata.get("file_id") or "")
        file_heading = metadata.get("file_heading") or "Untitled Document"

        for index, item in enumerate(parse_timeline_json(metadata.get("timeline_json"))):
            event_date = parse_dd_mm_yyyy(str(item.get("date") or ""))
            if not event_date:
                continue

            event_text = str(item.get("event") or "").strip() or "Important date"
            events.append(
                {
                    "id": f"{file_id}-{index}",
                    "file_id": file_id,
                    "file_heading": file_heading,
                    "date": event_date.isoformat(),
                    "display_date": item.get("date"),
                    "title": event_text,
                    "time": "All Day",
                    "category": "Document",
                    "priority": event_priority(event_text),
                    "completed": False,
                }
            )

    events.sort(key=lambda event: event["date"])
    return {"events": events}


@app.get("/get-documents/{file_id}")
def get_document(file_id: str):
    try:
        file_url = get_document_file_url(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid document id") from exc

    if not file_url:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"file_id": file_id, "file_url": file_url}


@app.post("/chat")
def chat(request: ChatRequest):
    """
    Chat endpoint that:
    1. embeds the user's query,
    2. filters Pinecone retrieval to the selected document names,
    3. sends the retrieved context into the LLM response module.
    """

    query = request.query.strip()
    selected_documents = [name.strip() for name in request.selected_documents if name and name.strip()]

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not selected_documents:
        raise HTTPException(
            status_code=400,
            detail="selected_documents must contain at least one document name.",
        )

    if len(selected_documents) > MAX_SELECTED_DOCUMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"selected_documents cannot contain more than {MAX_SELECTED_DOCUMENTS} documents.",
        )

    embedder = GeminiEmbedder()
    query_embedding = embedder.embed_text(query)

    pinecone_document_names = resolve_pinecone_document_names(selected_documents)

    retrieval_result = get_chunks_from_documents(
        document_names=pinecone_document_names,
        query_embedding=query_embedding,
        top_k=TOP_K_PER_DOCUMENT,
    )

    if isinstance(retrieval_result, dict):
        matches = retrieval_result.get("matches", [])
    else:
        matches = getattr(retrieval_result, "matches", [])

    context_text = build_context_from_matches(matches)

    llm_module = load_llm_module()
    answer = llm_module.generate_response(
        question=query,
        context=context_text,
    )

    return {
        "answer": answer,
        "matches": [
            {
                "id": getattr(match, "id", None),
                "score": getattr(match, "score", None),
                "metadata": getattr(match, "metadata", {}),
            }
            if not isinstance(match, dict)
            else match
            for match in matches
        ],
    }
