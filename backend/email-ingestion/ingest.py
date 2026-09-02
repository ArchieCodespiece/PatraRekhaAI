"""
Sync Gmail inboxes into Supabase-backed document storage.

Architecture:
    Supabase gmail_connections
            |
            | is_active = TRUE
            v
        ingest.py
            |
            v
        Gmail API
            |
            v
    Document attachments
            |
            v
    Supabase Storage


Connection lifecycle:

    ACTIVE
       |
       | browser heartbeat stops
       v
    INACTIVE
       |
       | browser returns
       | heartbeat resumes
       v
    ACTIVE


Important:
- Gmail OAuth connections are NOT deleted on logout.
- is_active is the single source of truth for Gmail ingestion.
- Stale browser sessions are automatically ignored.
- OAuth credentials remain stored.
- The worker only processes active Gmail connections.
- The worker re-checks connection state immediately before syncing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import msvcrt
import os
import re
import signal
import sys
import tempfile
import threading
import time

from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path


# ============================================================================
# Paths
# ============================================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

SUMMARIZATION_PIPELINE_DIR = (
    PROJECT_ROOT
    / "AI pipeline"
    / "summarization-deadline"
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if str(SUMMARIZATION_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(SUMMARIZATION_PIPELINE_DIR))


# ============================================================================
# Environment
# ============================================================================

from dotenv import load_dotenv


load_dotenv(BACKEND_DIR / ".env")

load_dotenv(
    Path(__file__).with_name(".env"),
    override=True,
)

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================================
# Database imports
# ============================================================================

from db.files import store_file

from db.gmail_connections import (
    get_gmail_connection,
    list_gmail_connections,
    update_gmail_connection_tokens,
)

from db.processed_messages import (
    is_message_processed,
    mark_message_processed,
)


# ============================================================================
# Configuration
# ============================================================================

STOP = False

_summarization_pipeline = None

GOOGLE_TOKEN_URL = (
    "https://oauth2.googleapis.com/token"
)

GMAIL_API_BASE = (
    "https://gmail.googleapis.com/gmail/v1"
)


# ============================================================================
# Local storage
# ============================================================================

STORAGE_DIR = Path(
    os.getenv(
        "STORAGE_DIR",
        "./data",
    )
).resolve()

GMAIL_HISTORY_STATE_FILE = (
    STORAGE_DIR / "gmail_history.json"
)


# ============================================================================
# Supported document types
# ============================================================================

DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv",
    "text/plain",
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".txt",
}


# ============================================================================
# Configuration helpers
# ============================================================================

def env_int(name: str, default: int) -> int:
    """Read an integer environment variable."""

    try:
        return int(
            os.getenv(
                name,
                default,
            )
        )

    except ValueError as exc:

        raise ValueError(
            f"{name} must be an integer"
        ) from exc


POLL_INTERVAL_SECONDS = env_int(
    "POLL_INTERVAL_SECONDS",
    300,
)

MAX_ATTACHMENT_BYTES = env_int(
    "MAX_ATTACHMENT_BYTES",
    25 * 1024 * 1024,
)

GMAIL_FETCH_BATCH_SIZE = env_int(
    "GMAIL_FETCH_BATCH_SIZE",
    100,
)

GMAIL_LOOKBACK_DAYS = env_int(
    "GMAIL_LOOKBACK_DAYS",
    60,
)

ALLOWED_SENDERS = {
    sender.strip().lower()
    for sender in os.getenv(
        "ALLOWED_SENDERS",
        "",
    ).split(",")
    if sender.strip()
}


def validate_config():
    """Validate required Google OAuth configuration."""

    missing = [
        name
        for name, value in {
            "GOOGLE_CLIENT_ID": os.getenv(
                "GOOGLE_CLIENT_ID"
            ),
            "GOOGLE_CLIENT_SECRET": os.getenv(
                "GOOGLE_CLIENT_SECRET"
            ),
        }.items()
        if not value
    ]

    if missing:

        raise ValueError(
            f"Missing configuration: {', '.join(missing)}"
        )


# ============================================================================
# Utility helpers
# ============================================================================

def _now() -> str:
    """Return local time for terminal logging."""

    return datetime.now().strftime(
        "%H:%M:%S"
    )


def safe_filename(
    value: str | None,
    fallback: str,
) -> str:
    """Create a safe filename."""

    name = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        value or fallback,
    )

    return name or fallback


def sender_address(message) -> str:
    """Extract the sender email address."""

    address = message.get(
        "From",
        "",
    )

    match = re.search(
        r"<([^>]+)>",
        address,
    )

    return (
        match.group(1)
        if match
        else address
    ).strip().lower()


def message_id_for(
    message,
    raw_message,
) -> str:
    """Return a stable email Message-ID."""

    return (
        message.get("Message-ID")
        or hashlib.sha256(
            raw_message
        ).hexdigest()
    )


def is_document_attachment(
    filename: str,
    content_type: str,
) -> bool:
    """Return True for supported document attachments."""

    extension = Path(
        filename or ""
    ).suffix.lower()

    return (
        extension in DOCUMENT_EXTENSIONS
        or content_type in DOCUMENT_CONTENT_TYPES
    )


def is_processable_document(
    filename: str,
    content_type: str,
) -> bool:
    """Return True for supported document types."""

    from document_preprocessing.converter import (
        is_supported_document,
    )

    return (
        is_supported_document(filename)
        or content_type in DOCUMENT_CONTENT_TYPES
    )


# ============================================================================
# Supabase user resolution
# ============================================================================

def resolve_user_id(
    connection: dict,
    owner_email: str,
) -> str | None:
    """
    Get the Supabase Auth UUID associated
    with this Gmail connection.
    """

    user_id = connection.get(
        "user_id"
    )

    if user_id:
        return str(user_id)

    print(
        f"[{_now()}] Gmail connection for "
        f"{owner_email} has no user_id."
    )

    return None


# ============================================================================
# Local processed-message cache
# ============================================================================

_processed_ids_cache: set[str] = set()

_cache_lock = threading.Lock()


def _load_processed_cache():
    """Load processed message IDs from local disk."""

    path = STORAGE_DIR / "processed.json"

    if not path.exists():
        return

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        with _cache_lock:

            _processed_ids_cache.update(
                data.get(
                    "message_ids",
                    [],
                )
            )

    except Exception:
        pass


def _persist_processed_cache():
    """Persist the local processed-message cache."""

    STORAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = STORAGE_DIR / "processed.json"

    tmp_path = path.with_suffix(
        ".tmp"
    )

    try:

        with open(
            tmp_path,
            "w",
            encoding="utf-8",
        ) as file:

            try:

                msvcrt.locking(
                    file.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )

            except Exception:
                pass

            try:

                with _cache_lock:

                    ids = list(
                        _processed_ids_cache
                    )

                json.dump(
                    {
                        "message_ids": ids
                    },
                    file,
                    indent=2,
                )

                file.write("\n")

            finally:

                try:

                    msvcrt.locking(
                        file.fileno(),
                        msvcrt.LK_UNLCK,
                        1,
                    )

                except Exception:
                    pass

        tmp_path.replace(path)

    except OSError:
        pass


def _mark_cached(
    gmail_msg_id: str,
):
    """Add a Gmail message ID to the local cache."""

    with _cache_lock:

        _processed_ids_cache.add(
            gmail_msg_id
        )

    _persist_processed_cache()


def _is_cached(
    gmail_msg_id: str,
) -> bool:
    """Check whether a Gmail message is cached locally."""

    with _cache_lock:

        return (
            gmail_msg_id
            in _processed_ids_cache
        )


# ============================================================================
# Summarization pipeline
# ============================================================================

def load_summarization_pipeline():
    """Load the metadata/summarization pipeline lazily."""

    global _summarization_pipeline

    if _summarization_pipeline is None:

        from pipeline import (
            process_pdf_metadata,
        )

        _summarization_pipeline = (
            process_pdf_metadata
        )

    return _summarization_pipeline


def process_metadata_for_attachment(
    file_record,
    filename,
    content,
):
    """Run metadata extraction for a stored document."""

    if not file_record:
        return

    file_id = file_record.get(
        "file_id"
    )

    if not file_id:
        return

    from document_preprocessing.converter import convert_to_pdf

    with tempfile.TemporaryDirectory(
        prefix="patrarekha-metadata-"
    ) as temp_dir:

        original_path = (
            Path(temp_dir)
            / filename
        )

        original_path.write_bytes(
            content
        )

        processing_path = original_path
        if original_path.suffix.lower() != ".pdf":
            pdf_path = (
                Path(temp_dir)
                / f"{original_path.stem}.pdf"
            )
            convert_to_pdf(original_path, pdf_path)
            processing_path = pdf_path

        process_pdf_metadata = (
            load_summarization_pipeline()
        )

        process_pdf_metadata(
            document_path=processing_path,
            file_id=str(file_id),
        )


# ============================================================================
# Gmail message processing
# ============================================================================

def store_message(
    message,
    raw_message,
    gmail_msg_id: str,
    owner_email: str,
    user_id: str,
):
    """
    Process one Gmail message.

    Every stored document must belong to a Supabase Auth user.
    """

    if not user_id:

        raise ValueError(
            "user_id is required for Gmail document storage."
        )

    email_message_id = message_id_for(
        message,
        raw_message,
    )

    # ------------------------------------------------------------------
    # 1. Local cache
    # ------------------------------------------------------------------

    if _is_cached(
        gmail_msg_id
    ):

        return {
            "skipped": True,
            "reason": "already_processed_cache",
        }

    # ------------------------------------------------------------------
    # 2. Supabase processed-message table
    # ------------------------------------------------------------------

    try:

        if is_message_processed(
            gmail_msg_id
        ):

            _mark_cached(
                gmail_msg_id
            )

            return {
                "skipped": True,
                "reason": "already_processed_db",
            }

    except Exception as error:

        print(
            f"Warning: could not check "
            f"processed status for "
            f"{gmail_msg_id}: {error}"
        )

    # ------------------------------------------------------------------
    # 3. Sender allow-list
    # ------------------------------------------------------------------

    sender = sender_address(
        message
    )

    if (
        ALLOWED_SENDERS
        and sender not in ALLOWED_SENDERS
    ):

        print(
            "Skipping message from "
            f"non-allowed sender: "
            f"{sender or 'unknown'}"
        )

        _mark_cached(
            gmail_msg_id
        )

        try:

            mark_message_processed(
                gmail_msg_id,
                owner_email,
                skipped=True,
                skip_reason="sender_not_allowed",
            )

        except Exception:
            pass

        return {
            "skipped": True,
            "reason": "sender_not_allowed",
        }

    # ------------------------------------------------------------------
    # 4. Find document attachments
    # ------------------------------------------------------------------

    document_attachments = []

    for index, attachment in enumerate(
        message.iter_attachments(),
        start=1,
    ):

        content = (
            attachment.get_payload(
                decode=True
            )
            or b""
        )

        original_name = (
            attachment.get_filename()
            or f"attachment-{index}"
        )

        content_type = (
            attachment.get_content_type()
        )

        if not is_document_attachment(
            original_name,
            content_type,
        ):
            continue

        if (
            len(content)
            > MAX_ATTACHMENT_BYTES
        ):

            print(
                f"Skipping oversized "
                f"attachment: "
                f"{original_name} "
                f"({len(content)} bytes)"
            )

            continue

        document_attachments.append(
            (
                attachment,
                original_name,
                content_type,
                content,
            )
        )

    # ------------------------------------------------------------------
    # 5. No documents
    # ------------------------------------------------------------------

    if not document_attachments:

        _mark_cached(
            gmail_msg_id
        )

        try:

            mark_message_processed(
                gmail_msg_id,
                owner_email,
                skipped=True,
                skip_reason="no_documents",
            )

        except Exception:
            pass

        return {
            "skipped": True,
            "no_documents": True,
        }

    # ------------------------------------------------------------------
    # 6. Store documents
    # ------------------------------------------------------------------

    received_at = datetime.now(
        timezone.utc
    )

    ingestion_id = (
        f"{received_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{hashlib.sha256(email_message_id.encode()).hexdigest()[:12]}"
    )

    stored_names = []

    for (
        _attachment,
        original_name,
        content_type,
        content,
    ) in document_attachments:

        content_hash = (
            hashlib.sha256(
                content
            ).hexdigest()
        )

        stored_name = (
            f"{content_hash[:12]}-"
            f"{safe_filename(original_name, 'attachment')}"
        )

        file_record = store_file(
            stored_name,
            content,
            content_type,
            owner_email=owner_email,
            user_id=user_id,
            content_hash=content_hash,
        )

        # --------------------------------------------------------------
        # Document metadata processing
        # --------------------------------------------------------------

        if is_processable_document(
            stored_name,
            content_type,
        ):

            try:

                process_metadata_for_attachment(
                    file_record,
                    stored_name,
                    content,
                )

            except Exception as error:

                print(
                    f"Metadata extraction "
                    f"failed for "
                    f"{stored_name}: "
                    f"{error}"
                )

        stored_names.append(
            stored_name
        )

    # ------------------------------------------------------------------
    # 7. Mark Gmail message processed
    # ------------------------------------------------------------------

    _mark_cached(
        gmail_msg_id
    )

    try:

        mark_message_processed(
            gmail_msg_id,
            owner_email,
        )

    except Exception as error:

        print(
            "Warning: could not persist "
            f"processed status for "
            f"{gmail_msg_id}: {error}"
        )

    return {
        "ingestion_id": ingestion_id,
        "attachment_count": len(
            stored_names
        ),
    }


# ============================================================================
# Gmail API
# ============================================================================

def refresh_access_token(
    refresh_token: str,
):
    """Refresh a Google OAuth access token."""

    form = urlencode(
        {
            "client_id": os.getenv(
                "GOOGLE_CLIENT_ID",
                "",
            ),
            "client_secret": os.getenv(
                "GOOGLE_CLIENT_SECRET",
                "",
            ),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")

    request = Request(
        GOOGLE_TOKEN_URL,
        data=form,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def _read_http_error(
    error,
):
    """Extract a useful message from an HTTP error."""

    try:

        payload = (
            error.read()
            .decode("utf-8")
        )

        data = json.loads(
            payload
        )

        reason = (
            data.get("error", {})
            .get("errors", [{}])[0]
            .get("reason")
        )

        message = (
            data.get("error", {})
            .get("message")
            or payload
        )

        return reason, message

    except Exception:

        return None, str(error)


def gmail_api_request(
    url: str,
    access_token: str,
):
    """Perform an authenticated Gmail API request."""

    request = Request(
        url,
        headers={
            "Authorization":
                f"Bearer {access_token}"
        },
    )

    try:

        with urlopen(
            request,
            timeout=30,
        ) as response:

            return json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except HTTPError as error:

        reason, message = (
            _read_http_error(error)
        )

        suffix = (
            f" ({reason})"
            if reason
            else ""
        )

        raise RuntimeError(
            "Gmail API request failed"
            f"{suffix}: {message}"
        ) from error


def decode_base64url(
    data: str,
):
    """Decode Gmail's URL-safe Base64 payload."""

    padding = "=" * (
        -len(data) % 4
    )

    return base64.urlsafe_b64decode(
        (
            data + padding
        ).encode("utf-8")
    )


