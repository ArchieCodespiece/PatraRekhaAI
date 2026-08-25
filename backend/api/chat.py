from __future__ import annotations

import re
from typing import Any, Dict, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from api.dependencies import (
    get_authenticated_identity,
    verify_requested_email,
)

from api.documents import (
    MAX_SELECTED_DOCUMENTS,
    TOP_K_PER_DOCUMENT,
    build_context_from_matches,
    get_match_metadata,
    resolve_pinecone_document_names,
)

from api.models import (
    ChatRequest,
)

from api.conversation_helpers import (
    create_conversation,
    get_conversation,
    save_message,
    update_conversation,
)

from embedding.embedder import GeminiEmbedder

from vectorstore.retrieval import (
    get_chunks_from_documents,
)


router = APIRouter()


FULL_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

SHORT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{12}-"
)

FILE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


def _clean_source_name(name: str) -> str:
    if not name:
        return name

    cleaned = str(name)

    while True:
        new = FULL_UUID_PATTERN.sub(
            "",
            cleaned,
        ).lstrip("-_")

        new = SHORT_ID_PATTERN.sub(
            "",
            new,
        ).lstrip("-_")

        if new == cleaned:
            break

        cleaned = new

    return cleaned


def _extract_file_id(value: str) -> str | None:
    if not value:
        return None
    match = FILE_ID_PATTERN.match(str(value))
    return match.group(0) if match else None


def _match_score(match: Any) -> float:
    if isinstance(match, dict):
        return float(match.get("score") or 0)
    return float(getattr(match, "score", 0) or 0)


def _build_citations(matches: List[Any]) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen_texts = set()

    for match in matches:
        metadata = get_match_metadata(match)

        document_name = metadata.get("document_name")
        if not document_name:
            continue

        text = str(metadata.get("text") or "").strip()
        if not text or text in seen_texts:
            continue
        seen_texts.add(text)

        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        section = metadata.get("section")

        document_id = metadata.get("document_id", "")
        file_id = _extract_file_id(document_id) or _extract_file_id(document_name)

        citations.append(
            {
                "document_name": _clean_source_name(document_name),
                "file_id": file_id,
                "page_start": page_start,
                "page_end": page_end,
                "section": section,
                "text": text,
                "score": _match_score(match),
            }
        )

    return citations


# ============================================================================
# LLM LOADER
# ============================================================================

_llm_module: Any | None = None


def load_llm_module() -> Any:
    global _llm_module

    if _llm_module is not None:
        return _llm_module

    from pathlib import Path
    import importlib.util
    import sys

    BACKEND_DIR = Path(__file__).resolve().parents[1]
    PROJECT_ROOT = BACKEND_DIR.parent
    REPO_ROOT = BACKEND_DIR.parent
    AI_PIPELINE_DIR = REPO_ROOT / "AI pipeline"

    if str(AI_PIPELINE_DIR) not in sys.path:
        sys.path.insert(0, str(AI_PIPELINE_DIR))

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
# CHAT
# ============================================================================

@router.post("/chat")
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

    save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=query,
        selected_documents=selected_documents,
        sources=[],
    )

    embedder = GeminiEmbedder()

    query_embedding = embedder.embed_text(
        query
    )

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

    context_text = build_context_from_matches(
        matches
    )

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

    citations = _build_citations(matches)

    sources = [
        citation["document_name"]
        for citation in citations
    ]

    save_message(
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        selected_documents=selected_documents,
        sources=sources,
    )

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

    return {
        "conversation_id": conversation_id,
        "answer": answer,
        "sources": sources,
        "citations": citations,
    }
