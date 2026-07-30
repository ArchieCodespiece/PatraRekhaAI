"""Sync Gmail inboxes into Supabase-backed document storage.

Strategy
--------
* Fetch ALL messages for each connected Gmail account (read and unread).
* Skip messages that contain no document attachments (PDF, DOCX, etc.).
* Track which Gmail message IDs have already been fully processed via the
  ``processed_gmail_messages`` Supabase table so that:
  - re-runs do not re-upload the same files, and
  - the local processed.json is only used as a fast in-process cache.
* Documents that are already in Supabase (by file_url uniqueness) are detected
  in ``db/files.py``; ``insert_file_record`` returns the existing record and
  re-triggers processing only when ``is_summarized`` or ``is_vectored`` is False.
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
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
SUMMARIZATION_PIPELINE_DIR = PROJECT_ROOT / "AI pipeline" / "summarization-deadline"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SUMMARIZATION_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(SUMMARIZATION_PIPELINE_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(Path(__file__).with_name(".env"), override=True)
load_dotenv(PROJECT_ROOT / ".env")

from db.files import store_file
from db.gmail_connections import (
    list_gmail_connections,
    update_gmail_connection_tokens,
)
from db.processed_messages import (
    is_message_processed,
    mark_message_processed,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STOP = False
_summarization_pipeline = None
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"

# Local cache file – only used as a fast in-process fallback
_STORAGE_DIR_ENV = os.getenv("STORAGE_DIR", "./data")
STORAGE_DIR = Path(_STORAGE_DIR_ENV).resolve()
GMAIL_HISTORY_STATE_FILE = STORAGE_DIR / "gmail_history.json"

# Document MIME types / extensions we consider worth ingesting
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
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt"
}


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


POLL_INTERVAL_SECONDS = env_int("POLL_INTERVAL_SECONDS", 300)
MAX_ATTACHMENT_BYTES = env_int("MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024)
# How many messages to fetch per Gmail API call (max 500 per Google's docs)
GMAIL_FETCH_BATCH_SIZE = env_int("GMAIL_FETCH_BATCH_SIZE", 100)
# Only look back this many days when fetching messages.
# On first login this prevents ingesting years of historical mail.
# Set to 0 in .env to disable the cutoff and fetch ALL history.
GMAIL_LOOKBACK_DAYS = env_int("GMAIL_LOOKBACK_DAYS", 60)
ALLOWED_SENDERS = {
    sender.strip().lower()
    for sender in os.getenv("ALLOWED_SENDERS", "").split(",")
    if sender.strip()
}


def validate_config():
    missing = [name for name, value in {
        "GOOGLE_CLIENT_ID": os.getenv("GOOGLE_CLIENT_ID"),
        "GOOGLE_CLIENT_SECRET": os.getenv("GOOGLE_CLIENT_SECRET"),
    }.items() if not value]
    if missing:
        raise ValueError(f"Missing configuration: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def safe_filename(value, fallback):
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", value or fallback)
    return name or fallback


def sender_address(message):
    address = message.get("From", "")
    match = re.search(r"<([^>]+)>", address)
    return (match.group(1) if match else address).strip().lower()


def message_id_for(message, raw_message):
    return message.get("Message-ID") or hashlib.sha256(raw_message).hexdigest()


def is_document_attachment(filename: str, content_type: str) -> bool:
    """Return True if the attachment looks like a processable document."""
    ext = Path(filename or "").suffix.lower()
    return ext in DOCUMENT_EXTENSIONS or content_type in DOCUMENT_CONTENT_TYPES


def is_pdf_attachment(filename, content_type):
    return filename.lower().endswith(".pdf") or content_type == "application/pdf"


# ---------------------------------------------------------------------------
# Local processed-state cache (fast in-process set, backed by Supabase)
# ---------------------------------------------------------------------------

_processed_ids_cache: set[str] = set()
_cache_lock = threading.Lock()


def _load_processed_cache():
    """Seed the in-process cache from the local JSON file (best effort)."""
    path = STORAGE_DIR / "processed.json"
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        with _cache_lock:
            _processed_ids_cache.update(data.get("message_ids", []))
    except Exception:
        pass


def _persist_processed_cache():
    """Write the in-process cache to disk with proper file locking."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = STORAGE_DIR / "processed.json"
    tmp_path = path.with_suffix(".tmp")

    # Windows file lock via msvcrt
    try:
        with open(str(tmp_path), "w", encoding="utf-8") as fh:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                with _cache_lock:
                    ids = list(_processed_ids_cache)
                json.dump({"message_ids": ids}, fh, indent=2)
                fh.write("\n")
            finally:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
        tmp_path.replace(path)
    except OSError:
        # Another process is writing – skip this write, not critical
        pass


