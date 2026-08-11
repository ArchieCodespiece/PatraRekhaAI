"""
PatraRekhaAI FastAPI Backend

Responsibilities:

- Authentication through Supabase
- Document listing/upload/deletion
- Semantic document search
- PDF chat using Pinecone + LLM
- Conversation persistence
- Recent chat history
- Loading previous conversations
- Gmail connection
- Webhook/document queue integration
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import threading
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request as UrllibRequest
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel


# ============================================================================
# PATHS / ENVIRONMENT
# ============================================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

AI_PIPELINE_DIR = REPO_ROOT / "AI pipeline"

if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))


# ============================================================================
# PROJECT IMPORTS
# ============================================================================

from db.supabase_client import supabase

from db.document_metadata import (
    delete_document_metadata,
    list_document_metadata,
    list_document_metadata_by_file_ids,
)

from db.files import (
    delete_file_from_storage,
    delete_file_record,
    get_document,
    get_document_file_url,
    list_documents,
    list_ready_documents,
    store_file,
)

from db.gmail_connections import (
    delete_gmail_connection,
    deactivate_gmail_connection,
    get_gmail_connection,
    touch_gmail_connection,
    upsert_gmail_connection,
)

from embedding.embedder import GeminiEmbedder

from services.gmail_oauth import (
    build_authorize_url,
    exchange_code_for_tokens,
    verify_state,
)

from vectorstore.retrieval import (
    get_chunks,
    get_chunks_from_documents,
)

from webhooks.router import router as webhooks_router
from webhooks.service.document_queue import document_queue


# ============================================================================
# CONSTANTS
# ============================================================================

MAX_SELECTED_DOCUMENTS = 5
TOP_K_PER_DOCUMENT = 4
MAX_CONTEXT_CHARS = 16_000

SEMANTIC_DOCUMENT_TOP_K = 25

SEMANTIC_DOCUMENT_SCORE_THRESHOLD = float(
    os.getenv(
        "SEMANTIC_DOCUMENT_SCORE_THRESHOLD",
        "0.35",
    )
)

FILE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


# ============================================================================
# APPLICATION LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await document_queue.start()

    try:
        yield
    finally:
        await document_queue.stop()


app = FastAPI(
    title="PatraRekha API",
    description="PatraRekhaAI document intelligence backend",
    lifespan=lifespan,
)


# ============================================================================
# CORS
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# WEBHOOKS
# ============================================================================

app.include_router(webhooks_router)


# ============================================================================
# GMAIL SYNC
# ============================================================================

def trigger_gmail_sync_non_blocking() -> None:
    """
    Trigger Gmail ingestion without blocking the API request.
    """

    def run_sync() -> None:
        try:
            request = UrllibRequest(
                "http://127.0.0.1:8002/sync",
                method="POST",
            )

            with urlopen(request, timeout=5):
                pass

        except Exception:
            # Gmail sync must never break the main API request.
            pass

    threading.Thread(
        target=run_sync,
        daemon=True,
    ).start()


# ============================================================================
# AUTHENTICATION
# ============================================================================

def get_current_user(
    authorization: str | None = Header(default=None),
):
    """
    Authenticate using:

        Authorization: Bearer <supabase-access-token>
    """

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header.",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header.",
        )

    access_token = authorization[7:].strip()

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Missing Supabase access token.",
        )

    try:
        response = supabase.auth.get_user(access_token)
        user = response.user

    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Supabase session.",
        ) from exc

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Supabase session.",
        )

    user_id = str(
        getattr(user, "id", "") or ""
    ).strip()

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user has no user ID.",
        )

    return user


def get_authenticated_identity(
    current_user=Depends(get_current_user),
):
    """
    Returns:

        user_id
        owner_email
    """

    user_id = str(current_user.id)

    owner_email = getattr(
        current_user,
        "email",
        None,
    )

    if owner_email:
        owner_email = owner_email.strip().lower()

    return user_id, owner_email


def verify_requested_email(
    requested_email: str | None,
    authenticated_email: str | None,
):
    """
    owner_email is kept for backwards compatibility.

    It can NEVER override the authenticated user.
    """

    if not authenticated_email:
        if requested_email:
            raise HTTPException(
                status_code=403,
                detail="Authenticated user has no email address.",
            )

        return None

    authenticated_email = (
        authenticated_email.strip().lower()
    )

    if requested_email:
        requested_email = (
            requested_email.strip().lower()
        )

        if requested_email != authenticated_email:
            raise HTTPException(
                status_code=403,
                detail="You cannot access another user's data.",
            )

    return authenticated_email


# ============================================================================
# REQUEST MODELS
# ============================================================================

class ChatRequest(BaseModel):
    query: str
    selected_documents: List[str]
    conversation_id: str | None = None
    owner_email: str | None = None


class DocumentSearchRequest(BaseModel):
    query: str
    owner_email: str | None = None


class ConversationCreateRequest(BaseModel):
    title: str | None = None


# ============================================================================
# LLM LOADER
# ============================================================================

_llm_module: Any | None = None


def load_llm_module() -> Any:
    global _llm_module

    if _llm_module is not None:
        return _llm_module

    llm_file = (
        AI_PIPELINE_DIR
        / "vectorstore"
        / "llm-response.py"
    )

    if not llm_file.exists():
        raise RuntimeError(
            f"LLM module not found: {llm_file}"
        )

    spec = importlib.util.spec_from_file_location(
        "llm_response_module",
        llm_file,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load llm-response module."
        )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    _llm_module = module

    return module


# ============================================================================
# SUPABASE HELPERS
# ============================================================================

def supabase_table(name: str):
    return supabase.table(name)


# ============================================================================
# CONVERSATION HELPERS
# ============================================================================

def create_conversation(
    user_id: str,
    title: str = "New Chat",
):
    """
    Create a conversation belonging to the authenticated user.
    """

    result = (
        supabase_table("conversations")
        .insert(
            {
                "user_id": user_id,
                "title": title,
            }
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Unable to create conversation.",
        )

    return result.data[0]


def get_conversation(
    conversation_id: str,
    user_id: str,
):
    """
    Retrieve a conversation only if it belongs
    to the authenticated user.
    """

    result = (
        supabase_table("conversations")
        .select("*")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    return result.data


def save_message(
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    selected_documents: List[str] | None = None,
    sources: List[str] | None = None,
):
    """
    Save a single chat message.
    """

    result = (
        supabase_table("messages")
        .insert(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "selected_documents": (
                    selected_documents or []
                ),
                "sources": sources or [],
            }
        )
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Unable to save chat message.",
        )

    return result.data[0]


def update_conversation(
    conversation_id: str,
    user_id: str,
    title: str | None = None,
):
    """
    Update conversation title/timestamp.
    """

    payload: Dict[str, Any] = {}

    if title:
        payload["title"] = title

    payload["updated_at"] = "now()"

    (
        supabase_table("conversations")
        .update(payload)
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )


def get_recent_conversations(
    user_id: str,
):
    """
    Return recent conversations for this user.
    """

    result = (
        supabase_table("conversations")
        .select("*")
        .eq("user_id", user_id)
        .order(
            "updated_at",
            desc=True,
        )
        .limit(50)
        .execute()
    )

    return result.data or []


def get_conversation_messages(
    conversation_id: str,
    user_id: str,
):
    """
    Return messages only if the conversation belongs
    to the authenticated user.
    """

    conversation = get_conversation(
        conversation_id,
        user_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    result = (
        supabase_table("messages")
        .select("*")
        .eq(
            "conversation_id",
            conversation_id,
        )
        .eq("user_id", user_id)
        .order(
            "created_at",
            desc=False,
        )
        .execute()
    )

    return result.data or []


# ============================================================================
# CONVERSATION API
# ============================================================================

@app.post("/conversations")
def create_new_conversation(
    request: ConversationCreateRequest,
    identity=Depends(get_authenticated_identity),
):
    """
    Create a new empty chat.
    """

    user_id, _ = identity

    title = (
        request.title.strip()
        if request.title
        else "New Chat"
    )

    conversation = create_conversation(
        user_id=user_id,
        title=title,
    )

    return {
        "conversation": conversation,
    }


@app.get("/conversations")
def list_conversations(
    identity=Depends(get_authenticated_identity),
):
    """
    ChatGPT-style recent conversations.
    """

    user_id, _ = identity

    conversations = get_recent_conversations(
        user_id
    )

    return {
        "conversations": conversations,
    }


@app.get("/conversations/{conversation_id}")
def open_conversation(
    conversation_id: str,
    identity=Depends(get_authenticated_identity),
):
    """
    Open one previous conversation.
    """

    user_id, _ = identity

    conversation = get_conversation(
        conversation_id,
        user_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    messages = get_conversation_messages(
        conversation_id,
        user_id,
    )

    return {
        "conversation": conversation,
        "messages": messages,
    }


@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    identity=Depends(get_authenticated_identity),
):
    """
    Delete a conversation and all its messages.
    """

    user_id, _ = identity

    conversation = get_conversation(
        conversation_id,
        user_id,
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    (
        supabase_table("messages")
        .delete()
        .eq(
            "conversation_id",
            conversation_id,
        )
        .eq("user_id", user_id)
        .execute()
    )

    (
        supabase_table("conversations")
        .delete()
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .execute()
    )

    return {
        "ok": True,
        "conversation_id": conversation_id,
    }


# ============================================================================
# RETRIEVAL HELPERS
# ============================================================================

def get_match_field(
    match: Any,
    field: str,
    default: Any = None,
):
    if isinstance(match, dict):
        return match.get(
            field,
            default,
        )

    return getattr(
        match,
        field,
        default,
    )


def get_match_metadata(
    match: Any,
):
    metadata = get_match_field(
        match,
        "metadata",
        {},
    )

    return (
        metadata
        if isinstance(metadata, dict)
        else {}
    )


def match_score(
    match: Any,
) -> float:
    if isinstance(match, dict):
        return float(
            match.get("score") or 0
        )

    return float(
        getattr(
            match,
            "score",
            0,
        )
        or 0
    )


def build_context_from_matches(
    matches: List[Any],
    max_chars: int = MAX_CONTEXT_CHARS,
):
    blocks: List[str] = []
    used_chars = 0

    for match in matches:
        metadata = get_match_metadata(match)

        text = str(
            metadata.get("text") or ""
        ).strip()

        if not text:
            continue

        document_name = (
            metadata.get("document_name")
            or metadata.get("document_id")
            or "Unknown document"
        )

        page_start = metadata.get(
            "page_start"
        )

        page_end = metadata.get(
            "page_end"
        )

        chunk_id = (
            get_match_field(
                match,
                "id",
            )
            or metadata.get("chunk_id")
            or "unknown"
        )

        page_label = ""

        if page_start and page_end:
            if page_start != page_end:
                page_label = (
                    f" | Pages: "
                    f"{page_start}-{page_end}"
                )
            else:
                page_label = (
                    f" | Page: "
                    f"{page_start}"
                )

        header = (
            f"[Document: {document_name}"
            f"{page_label}"
            f" | Chunk: {chunk_id}]"
        )

        block = (
            f"{header}\n"
            f"{text}"
        )

        remaining = (
            max_chars - used_chars
        )

        if remaining <= 0:
            break

        if len(block) > remaining:
            block = (
                block[:remaining]
                .rstrip()
            )

        if not block:
            break

        blocks.append(block)

        used_chars += len(block) + 2

    return "\n\n".join(blocks)


def clean_document_key(
    value: str,
):
    return Path(value).stem.strip()


def safe_filename(
    value: str,
    fallback: str,
):
    name = re.sub(
        r"[^a-zA-Z0-9.*-]",
        "",
        value or fallback,
    ).strip("._")

    return name or fallback


def resolve_pinecone_document_names(
    selected_documents: List[str],
    owner_email: str | None = None,
):
    selected_keys = {
        clean_document_key(name): name
        for name in selected_documents
    }

    resolved_names: List[str] = []

    try:
        documents = list_documents(
            owner_email=owner_email,
        )
    except Exception:
        documents = []

    for document in documents:
        file_id = str(
            document.get("file_id") or ""
        ).strip()

        filename = str(
            document.get("filename") or ""
        ).strip()

        filename_stem = clean_document_key(
            filename
        )

        if not file_id or not filename_stem:
            continue

        matched = False

        for selected_key in selected_keys:
            if (
                filename_stem == selected_key
                or filename_stem.endswith(
                    f"-{selected_key}"
                )
            ):
                matched = True
                break

        if matched:
            resolved_names.append(
                f"{file_id}-{filename_stem}"
            )

    resolved_names.extend(
        selected_documents
    )

    return list(
        dict.fromkeys(
            resolved_names
        )
    )


# ============================================================================
# DOCUMENT HELPERS
# ============================================================================

def ready_documents_with_metadata(
    owner_email: str | None = None,
):
    documents = list_ready_documents(
        owner_email=owner_email
    )

    file_ids = [
        str(document["file_id"])
        for document in documents
        if document.get("file_id")
    ]

    metadata_rows = (
        list_document_metadata_by_file_ids(
            file_ids
        )
    )

    metadata_by_file_id = {
        str(metadata["file_id"]): metadata
        for metadata in metadata_rows
        if metadata.get("file_id")
    }

    enriched_documents = []

    for document in documents:
        file_id = str(
            document.get("file_id") or ""
        )

        metadata = (
            metadata_by_file_id.get(
                file_id,
                {},
            )
        )

        enriched_documents.append(
            {
                **document,
                "file_heading": metadata.get(
                    "file_heading"
                ),
                "summarization": metadata.get(
                    "summarization"
                ),
                "timeline_json": metadata.get(
                    "timeline_json"
                ),
                "metadata_created_at": metadata.get(
                    "created_at"
                ),
                "metadata_updated_at": metadata.get(
                    "updated_at"
                ),
            }
        )

    return enriched_documents


# ============================================================================
# TIMELINE HELPERS
# ============================================================================

def parse_timeline_json(
    value: Any,
):
    if not value:
        return []

    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, list):
            return [
                item
                for item in parsed
                if isinstance(item, dict)
            ]

    return []


def parse_dd_mm_yyyy(
    value: str,
):
    match = re.search(
        r"\b(\d{1,2})/"
        r"(\d{1,2})/"
        r"(\d{4})\b",
        value or "",
    )

    if not match:
        return None

    day, month, year = (
        int(part)
        for part in match.groups()
    )

    try:
        return date(
            year,
            month,
            day,
        )
    except ValueError:
        return None


def event_priority(
    event_text: str,
):
    text = (
        event_text or ""
    ).lower()

    if any(
        word in text
        for word in (
            "deadline",
            "submission",
            "award",
            "closes",
            "due",
        )
    ):
        return "high"

    if any(
        word in text
        for word in (
            "opens",
            "begins",
            "notification",
            "visit",
            "presentation",
        )
    ):
        return "medium"

    return "normal"


# ============================================================================
# HEALTH
# ============================================================================

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "PatraRekha API",
    }


# ============================================================================
# DOCUMENT LIST
# ============================================================================

@app.get("/get-documents")
def get_documents(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    trigger_gmail_sync_non_blocking()

    documents = ready_documents_with_metadata(
        owner_email=effective_email
    )

    return {
        "documents": documents
    }


# ============================================================================
# DOCUMENT UPLOAD
# ============================================================================

@app.post("/upload-document")
def upload_document(
    file: UploadFile = File(...),
    owner_email: str | None = Form(default=None),
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    original_name = (
        file.filename
        or "document.pdf"
    ).strip()

    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF documents are supported.",
        )

    content = file.file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    content_hash = hashlib.sha256(
        content
    ).hexdigest()

    stored_name = (
        f"{content_hash[:12]}-"
        f"{safe_filename(original_name, 'document.pdf')}"
    )

    record = store_file(
        stored_name,
        content,
        file.content_type or "application/pdf",
        owner_email=effective_email,
        user_id=user_id,
        content_hash=content_hash,
    )

    if not record:
        raise HTTPException(
            status_code=500,
            detail=(
                "Document was uploaded but "
                "no database record was returned."
            ),
        )

    return {
        "ok": True,
        "file_id": record["file_id"],
        "filename": record["filename"],
    }


# ============================================================================
# DOCUMENT URL
# ============================================================================

@app.get("/get-documents/{file_id}")
def get_document_endpoint(
    file_id: str,
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    try:
        document = get_document(
            file_id,
            owner_email=effective_email,
            user_id=user_id,
        )
    except TypeError:
        document = get_document(
            file_id,
            owner_email=effective_email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid document id",
        ) from exc

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    try:
        file_url = get_document_file_url(
            file_id,
            owner_email=effective_email,
            user_id=user_id,
        )
    except TypeError:
        file_url = get_document_file_url(
            file_id,
            owner_email=effective_email,
        )

    if not file_url:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return {
        "file_id": file_id,
        "file_url": file_url,
    }


# ============================================================================
# DOCUMENT DELETE
# ============================================================================

@app.delete("/documents/{file_id}")
def delete_document(
    file_id: str,
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    try:
        document = get_document(
            file_id,
            owner_email=effective_email,
            user_id=user_id,
        )
    except TypeError:
        document = get_document(
            file_id,
            owner_email=effective_email,
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    pinecone_deleted = True

    # ------------------------------------------------------------------------
    # PINECONE CLEANUP
    # ------------------------------------------------------------------------

    try:
        from vectorstore.pinecone_store import (
            PineconeStore,
        )

        store = PineconeStore(
            namespace=user_id
        )

        document_name = clean_document_key(
            str(
                document.get("filename")
                or ""
            )
        )

        candidates = set()

        if document_name:
            candidates.add(document_name)
            candidates.add(
                f"{file_id}-{document_name}"
            )

        for name in candidates:
            store.delete_document(
                name,
                namespace=user_id,
            )

    except Exception as exc:
        pinecone_deleted = False

        print(
            "[delete-document] "
            f"Pinecone cleanup failed: {exc}"
        )

    # ------------------------------------------------------------------------
    # STORAGE CLEANUP
    # ------------------------------------------------------------------------

    try:
        delete_file_from_storage(
            str(
                document.get("filename")
                or ""
            ),
            owner_email=effective_email,
            user_id=user_id,
        )

    except TypeError:
        delete_file_from_storage(
            str(
                document.get("filename")
                or ""
            ),
            owner_email=effective_email,
        )

    except Exception as exc:
        print(
            "[delete-document] "
            f"Storage cleanup failed: {exc}"
        )

    # ------------------------------------------------------------------------
    # DATABASE CLEANUP
    # ------------------------------------------------------------------------

    try:
        delete_file_record(
            file_id,
            owner_email=effective_email,
            user_id=user_id,
        )

    except TypeError:
        delete_file_record(
            file_id,
            owner_email=effective_email,
        )

    except Exception as exc:
        print(
            "[delete-document] "
            f"Database cleanup failed: {exc}"
        )

    # ------------------------------------------------------------------------
    # METADATA CLEANUP
    # ------------------------------------------------------------------------

    try:
        delete_document_metadata(
            file_id
        )

    except Exception as exc:
        print(
            "[delete-document] "
            f"Metadata cleanup failed: {exc}"
        )

    return {
        "ok": True,
        "file_id": file_id,
        "pinecone_deleted": pinecone_deleted,
    }


# ============================================================================
# SEMANTIC DOCUMENT SEARCH
# ============================================================================

@app.post("/semantic-document-search")
def semantic_document_search(
    request: DocumentSearchRequest,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        request.owner_email,
        authenticated_email,
    )

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty.",
        )

    documents = ready_documents_with_metadata(
        effective_email
    )

    documents_by_file_id = {
        str(document["file_id"]): document
        for document in documents
        if document.get("file_id")
    }

    embedder = GeminiEmbedder()

    query_embedding = embedder.embed_text(
        query
    )

    retrieval_result = get_chunks(
        query_embedding=query_embedding,
        top_k=SEMANTIC_DOCUMENT_TOP_K,
        namespace=user_id,
    )

    if isinstance(
        retrieval_result,
        dict,
    ):
        matches = retrieval_result.get(
            "matches",
            [],
        )
    else:
        matches = getattr(
            retrieval_result,
            "matches",
            [],
        )

    ranked_documents: Dict[str, Dict[str, Any]] = {}

    for match in matches:
        metadata = get_match_metadata(match)
        score = match_score(match)

        if (
            score
            < SEMANTIC_DOCUMENT_SCORE_THRESHOLD
        ):
            continue

        file_id = None

        for key in (
            "document_id",
            "document_name",
        ):
            value = str(
                metadata.get(key) or ""
            )

            match_id = FILE_ID_PATTERN.match(
                value
            )

            if match_id:
                file_id = match_id.group(0)
                break

        document = (
            documents_by_file_id.get(file_id)
            if file_id
            else None
        )

        if not document:
            continue

        document_file_id = str(
            document["file_id"]
        )

        existing = ranked_documents.get(
            document_file_id
        )

        if (
            not existing
            or score
            > existing["semantic_score"]
        ):
            ranked_documents[
                document_file_id
            ] = {
                **document,
                "semantic_score": score,
                "matched_document_name": (
                    metadata.get(
                        "document_name"
                    )
                ),
                "matched_chunk_id": (
                    get_match_field(
                        match,
                        "id",
                    )
                ),
            }

    results = sorted(
        ranked_documents.values(),
        key=lambda document:
            document["semantic_score"],
        reverse=True,
    )

    return {
        "documents": results
    }


# ============================================================================
# CALENDAR
# ============================================================================

@app.get("/calender-events")
def get_calender_events(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    documents = list_documents(
        owner_email=effective_email
    )

    metadata_rows = list_document_metadata()

    allowed_file_ids = {
        str(document.get("file_id"))
        for document in documents
        if document.get("file_id")
    }

    events = []

    for metadata in metadata_rows:
        file_id = str(
            metadata.get("file_id")
            or ""
        )

        if (
            allowed_file_ids
            and file_id not in allowed_file_ids
        ):
            continue

        file_heading = (
            metadata.get("file_heading")
            or "Untitled Document"
        )

        timeline_items = parse_timeline_json(
            metadata.get("timeline_json")
        )

        for index, item in enumerate(
            timeline_items
        ):
            event_date = parse_dd_mm_yyyy(
                str(
                    item.get("date")
                    or ""
                )
            )

            if not event_date:
                continue

            event_text = (
                str(
                    item.get("event")
                    or ""
                ).strip()
                or "Important date"
            )

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
                    "priority": event_priority(
                        event_text
                    ),
                    "completed": False,
                }
            )

    events.sort(
        key=lambda event:
            event["date"]
    )

    return {
        "events": events
    }


# ============================================================================
# CHAT
# ============================================================================

@app.post("/chat")
def chat(
    request: ChatRequest,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        request.owner_email,
        authenticated_email,
    )

    query = request.query.strip()

    selected_documents = [
        name.strip()
        for name in request.selected_documents
        if name and name.strip()
    ]

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty.",
        )

    if not selected_documents:
        raise HTTPException(
            status_code=400,
            detail=(
                "selected_documents must contain "
                "at least one document name."
            ),
        )

    if (
        len(selected_documents)
        > MAX_SELECTED_DOCUMENTS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "selected_documents cannot contain "
                f"more than {MAX_SELECTED_DOCUMENTS} documents."
            ),
        )

    # ------------------------------------------------------------------------
    # CONVERSATION
    # ------------------------------------------------------------------------

    conversation_id = request.conversation_id

    if conversation_id:
        conversation = get_conversation(
            conversation_id,
            user_id,
        )

        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

    else:
        conversation = create_conversation(
            user_id=user_id,
            title=query[:80],
        )

        conversation_id = str(
            conversation["id"]
        )

    # ------------------------------------------------------------------------
    # SAVE USER MESSAGE
    # ------------------------------------------------------------------------

    save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=query,
        selected_documents=selected_documents,
        sources=[],
    )

    # ------------------------------------------------------------------------
    # EMBEDDING
    # ------------------------------------------------------------------------

    embedder = GeminiEmbedder()

    query_embedding = embedder.embed_text(
        query
    )

    # ------------------------------------------------------------------------
    # PINECONE
    # ------------------------------------------------------------------------

    pinecone_document_names = (
        resolve_pinecone_document_names(
            selected_documents,
            owner_email=effective_email,
        )
    )

    retrieval_result = get_chunks_from_documents(
        document_names=pinecone_document_names,
        query_embedding=query_embedding,
        top_k=TOP_K_PER_DOCUMENT,
        namespace=user_id,
    )

    if isinstance(
        retrieval_result,
        dict,
    ):
        matches = retrieval_result.get(
            "matches",
            [],
        )
    else:
        matches = getattr(
            retrieval_result,
            "matches",
            [],
        )

    # ------------------------------------------------------------------------
    # CONTEXT
    # ------------------------------------------------------------------------

    context_text = build_context_from_matches(
        matches
    )

    # ------------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------------

    llm_module = load_llm_module()

    try:
        answer = llm_module.generate_response(
            question=query,
            context=context_text,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM generation failed: {exc}",
        ) from exc

    if not answer:
        answer = (
            "I could not generate an answer "
            "from the selected documents."
        )

    # ------------------------------------------------------------------------
    # SOURCES
    # ------------------------------------------------------------------------

    sources = []

    for match in matches:
        metadata = get_match_metadata(match)

        document_name = metadata.get(
            "document_name"
        )

        if document_name:
            sources.append(document_name)

    sources = list(
        dict.fromkeys(sources)
    )

    # ------------------------------------------------------------------------
    # SAVE AI MESSAGE
    # ------------------------------------------------------------------------

    save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        selected_documents=selected_documents,
        sources=sources,
    )

    # ------------------------------------------------------------------------
    # UPDATE TITLE / TIMESTAMP
    # ------------------------------------------------------------------------

    if conversation.get("title") in (
        None,
        "",
        "New Chat",
    ):
        update_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
            title=query[:80],
        )
    else:
        update_conversation(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------------
    # RESPONSE
    # ------------------------------------------------------------------------

    formatted_matches = []

    for match in matches:
        if isinstance(match, dict):
            formatted_matches.append(match)
        else:
            formatted_matches.append(
                {
                    "id": getattr(
                        match,
                        "id",
                        None,
                    ),
                    "score": getattr(
                        match,
                        "score",
                        None,
                    ),
                    "metadata": getattr(
                        match,
                        "metadata",
                        {},
                    ),
                }
            )

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "matches": formatted_matches,
    }


# ============================================================================
# GMAIL CONNECT
# ============================================================================

@app.get("/gmail/connect/start")
def gmail_connect_start(
    owner_email: str = Query(
        ...,
        min_length=3,
    ),
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    if not effective_email:
        raise HTTPException(
            status_code=400,
            detail="Missing authenticated email.",
        )

    try:
        authorization_url = build_authorize_url(
            owner_email=effective_email,
            user_id=user_id,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "authorization_url": authorization_url
    }


# ============================================================================
# GMAIL CALLBACK
# ============================================================================

@app.get("/gmail/connect/callback")
def gmail_connect_callback(
    code: str,
    state: str,
):
    try:
        state_data = verify_state(state)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    owner_email = str(
        state_data["owner_email"]
    ).strip().lower()

    user_id = str(
        state_data["user_id"]
    ).strip()

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="OAuth state missing user_id.",
        )

    try:
        token_data = exchange_code_for_tokens(
            code
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    google_email = str(
        token_data.get("email")
        or owner_email
    ).strip().lower()

    access_token = str(
        token_data.get("access_token")
        or ""
    )

    refresh_token = str(
        token_data.get("refresh_token")
        or ""
    )

    scopes = str(
        token_data.get("scope")
        or ""
    )

    if not access_token:
        raise HTTPException(
            status_code=500,
            detail=(
                "Google OAuth did not return "
                "an access token."
            ),
        )

    try:
        stored = upsert_gmail_connection(
            user_id=user_id,
            owner_email=owner_email,
            google_email=google_email,
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=scopes,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    trigger_gmail_sync_non_blocking()

    redirect_target = os.getenv(
        "FRONTEND_GMAIL_CONNECT_REDIRECT",
        "http://localhost:3000/dashboard",
    )

    connection_name = google_email

    if isinstance(stored, dict):
        connection_name = (
            stored.get("google_email")
            or google_email
        )

    return RedirectResponse(
        url=(
            f"{redirect_target}"
            f"?gmail_connected=1"
            f"&owner_email={owner_email}"
            f"&google_email={connection_name}"
        ),
        status_code=302,
    )


# ============================================================================
# GMAIL CONNECTION STATUS
# ============================================================================

@app.get("/gmail/connect/status")
def gmail_connect_status(
    owner_email: str = Query(
        ...,
        min_length=3,
    ),
    identity=Depends(get_authenticated_identity),
):
    """
    Return the current Gmail connection state.

    This endpoint does NOT reactivate the connection.

    The important distinction is:

        status  -> read-only
        heartbeat -> reactivates connection

    Therefore a stale/inactive Gmail connection can remain
    inactive until the browser returns and sends a heartbeat.
    """

    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    if not effective_email:
        raise HTTPException(
            status_code=400,
            detail="Missing authenticated email.",
        )

    connection = get_gmail_connection(
        effective_email
    )

    if not connection:
        return {
            "connected": False,
            "active": False,
            "owner_email": effective_email,
        }

    if isinstance(connection, dict):
        google_email = (
            connection.get("google_email")
            or effective_email
        )

        active = bool(
            connection.get("active", False)
        )

        return {
            "connected": True,
            "active": active,
            "owner_email": effective_email,
            "google_email": google_email,
            "connection": connection,
        }

    return {
        "connected": True,
        "active": False,
        "owner_email": effective_email,
        "google_email": effective_email,
    }

# ============================================================================
# GMAIL STATUS
# ============================================================================

@app.post("/gmail/connect/heartbeat")
def gmail_connect_heartbeat(
    owner_email: str = Query(
        ...,
        min_length=3,
    ),
    identity=Depends(get_authenticated_identity),
):
    """
    Record recent browser activity for the authenticated
    Gmail connection.

    Every heartbeat also reactivates the Gmail connection.

    Therefore:

        INACTIVE
            ↓
        browser returns
            ↓
        heartbeat
            ↓
        ACTIVE

    OAuth credentials are never deleted here.
    """

    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    if not effective_email:
        raise HTTPException(
            status_code=400,
            detail="Missing authenticated email.",
        )

    connection = touch_gmail_connection(
        effective_email
    )

    if not connection:
        raise HTTPException(
            status_code=404,
            detail="Gmail connection not found.",
        )

    return {
        "ok": True,
        "connected": True,
        "active": True,
        "owner_email": effective_email,
    }


# ============================================================================
# GMAIL DEACTIVATE
# ============================================================================

@app.post("/gmail/connect/deactivate")
def gmail_deactivate(
    identity=Depends(get_authenticated_identity),
):
    """
    Explicitly disable Gmail ingestion without deleting
    the Gmail OAuth connection.

    This is used during Supabase logout.

    OAuth credentials remain stored so the user does not
    need to reconnect Gmail when they sign in again.
    """

    user_id, authenticated_email = identity

    if not authenticated_email:
        raise HTTPException(
            status_code=400,
            detail=(
                "Authenticated user has no "
                "email address."
            ),
        )

    connection = deactivate_gmail_connection(
        authenticated_email
    )

    return {
        "ok": True,
        "active": False,
        "connection": connection,
    }


# ============================================================================
# GMAIL DISCONNECT
# ============================================================================

@app.delete("/gmail/connect")
def gmail_disconnect(
    owner_email: str = Query(
        ...,
        min_length=3,
    ),
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    delete_gmail_connection(
        effective_email
    )

    return {
        "ok": True,
    }


# ============================================================================
# GMAIL RESET
# ============================================================================

@app.delete("/gmail/connect/reset")
def gmail_disconnect_all(
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    if not authenticated_email:
        raise HTTPException(
            status_code=400,
            detail=(
                "Authenticated user has no "
                "email address."
            ),
        )

    delete_gmail_connection(
        authenticated_email
    )

    return {
        "ok": True,
    }