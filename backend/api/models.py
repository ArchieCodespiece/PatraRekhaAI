# ============================================================================
# REQUEST MODELS
# ============================================================================

from typing import List
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    selected_documents: List[str] = Field(..., max_length=50)
    conversation_id: str | None = Field(None, max_length=100)
    owner_email: str | None = Field(None, max_length=255)
    target_format: str | None = Field(None, max_length=16)
    think_mode: bool = False


class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    owner_email: str | None = Field(None, max_length=255)


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
