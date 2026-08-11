"""
Supabase-backed Gmail connection storage.

Connection lifecycle:

    ACTIVE
       |
       | no browser heartbeat
       v
    INACTIVE
       |
       | browser heartbeat / browser returns
       v
    ACTIVE

Important:
- Gmail OAuth credentials are NOT deleted when inactive.
- is_active is the single source of truth for Gmail ingestion.
- last_seen_at is updated by the frontend heartbeat.
- Stale connections are automatically marked inactive.
- Reactivation is safe against stale-expiration race conditions.
"""

from __future__ import annotations

from datetime import datetime, timezone

from postgrest.exceptions import APIError

from db.supabase_client import supabase


# ============================================================================
# Configuration
# ============================================================================

GMAIL_CONNECTIONS_TABLE = "gmail_connections"

# Browser heartbeat is normally sent every 60 seconds.
# A connection becomes stale after 180 seconds without a heartbeat.
GMAIL_ACTIVITY_TIMEOUT_SECONDS = 180


GMAIL_CONNECTIONS_SELECT_COLUMNS = (
    "user_id,"
    "owner_email,"
    "google_email,"
    "provider_access_token,"
    "provider_refresh_token,"
    "scopes,"
    "connected_at,"
    "updated_at,"
    "is_active,"
    "last_seen_at"
)


# ============================================================================
# Helpers
# ============================================================================

def normalize_email(email: str | None) -> str:
    """Normalize an email address for consistent database lookups."""

    return (email or "").strip().lower()


def utc_now() -> str:
    """Return the current UTC timestamp as ISO-8601."""

    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value) -> datetime | None:
    """
    Parse a Supabase/PostgreSQL timestamp into an aware UTC datetime.
    """

    if not value:
        return None

    if isinstance(value, datetime):
        timestamp = value

    else:
        try:
            timestamp = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        except (TypeError, ValueError):
            return None

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    return timestamp.astimezone(timezone.utc)


# ============================================================================
# Create / update Gmail connection
# ============================================================================

def upsert_gmail_connection(
    user_id,
    owner_email,
    google_email,
    access_token,
    refresh_token,
    scopes,
):
    """
    Create or update a Gmail connection.

    Existing OAuth connections are reused.

    If the connection was previously inactive, connecting/returning
    to the application activates it again.

    OAuth credentials remain stored even when the connection becomes
    inactive.
    """

    if not user_id:
        raise ValueError(
            "user_id is required for Gmail connection."
        )

    owner_email = normalize_email(owner_email)
    google_email = normalize_email(google_email)

    if not owner_email:
        raise ValueError(
            "owner_email is required for Gmail connection."
        )

    now = utc_now()

    row = {
        "user_id": str(user_id),
        "owner_email": owner_email,
        "google_email": google_email,
        "provider_access_token": access_token,
        "provider_refresh_token": refresh_token,
        "scopes": scopes,
        "connected_at": now,
        "updated_at": now,
        "is_active": True,
        "last_seen_at": now,
    }

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .upsert(
                row,
                on_conflict="owner_email",
            )
            .execute()
        )

    except APIError as exc:
        raise RuntimeError(
            "gmail_connections table is missing or unavailable in Supabase."
        ) from exc

    return response.data[0] if response.data else None


# ============================================================================
# Get one Gmail connection
# ============================================================================

def get_gmail_connection(owner_email):
    """Return the Gmail connection for a user."""

    owner_email = normalize_email(owner_email)

    if not owner_email:
        return None

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .select(GMAIL_CONNECTIONS_SELECT_COLUMNS)
            .eq(
                "owner_email",
                owner_email,
            )
            .limit(1)
            .execute()
        )

    except APIError:
        return None

    return response.data[0] if response.data else None


# ============================================================================
# Expire stale Gmail connections
# ============================================================================

