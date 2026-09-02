from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import (
    get_authenticated_identity,
    verify_requested_email,
)

from api.models import (
    DocumentSearchRequest,
)

from db.document_metadata import (
    delete_document_metadata,
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

from document_preprocessing.converter import (
    get_content_type,
    is_supported_document,
)

from embedding.embedder import GeminiEmbedder

from vectorstore.retrieval import (
    get_chunks,
)


router = APIRouter()

limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# CONSTANTS
# ============================================================================

MAX_SELECTED_DOCUMENTS = 5
TOP_K_PER_DOCUMENT = 4
MAX_CONTEXT_CHARS = 16_000

SEMANTIC_DOCUMENT_TOP_K = 25

SEMANTIC_DOCUMENT_SCORE_THRESHOLD = float(
    __import__("os")
    .getenv(
        "SEMANTIC_DOCUMENT_SCORE_THRESHOLD",
        "0.35",
    )
)

MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_ATTACHMENT_BYTES", 50 * 1024 * 1024)
)

FILE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


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
            or "Unknown document"
        )

        page_start = metadata.get(
            "page_start"
        )

        page_end = metadata.get(
            "page_end"
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
            f"]"
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


# ============================================================================
# DOCUMENT HELPERS
# ============================================================================

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
                "language": metadata.get(
                    "language"
                ),
                "languages": metadata.get(
                    "languages"
                ),
                "script": metadata.get(
                    "script"
                ),
                "scripts": metadata.get(
                    "scripts"
                ),
                "language_confidence": metadata.get(
                    "language_confidence"
                ),
                "is_romanized": metadata.get(
                    "is_romanized"
                ),
                "is_code_switched": metadata.get(
                    "is_code_switched"
                ),
            }
        )

    return enriched_documents


# ============================================================================
# DOCUMENT LIST
# ============================================================================

@router.get("/get-documents")
def get_documents(
    owner_email: str | None = None,
    identity=Depends(get_authenticated_identity),
):
    """
    Return documents belonging only to the authenticated user.

    Flow:

        authenticated user
                ↓
            files table
                ↓
          user's file_ids
                ↓
        document_metadata
                ↓
             merge
    """

    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        owner_email,
        authenticated_email,
    )

    documents = list_documents(
        owner_email=effective_email,
        user_id=user_id,
    )

    if not documents:
        return {
            "documents": []
        }

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

        metadata = metadata_by_file_id.get(
            file_id,
            {},
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

                "language": metadata.get(
                    "language"
                ),

                "languages": metadata.get(
                    "languages"
                ),

                "script": metadata.get(
                    "script"
                ),

                "scripts": metadata.get(
                    "scripts"
                ),

                "language_confidence": metadata.get(
                    "language_confidence"
                ),

                "is_romanized": metadata.get(
                    "is_romanized"
                ),

                "is_code_switched": metadata.get(
                    "is_code_switched"
                ),
            }
        )

    return {
        "documents": enriched_documents
    }


# ============================================================================
# DOCUMENT UPLOAD
# ============================================================================

@router.post("/upload-document")
@limiter.limit("10/minute")
def upload_document(
    request: Request,
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

    if not is_supported_document(original_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Supported: PDF, DOCX, DOC, PPTX, PPT, "
                "XLSX, XLS, TXT, CSV."
            ),
        )

    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large. Maximum size is "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
            ),
        )

    content = file.file.read()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large. Maximum size is "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
            ),
        )

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
        f"{safe_filename(
            original_name,
            'document.pdf'
        )}"
    )

    content_type = (
        file.content_type
        or get_content_type(original_name)
    )

    record = store_file(
        stored_name,
        content,
        content_type,
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
        "processing": True,
    }


# ============================================================================
# DOCUMENT URL
# ============================================================================

@router.get("/get-documents/{file_id}")
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

@router.delete("/documents/{file_id}")
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
# DOCUMENT RE-PROCESS
# ============================================================================

@router.post("/documents/{file_id}/reprocess")
@limiter.limit("5/minute")
def reprocess_document(
    request: Request,
    file_id: str,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    try:
        document = get_document(
            file_id,
            user_id=user_id,
        )
    except TypeError:
        document = get_document(
            file_id,
            owner_email=authenticated_email,
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    from webhooks.service.document_queue import document_queue

    try:
        document_queue.enqueue(
            {
                "file_id": file_id,
                "filename": document.get("filename"),
                "user_id": user_id,
                "owner_email": authenticated_email,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enqueue re-processing: {exc}",
        ) from exc

    return {
        "ok": True,
        "file_id": file_id,
        "message": "Document queued for re-processing.",
    }


# ============================================================================
# SEMANTIC DOCUMENT SEARCH
# ============================================================================

@router.post("/semantic-document-search")
@limiter.limit("30/minute")
def semantic_document_search(
    request: Request,
    body: DocumentSearchRequest,
    identity=Depends(get_authenticated_identity),
):
    user_id, authenticated_email = identity

    effective_email = verify_requested_email(
        body.owner_email,
        authenticated_email,
    )

    query = body.query.strip()

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
