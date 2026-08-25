# ============================================================================
# REQUEST MODELS
# ============================================================================

from typing import List
from pydantic import BaseModel


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