def expire_stale_gmail_connections():
    """
    Mark stale Gmail connections inactive.

    Deactivation is conditional on the SAME stale timestamp that
    was observed during the initial read.

    This prevents this race:

        ingest reads stale connection
                    |
                    v
        browser heartbeat arrives
                    |
                    v
        connection becomes ACTIVE
                    |
                    v
        old stale-ingest operation deactivates it again

    The final UPDATE checks last_seen_at again, so a fresh heartbeat
    always wins.
    """

    now = datetime.now(timezone.utc)

    stale_connections = []

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .select(
                "owner_email,last_seen_at,is_active"
            )
            .eq(
                "is_active",
                True,
            )
            .execute()
        )

    except APIError as exc:
        print(
            f"[GMAIL] Failed to inspect stale connections: {exc}"
        )
        return []

    for connection in response.data or []:

        owner_email = normalize_email(
            connection.get("owner_email")
        )

        if not owner_email:
            continue

        last_seen = parse_timestamp(
            connection.get("last_seen_at")
        )

        # A missing heartbeat timestamp is treated as stale.
        if last_seen is None:

            stale_connections.append(
                (
                    owner_email,
                    None,
                )
            )

            continue

        age_seconds = (
            now - last_seen
        ).total_seconds()

        if age_seconds > GMAIL_ACTIVITY_TIMEOUT_SECONDS:

            stale_connections.append(
                (
                    owner_email,
                    last_seen,
                )
            )

    expired_emails = []

    for owner_email, observed_last_seen in stale_connections:

        try:

            if deactivate_stale_gmail_connection(
                owner_email,
                observed_last_seen,
            ):

                expired_emails.append(
                    owner_email
                )

                print(
                    f"[GMAIL] Marked stale connection inactive: "
                    f"{owner_email}"
                )

        except Exception as error:

            print(
                f"[GMAIL] Failed to deactivate stale "
                f"connection {owner_email}: {error}"
            )

    return expired_emails


def deactivate_stale_gmail_connection(
    owner_email: str,
    observed_last_seen: datetime | None,
) -> bool:
    """
    Conditionally deactivate a stale Gmail connection.

    If a heartbeat arrived after the stale connection was read,
    last_seen_at will have changed and this UPDATE will affect
    zero rows.

    Therefore a newer heartbeat always wins.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return False

    update_query = (
        supabase
        .table(GMAIL_CONNECTIONS_TABLE)
        .update(
            {
                "is_active": False,
                "updated_at": utc_now(),
            }
        )
        .eq(
            "owner_email",
            owner_email,
        )
        .eq(
            "is_active",
            True,
        )
    )

    if observed_last_seen is None:

        update_query = update_query.is_(
            "last_seen_at",
            "null",
        )

    else:

        update_query = update_query.eq(
            "last_seen_at",
            observed_last_seen.isoformat(),
        )

    response = update_query.execute()

    return bool(
        response.data
    )


# ============================================================================
# List active Gmail connections
# ============================================================================

def list_gmail_connections():
    """
    Return Gmail connections that are currently active.

    Stale connections are expired before querying active connections.
    """

    expire_stale_gmail_connections()

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .select(GMAIL_CONNECTIONS_SELECT_COLUMNS)
            .eq(
                "is_active",
                True,
            )
            .execute()
        )

    except APIError as exc:

        print(
            f"[GMAIL] Failed to list active connections: {exc}"
        )

        return []

    return response.data or []


# ============================================================================
# List all Gmail connections
# ============================================================================

def list_all_gmail_connections():
    """Return every Gmail connection, active or inactive."""

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .select(GMAIL_CONNECTIONS_SELECT_COLUMNS)
            .execute()
        )

    except APIError:
        return []

    return response.data or []


# ============================================================================
# Update OAuth tokens
# ============================================================================

def update_gmail_connection_tokens(
    owner_email,
    access_token,
    refresh_token=None,
):
    """
    Update OAuth access/refresh tokens.

    Token refresh does NOT change is_active.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return None

    row = {
        "provider_access_token": access_token,
        "updated_at": utc_now(),
    }

    if refresh_token:
        row[
            "provider_refresh_token"
        ] = refresh_token

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .update(row)
            .eq(
                "owner_email",
                owner_email,
            )
            .execute()
        )

    except APIError as exc:

        raise RuntimeError(
            "gmail_connections table is missing or unavailable in Supabase."
        ) from exc

    return response.data[0] if response.data else None


