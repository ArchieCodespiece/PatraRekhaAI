from fastapi import APIRouter, Depends, HTTPException

import re

from api.dependencies import get_authenticated_identity
from api.models import ConversationCreateRequest



from api.conversation_helpers import (
    create_conversation,
    get_conversation,
    get_conversation_messages,
    get_recent_conversations,
    supabase_table,
)

router = APIRouter()


FULL_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

SHORT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{12}-"
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


@router.post("/conversations")
def create_conversation_endpoint(
    body: ConversationCreateRequest,
    identity=Depends(get_authenticated_identity),
):
    """
    Create a new conversation for the authenticated user.
    """

    if not body.title:
        body.title = "New Chat"

    user_id, _ = identity

    return create_conversation(
        user_id=user_id,
        title=body.title,
    )

@router.get("/conversations")
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



@router.get("/conversations/{conversation_id}")
def get_conversation_endpoint(
    conversation_id: str,
    identity=Depends(get_authenticated_identity),
):
    """
    Get a single conversation and its messages
    if it belongs to the user.
    """
    user_id, _ = identity

    messages = get_conversation_messages(
        conversation_id,
        user_id,
    )

    for message in messages:
        if isinstance(message.get("sources"), list):
            message["sources"] = [
                _clean_source_name(src)
                for src in message["sources"]
                if _clean_source_name(src)
            ]

    conv = get_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    if not conv:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return {
        "conversation": conv,
        "messages": messages,
    }


@router.delete("/conversations/{conversation_id}")
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