def _gmail_lookback_query() -> str:
    """Build the Gmail date-window query."""

    if GMAIL_LOOKBACK_DAYS <= 0:
        return "in:inbox"

    cutoff = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            days=GMAIL_LOOKBACK_DAYS
        )
    )

    return (
        "in:inbox after:"
        f"{cutoff.strftime('%Y/%m/%d')}"
    )


def gmail_list_all_messages(
    access_token: str,
) -> list[dict]:
    """Fetch all Gmail message references."""

    query = _gmail_lookback_query()

    messages = []

    url = (
        f"{GMAIL_API_BASE}/users/me/messages?"
        f"{urlencode({
            'q': query,
            'maxResults': str(
                GMAIL_FETCH_BATCH_SIZE
            ),
        })}"
    )

    while url:

        payload = gmail_api_request(
            url,
            access_token,
        )

        messages.extend(
            payload.get(
                "messages",
                [],
            )
        )

        next_page_token = (
            payload.get(
                "nextPageToken"
            )
        )

        if next_page_token:

            url = (
                f"{GMAIL_API_BASE}/users/me/messages?"
                f"{urlencode({
                    'q': query,
                    'maxResults': str(
                        GMAIL_FETCH_BATCH_SIZE
                    ),
                    'pageToken':
                        next_page_token,
                })}"
            )

        else:

            url = None

    return messages


