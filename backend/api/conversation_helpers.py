
from typing import Any, Dict, List

from fastapi import HTTPException

from db.supabase_client import supabase

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

