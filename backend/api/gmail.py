from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from api.dependencies import (
    get_authenticated_identity,
    verify_requested_email,
)

from db.gmail_connections import (
    delete_gmail_connection,
    deactivate_gmail_connection,
    get_gmail_connection,
    touch_gmail_connection,
    upsert_gmail_connection,
)

from services.gmail_oauth import (
    build_authorize_url,
    exchange_code_for_tokens,
    verify_state,
)

from fastapi.responses import RedirectResponse

import os
import threading
from urllib.request import Request as UrllibRequest
from urllib.request import urlopen


router = APIRouter()


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
# GMAIL CONNECT
# ============================================================================

@router.get("/gmail/connect/start")
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

@router.get("/gmail/connect/callback")
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

@router.get("/gmail/connect/status")
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

@router.post("/gmail/connect/heartbeat")
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

@router.post("/gmail/connect/deactivate")
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

@router.delete("/gmail/connect")
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

@router.delete("/gmail/connect/reset")
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