def gmail_get_message(
    access_token,
    message_id,
):
    """Download and parse a Gmail message."""

    url = (
        f"{GMAIL_API_BASE}/users/me/messages/"
        f"{message_id}?format=raw"
    )

    payload = gmail_api_request(
        url,
        access_token,
    )

    raw = payload.get(
        "raw",
        "",
    )

    return BytesParser(
        policy=policy.default
    ).parsebytes(
        decode_base64url(raw)
    )


# ============================================================================
# Gmail connection state
# ============================================================================

def gmail_connection_is_active(
    connection: dict,
) -> bool:
    """
    Check whether the Gmail connection is currently active.

    is_active is the single source of truth.
    """

    return bool(
        connection.get(
            "is_active",
            False,
        )
    )


def refresh_connection_state(
    connection: dict,
) -> dict | None:
    """
    Re-read the Gmail connection directly from Supabase.

    This is intentionally done immediately before syncing.

    Why?

    The connection returned by list_gmail_connections()
    is only a snapshot.

    Between the moment the snapshot is created and the
    moment the Gmail sync starts, the browser may:

        ACTIVE -> INACTIVE

    or:

        INACTIVE -> ACTIVE

    Therefore the worker must never blindly trust an old
    snapshot.

    The database remains the source of truth.
    """

    owner_email = (
        connection.get("owner_email")
    )

    if not owner_email:
        return None

    try:

        latest = get_gmail_connection(
            owner_email
        )

    except Exception as error:

        print(
            f"[{_now()}] Failed to refresh "
            f"Gmail connection state for "
            f"{owner_email}: {error}"
        )

        return None

    if not latest:

        print(
            f"[{_now()}] Gmail connection "
            f"for {owner_email} no longer exists."
        )

        return None

    return latest


