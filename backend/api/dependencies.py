
# ============================================================================
# AUTHENTICATION
# ============================================================================

from fastapi import Depends, Header, HTTPException

from db.supabase_client import supabase

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