def _mark_cached(gmail_msg_id: str):
    with _cache_lock:
        _processed_ids_cache.add(gmail_msg_id)
    _persist_processed_cache()


def _is_cached(gmail_msg_id: str) -> bool:
    with _cache_lock:
        return gmail_msg_id in _processed_ids_cache


# ---------------------------------------------------------------------------
# Summarization pipeline
# ---------------------------------------------------------------------------

def load_summarization_pipeline():
    global _summarization_pipeline
    if _summarization_pipeline is None:
        from pipeline import process_pdf_metadata
        _summarization_pipeline = process_pdf_metadata
    return _summarization_pipeline


def process_metadata_for_attachment(file_record, filename, content):
    if not file_record or not file_record.get("file_id"):
        return
    with tempfile.TemporaryDirectory(prefix="patrarekha-metadata-") as temp_dir:
        pdf_path = Path(temp_dir) / filename
        pdf_path.write_bytes(content)
        process_pdf_metadata = load_summarization_pipeline()
        process_pdf_metadata(pdf_path=pdf_path, file_id=str(file_record["file_id"]))


# ---------------------------------------------------------------------------
# Message processing
# ---------------------------------------------------------------------------

def store_message(message, raw_message, gmail_msg_id: str, owner_email: str):
    """Process a single email message.

    Returns a dict with:
      - ``skipped`` (bool) if the message was not processed
      - ``no_documents`` (bool) if there were no document attachments
      - ``ingestion_id`` / ``attachment_count`` on success
    """
    email_message_id = message_id_for(message, raw_message)

    # 1. Check in-process cache first (fast path)
    if _is_cached(gmail_msg_id):
        return {"skipped": True, "reason": "already_processed_cache"}

    # 2. Check Supabase for durability (survives restarts)
    try:
        if is_message_processed(gmail_msg_id):
            _mark_cached(gmail_msg_id)  # warm the cache
            return {"skipped": True, "reason": "already_processed_db"}
    except Exception as err:
        print(f"Warning: could not check processed status for {gmail_msg_id}: {err}")

    # 3. Sender allow-list check
    sender = sender_address(message)
    if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
        print(f"Skipping message from non-allowed sender: {sender or 'unknown'}")
        _mark_cached(gmail_msg_id)
        try:
            mark_message_processed(gmail_msg_id, owner_email, skipped=True, skip_reason="sender_not_allowed")
        except Exception:
            pass
        return {"skipped": True, "reason": "sender_not_allowed"}

    # 4. Scan for document attachments
    document_attachments = []
    for index, attachment in enumerate(message.iter_attachments(), start=1):
        content = attachment.get_payload(decode=True) or b""
        original_name = attachment.get_filename() or f"attachment-{index}"
        content_type = attachment.get_content_type()

        if not is_document_attachment(original_name, content_type):
            continue  # skip non-document attachments (images, etc.)

        if len(content) > MAX_ATTACHMENT_BYTES:
            print(f"Skipping oversized attachment: {original_name} ({len(content)} bytes)")
            continue

        document_attachments.append((attachment, original_name, content_type, content))

    # 5. If no document attachments – mark as processed and skip silently
    if not document_attachments:
        _mark_cached(gmail_msg_id)
        try:
            mark_message_processed(gmail_msg_id, owner_email, skipped=True, skip_reason="no_documents")
        except Exception:
            pass
        return {"skipped": True, "no_documents": True}

    # 6. Process each document attachment
    received_at = datetime.now(timezone.utc)
    ingestion_id = (
        f"{received_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{hashlib.sha256(email_message_id.encode()).hexdigest()[:12]}"
    )
    stored_names = []
    for _attachment, original_name, content_type, content in document_attachments:
        content_hash = hashlib.sha256(content).hexdigest()
        stored_name = f"{content_hash[:12]}-{safe_filename(original_name, 'attachment')}"
        # Pass full content_hash so DB layer can deduplicate by bytes,
        # not just by filename/URL (handles same doc sent by two people).
        file_record = store_file(
            stored_name, content, content_type,
            owner_email=owner_email,
            content_hash=content_hash,
        )

        if is_pdf_attachment(stored_name, content_type):
            try:
                process_metadata_for_attachment(file_record, stored_name, content)
            except Exception as error:
                print(f"Metadata extraction failed for {stored_name}: {error}")

        stored_names.append(stored_name)

    # 7. Persist processed status
    _mark_cached(gmail_msg_id)
    try:
        mark_message_processed(gmail_msg_id, owner_email)
    except Exception as err:
        print(f"Warning: could not persist processed status for {gmail_msg_id}: {err}")

    return {"ingestion_id": ingestion_id, "attachment_count": len(stored_names)}