# ============================================================================
# Gmail connection sync
# ============================================================================

def sync_gmail_connection(
    connection: dict,
):
    """
    Synchronize one active Gmail account.

    The connection is re-read immediately before processing
    so stale snapshots cannot cause Gmail ingestion.
    """

    owner_email = connection.get(
        "owner_email",
        "unknown",
    )

    # ------------------------------------------------------------------
    # IMPORTANT:
    #
    # Never trust the connection snapshot received from
    # list_gmail_connections().
    #
    # Re-read it immediately before doing Gmail work.
    # ------------------------------------------------------------------

    latest_connection = (
        refresh_connection_state(
            connection
        )
    )

    if not latest_connection:

        print(
            f"[{_now()}] Could not obtain "
            f"current Gmail connection state "
            f"for {owner_email}. Skipping."
        )

        return

    connection = latest_connection

    # ------------------------------------------------------------------
    # ACTIVE / INACTIVE CHECK
    # ------------------------------------------------------------------

    if not gmail_connection_is_active(
        connection
    ):

        print(
            f"[{_now()}] Gmail connection "
            f"for {owner_email} is INACTIVE. "
            "Skipping Gmail sync."
        )

        return

    owner_email = connection.get(
        "owner_email"
    )

    refresh_token = connection.get(
        "provider_refresh_token"
    )

    access_token = connection.get(
        "provider_access_token"
    )

    if not owner_email or not refresh_token:

        print(
            f"[{_now()}] Skipping Gmail connection "
            f"with missing owner or refresh token: "
            f"{owner_email or 'unknown'}"
        )

        return

    # ------------------------------------------------------------------
    # Resolve Supabase Auth user
    # ------------------------------------------------------------------

    user_id = resolve_user_id(
        connection,
        owner_email,
    )

    if not user_id:

        print(
            f"[{_now()}] ERROR: Could not "
            f"resolve Supabase user_id for "
            f"{owner_email}. "
            "Gmail sync will not upload documents."
        )

        return

    print(
        f"[{_now()}] Gmail owner: "
        f"{owner_email}"
    )

    print(
        f"[{_now()}] Supabase user_id: "
        f"{user_id}"
    )

    # ------------------------------------------------------------------
    # Refresh access token
    # ------------------------------------------------------------------

    try:

        refreshed = refresh_access_token(
            refresh_token
        )

        access_token = (
            refreshed.get(
                "access_token"
            )
            or access_token
        )

        if refreshed.get(
            "access_token"
        ):

            update_gmail_connection_tokens(
                owner_email,
                refreshed[
                    "access_token"
                ],
                refreshed.get(
                    "refresh_token"
                )
                or refresh_token,
            )

    except Exception as error:

        print(
            f"[{_now()}] Unable to refresh "
            f"Gmail token for {owner_email}: "
            f"{error}"
        )

        return

    # ------------------------------------------------------------------
    # IMPORTANT SECOND STATE CHECK
    #
    # Token refresh can take some time.
    #
    # The browser may have gone stale while the token
    # was being refreshed.
    #
    # Re-read the database again before Gmail API work.
    # ------------------------------------------------------------------

    latest_connection = (
        refresh_connection_state(
            connection
        )
    )

    if not latest_connection:

        print(
            f"[{_now()}] Gmail connection "
            f"for {owner_email} disappeared "
            "during token refresh. Skipping."
        )

        return

    if not gmail_connection_is_active(
        latest_connection
    ):

        print(
            f"[{_now()}] Gmail connection "
            f"for {owner_email} became INACTIVE "
            "during token refresh. "
            "Gmail sync cancelled."
        )

        return

    # ------------------------------------------------------------------
    # Gmail message window
    # ------------------------------------------------------------------

    window_desc = (
        f"last {GMAIL_LOOKBACK_DAYS} days "
        f"({_gmail_lookback_query()})"
        if GMAIL_LOOKBACK_DAYS > 0
        else "ALL history (no date cutoff)"
    )

    print(
        f"[{_now()}] Syncing Gmail inbox "
        f"for {owner_email} "
        f"({latest_connection.get('google_email')}) "
        f"— window: {window_desc}"
    )

    try:

        message_refs = (
            gmail_list_all_messages(
                access_token
            )
        )

        print(
            f"[{_now()}] Found "
            f"{len(message_refs)} Gmail "
            f"message(s) for "
            f"{owner_email}"
        )

        processed_count = 0
        skipped_count = 0
        document_count = 0

        # --------------------------------------------------------------
        # Process each message
        # --------------------------------------------------------------

        for message_ref in message_refs:

            # ----------------------------------------------------------
            # IMPORTANT:
            #
            # If the browser becomes stale while a large Gmail
            # mailbox is being processed, stop processing it.
            #
            # This prevents documents from continuing to arrive
            # after the browser has become inactive.
            # ----------------------------------------------------------

            current_connection = (
                refresh_connection_state(
                    latest_connection
                )
            )

            if not current_connection:

                print(
                    f"[{_now()}] Gmail connection "
                    f"for {owner_email} disappeared "
                    "during sync. Stopping."
                )

                return

            if not gmail_connection_is_active(
                current_connection
            ):

                print(
                    f"[{_now()}] Gmail connection "
                    f"for {owner_email} became INACTIVE "
                    "during sync. Stopping immediately."
                )

                return

            gmail_msg_id = (
                message_ref.get("id")
            )

            if not gmail_msg_id:
                continue

            # ----------------------------------------------------------
            # Fast cache check
            # ----------------------------------------------------------

            if _is_cached(
                gmail_msg_id
            ):

                skipped_count += 1
                continue

            # ----------------------------------------------------------
            # Durable DB check
            # ----------------------------------------------------------

            try:

                if is_message_processed(
                    gmail_msg_id
                ):

                    _mark_cached(
                        gmail_msg_id
                    )

                    skipped_count += 1

                    continue

            except Exception:
                pass

            # ----------------------------------------------------------
            # Fetch and process
            # ----------------------------------------------------------

            try:

                message = (
                    gmail_get_message(
                        access_token,
                        gmail_msg_id,
                    )
                )

                raw_bytes = (
                    message.as_bytes()
                )

                result = store_message(
                    message,
                    raw_bytes,
                    gmail_msg_id,
                    owner_email,
                    user_id,
                )

            except Exception as error:

                print(
                    f"[{_now()}] Error "
                    f"processing Gmail message "
                    f"{gmail_msg_id}: "
                    f"{error}"
                )

                continue

            # ----------------------------------------------------------
            # Result
            # ----------------------------------------------------------

            if result.get(
                "skipped"
            ):

                skipped_count += 1

            else:

                processed_count += 1

                document_count += (
                    result.get(
                        "attachment_count",
                        0,
                    )
                )

                print(
                    f"Stored "
                    f"{result['ingestion_id']} "
                    f"("
                    f"{result['attachment_count']}"
                    f" document(s))"
                )

        print(
            f"[{_now()}] Sync complete "
            f"for {owner_email}: "
            f"{processed_count} new "
            f"message(s) with documents, "
            f"{skipped_count} skipped, "
            f"{document_count} document(s) "
            f"uploaded."
        )

    except Exception as error:

        print(
            f"[{_now()}] Gmail sync failed "
            f"for {owner_email}: "
            f"{error}"
        )