# ============================================================================
# Activate Gmail connection
# ============================================================================

def activate_gmail_connection(
    owner_email,
):
    """
    Mark an existing Gmail connection as active.

    This is used when the browser returns to the application.

    OAuth credentials are preserved.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return None

    now = utc_now()

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .update(
                {
                    "is_active": True,
                    "last_seen_at": now,
                    "updated_at": now,
                }
            )
            .eq(
                "owner_email",
                owner_email,
            )
            .execute()
        )

    except APIError as exc:

        raise RuntimeError(
            "Unable to activate Gmail connection."
        ) from exc

    return response.data[0] if response.data else None


# ============================================================================
# Update Gmail activity / heartbeat
# ============================================================================

def touch_gmail_connection(
    owner_email,
):
    """
    Record browser activity.

    This function ALWAYS performs:

        last_seen_at = NOW
        updated_at = NOW
        is_active = TRUE

    Therefore:

        INACTIVE
            |
            | browser returns / heartbeat
            v
        ACTIVE

    No OAuth reconnect is required here.
    The existing stored Gmail OAuth credentials remain untouched.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return None

    now = utc_now()

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .update(
                {
                    "last_seen_at": now,
                    "updated_at": now,
                    "is_active": True,
                }
            )
            .eq(
                "owner_email",
                owner_email,
            )
            .execute()
        )

    except APIError as exc:

        raise RuntimeError(
            "Unable to update Gmail activity."
        ) from exc

    return response.data[0] if response.data else None


# ============================================================================
# Deactivate Gmail connection
# ============================================================================

def deactivate_gmail_connection(
    owner_email,
):
    """
    Mark a Gmail connection inactive.

    OAuth tokens remain stored.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return None

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .update(
                {
                    "is_active": False,
                    "updated_at": utc_now(),
                }
            )
            .eq(
                "owner_email",
                owner_email,
            )
            .execute()
        )

    except APIError as exc:

        raise RuntimeError(
            "Unable to deactivate Gmail connection."
        ) from exc

    return response.data[0] if response.data else None


# ============================================================================
# Deactivate all Gmail connections for a user
# ============================================================================

def deactivate_all_gmail_connections(
    user_id,
):
    """
    Mark every Gmail connection belonging to a Supabase user
    as inactive.

    OAuth credentials are preserved.
    """

    if not user_id:
        return []

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .update(
                {
                    "is_active": False,
                    "updated_at": utc_now(),
                }
            )
            .eq(
                "user_id",
                str(user_id),
            )
            .execute()
        )

    except APIError as exc:

        raise RuntimeError(
            "Unable to deactivate Gmail connections."
        ) from exc

    return response.data or []


# ============================================================================
# Delete Gmail connection
# ============================================================================

def delete_gmail_connection(
    owner_email,
):
    """
    Permanently delete a Gmail connection.

    Normally this should NOT be used for logout.
    """

    owner_email = normalize_email(
        owner_email
    )

    if not owner_email:
        return []

    try:
        response = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .delete()
            .eq(
                "owner_email",
                owner_email,
            )
            .execute()
        )

    except APIError:
        return []

    return response.data or []


# ============================================================================
# Clear Gmail connections
# ============================================================================

def clear_gmail_connections(
    owner_email=None,
):
    """
    Permanently delete Gmail connections.

    If owner_email is provided, only that connection is deleted.
    Otherwise all Gmail connections are deleted.
    """

    try:
        query = (
            supabase
            .table(GMAIL_CONNECTIONS_TABLE)
            .delete()
        )

        if owner_email:

            query = query.eq(
                "owner_email",
                normalize_email(
                    owner_email
                ),
            )

        else:

            query = query.neq(
                "owner_email",
                "__none__",
            )

        response = query.execute()

    except APIError:
        return []

    return response.data or []