# ---------------------------------------------------------------------------
# Gmail API helpers
# ---------------------------------------------------------------------------

def refresh_access_token(refresh_token):
    form = urlencode({
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = Request(
        GOOGLE_TOKEN_URL,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_http_error(error):
    try:
        payload = error.read().decode("utf-8")
        data = json.loads(payload)
        reason = data.get("error", {}).get("errors", [{}])[0].get("reason")
        message = data.get("error", {}).get("message") or payload
        return reason, message
    except Exception:
        return None, str(error)


def gmail_api_request(url, access_token):
    request = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        reason, message = _read_http_error(error)
        suffix = f" ({reason})" if reason else ""
        raise RuntimeError(f"Gmail API request failed{suffix}: {message}") from error


def decode_base64url(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _gmail_lookback_query() -> str:
    """Build a Gmail search query that restricts messages to the lookback window.

    Returns ``'in:inbox'`` when ``GMAIL_LOOKBACK_DAYS`` is 0 (no cutoff).
    Otherwise returns ``'in:inbox after:YYYY/MM/DD'`` using the date
    ``GMAIL_LOOKBACK_DAYS`` days ago, so only recent emails are fetched.
    """
    if GMAIL_LOOKBACK_DAYS <= 0:
        return "in:inbox"
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=GMAIL_LOOKBACK_DAYS)
    return f"in:inbox after:{cutoff.strftime('%Y/%m/%d')}"


def gmail_list_all_messages(access_token: str) -> list[dict]:
    """Fetch all message refs within the lookback window, paginating automatically.

    Uses Gmail's ``after:YYYY/MM/DD`` search operator to restrict results to
    the configured window (default: last 60 days). This avoids processing years
    of historical mail on the very first login.
    """
    query = _gmail_lookback_query()
    messages = []
    url = (
        f"{GMAIL_API_BASE}/users/me/messages?"
        f"{urlencode({'q': query, 'maxResults': str(GMAIL_FETCH_BATCH_SIZE)})}"
    )
    while url:
        payload = gmail_api_request(url, access_token)
        messages.extend(payload.get("messages", []))
        next_page_token = payload.get("nextPageToken")
        if next_page_token:
            url = (
                f"{GMAIL_API_BASE}/users/me/messages?"
                f"{urlencode({'q': query, 'maxResults': str(GMAIL_FETCH_BATCH_SIZE), 'pageToken': next_page_token})}"
            )
        else:
            url = None
    return messages


def gmail_get_message(access_token, message_id):
    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}?format=raw"
    payload = gmail_api_request(url, access_token)
    raw = payload.get("raw", "")
    return BytesParser(policy=policy.default).parsebytes(decode_base64url(raw))


# ---------------------------------------------------------------------------
# Per-connection sync
# ---------------------------------------------------------------------------

def sync_gmail_connection(connection: dict):
    owner_email = connection.get("owner_email")
    refresh_token = connection.get("provider_refresh_token")
    access_token = connection.get("provider_access_token")

    if not owner_email or not refresh_token:
        print(f"Skipping Gmail connection with missing owner or refresh token: {owner_email or 'unknown'}")
        return

    # Refresh the access token
    try:
        refreshed = refresh_access_token(refresh_token)
        access_token = refreshed.get("access_token") or access_token
        if refreshed.get("access_token"):
            update_gmail_connection_tokens(
                owner_email,
                refreshed["access_token"],
                refreshed.get("refresh_token") or refresh_token,
            )
    except Exception as error:
        print(f"Unable to refresh Gmail token for {owner_email}: {error}")
        return

    window_desc = (
        f"last {GMAIL_LOOKBACK_DAYS} days ({_gmail_lookback_query()})"
        if GMAIL_LOOKBACK_DAYS > 0
        else "ALL history (no date cutoff)"
    )
    print(f"Syncing Gmail inbox for {owner_email} ({connection.get('google_email')}) — window: {window_desc}")
    try:
        message_refs = gmail_list_all_messages(access_token)
        print(f"Found {len(message_refs)} Gmail message(s) for {owner_email}")

        processed_count = 0
        skipped_count = 0
        document_count = 0

        for message_ref in message_refs:
            gmail_msg_id = message_ref.get("id")
            if not gmail_msg_id:
                continue

            # Fast check: already processed?
            if _is_cached(gmail_msg_id):
                skipped_count += 1
                continue
            try:
                if is_message_processed(gmail_msg_id):
                    _mark_cached(gmail_msg_id)
                    skipped_count += 1
                    continue
            except Exception:
                pass  # Network issue – will try again on next poll

            # Fetch and process the message
            try:
                message = gmail_get_message(access_token, gmail_msg_id)
                raw_bytes = message.as_bytes()
                result = store_message(message, raw_bytes, gmail_msg_id, owner_email)
            except Exception as error:
                print(f"Error processing Gmail message {gmail_msg_id}: {error}")
                continue

            if result.get("skipped"):
                skipped_count += 1
                if not result.get("no_documents"):
                    pass  # already logged inside store_message
            else:
                processed_count += 1
                document_count += result.get("attachment_count", 0)
                print(
                    f"Stored {result['ingestion_id']} "
                    f"({result['attachment_count']} document(s))"
                )

        print(
            f"Sync complete for {owner_email}: "
            f"{processed_count} new message(s) with documents, "
            f"{skipped_count} skipped, "
            f"{document_count} document(s) uploaded."
        )

    except Exception as error:
        print(f"Gmail sync failed for {owner_email}: {error}")


# ---------------------------------------------------------------------------
# Sync orchestrator
# ---------------------------------------------------------------------------

sync_lock = threading.Lock()


def sync_all_connected_gmail():
    if not sync_lock.acquire(blocking=False):
        print("Gmail sync is already in progress. Skipping concurrent request.")
        return
    try:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        _load_processed_cache()  # seed from disk
        connections = list_gmail_connections()

        if not connections:
            print("No connected Gmail accounts found. Skipping sync.")
            return

        print(f"Found {len(connections)} connected Gmail account(s)")
        for connection in connections:
            sync_gmail_connection(connection)
    finally:
        sync_lock.release()


# ---------------------------------------------------------------------------
# HTTP trigger server (called by the backend API)
# ---------------------------------------------------------------------------

class SyncRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/sync":
            print("Received sync trigger request from backend API")
            threading.Thread(target=sync_all_connected_gmail, daemon=True).start()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                print(f"Failed to send response: {e}")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP logs


# ---------------------------------------------------------------------------
# Signal handling & main loop
# ---------------------------------------------------------------------------

def stop(_signum, _frame):
    global STOP
    STOP = True


def main():
    validate_config()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def run_server():
        try:
            server_address = ("127.0.0.1", 8002)
            httpd = HTTPServer(server_address, SyncRequestHandler)
            print("Sync trigger server listening on http://127.0.0.1:8002")
            httpd.serve_forever()
        except Exception as error:
            print(f"Failed to start trigger server: {error}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    print("Watching connected Gmail accounts (polling ALL messages every cycle)")
    while not STOP:
        try:
            sync_all_connected_gmail()
        except Exception as error:
            print(f"Mailbox poll failed: {error}")
        if not STOP:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