# ============================================================================
# Sync orchestrator
# ============================================================================

sync_lock = threading.Lock()


def sync_all_connected_gmail():
    """
    Synchronize all Gmail accounts that are currently active.

    list_gmail_connections() expires stale sessions before
    returning the active connections.

    Each connection is then re-read immediately before syncing.
    """

    if not sync_lock.acquire(
        blocking=False
    ):

        print(
            f"[{_now()}] Gmail sync is "
            "already in progress. "
            "Skipping concurrent request."
        )

        return

    try:

        STORAGE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        _load_processed_cache()

        # --------------------------------------------------------------
        # Database helper:
        #
        # 1. expires stale connections
        # 2. returns active connections only
        # --------------------------------------------------------------

        connections = (
            list_gmail_connections()
        )

        if not connections:

            print(
                f"[{_now()}] No active Gmail "
                "connections. "
                "Skipping sync."
            )

            return

        print(
            f"[{_now()}] Found "
            f"{len(connections)} "
            "active Gmail account(s)"
        )

        for connection in connections:

            # ----------------------------------------------------------
            # Re-check immediately before every account.
            #
            # This prevents a stale snapshot from being used.
            # ----------------------------------------------------------

            current_connection = (
                refresh_connection_state(
                    connection
                )
            )

            if not current_connection:

                continue

            if not gmail_connection_is_active(
                current_connection
            ):

                print(
                    f"[{_now()}] Skipping "
                    f"inactive Gmail connection: "
                    f"{current_connection.get('owner_email', 'unknown')}"
                )

                continue

            sync_gmail_connection(
                current_connection
            )

    finally:

        sync_lock.release()


# ============================================================================
# HTTP trigger server
# ============================================================================

class SyncRequestHandler(
    BaseHTTPRequestHandler
):
    """HTTP endpoint for triggering Gmail sync."""

    def do_POST(self):

        if self.path == "/sync":

            print(
                "Received sync trigger "
                "request from backend API"
            )

            threading.Thread(
                target=sync_all_connected_gmail,
                daemon=True,
            ).start()

            try:

                self.send_response(
                    200
                )

                self.send_header(
                    "Content-Type",
                    "application/json",
                )

                self.end_headers()

                self.wfile.write(
                    b'{"status":"ok"}'
                )

            except Exception as error:

                print(
                    f"Failed to send "
                    f"response: {error}"
                )

        else:

            self.send_response(
                404
            )

            self.end_headers()

    def log_message(
        self,
        format,
        *args,
    ):
        """Suppress noisy HTTP logs."""

        pass


# ============================================================================
# Signal handling
# ============================================================================

def stop(
    _signum,
    _frame,
):
    """Stop the polling loop."""

    global STOP

    STOP = True


# ============================================================================
# Main
# ============================================================================

def main():
    """Start the Gmail polling service."""

    validate_config()

    signal.signal(
        signal.SIGINT,
        stop,
    )

    signal.signal(
        signal.SIGTERM,
        stop,
    )

    # ------------------------------------------------------------------
    # HTTP trigger server
    # ------------------------------------------------------------------

    def run_server():

        try:

            server_address = (
                "127.0.0.1",
                8002,
            )

            httpd = HTTPServer(
                server_address,
                SyncRequestHandler,
            )

            print(
                "Sync trigger server listening "
                "on http://127.0.0.1:8002"
            )

            httpd.serve_forever()

        except Exception as error:

            print(
                f"Failed to start trigger "
                f"server: {error}"
            )

    server_thread = threading.Thread(
        target=run_server,
        daemon=True,
    )

    server_thread.start()

    print(
        "Watching ACTIVE Gmail accounts "
        "(polling every "
        f"{POLL_INTERVAL_SECONDS} seconds)"
    )

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    while not STOP:

        try:

            sync_all_connected_gmail()

        except Exception as error:

            print(
                f"[{_now()}] Mailbox poll failed: "
                f"{error}"
            )

        if not STOP:

            time.sleep(
                POLL_INTERVAL_SECONDS
            )


if __name__ == "__main__":
    main()