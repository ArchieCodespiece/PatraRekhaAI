"""Sync Gmail inboxes into Supabase-backed document storage."""

from __future__ import annotations

import base64
import hashlib
import imaplib
import json
import os
import re
import signal
import sys
import tempfile
import time
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

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
from db.gmail_connections import list_gmail_connections, update_gmail_connection_tokens


STOP = False
_summarization_pipeline = None
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
GMAIL_HISTORY_STATE_FILE = Path(os.getenv("GMAIL_HISTORY_STATE_FILE", str(STORAGE_DIR := Path(os.getenv("STORAGE_DIR", "./data")).resolve() / "gmail_history.json")))


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = env_int("IMAP_PORT", 993)
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")
IMAP_MAILBOX = os.getenv("IMAP_MAILBOX", "INBOX")
POLL_INTERVAL_SECONDS = env_int("POLL_INTERVAL_SECONDS", 30)
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./data")).resolve()
MAX_ATTACHMENT_BYTES = env_int("MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024)
ALLOWED_SENDERS = {
    sender.strip().lower()
    for sender in os.getenv("ALLOWED_SENDERS", "").split(",")
    if sender.strip()
}


def validate_config():
    missing = [name for name, value in {
        "IMAP_HOST": IMAP_HOST,
        "IMAP_USER": IMAP_USER,
        "IMAP_PASSWORD": IMAP_PASSWORD,
    }.items() if not value]
    if missing:
        raise ValueError(f"Missing configuration: {', '.join(missing)}")


def safe_filename(value, fallback):
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", value or fallback)
    return name or fallback


def load_state():
    path = STORAGE_DIR / "processed.json"
    if not path.exists():
        return {"message_ids": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state):
    path = STORAGE_DIR / "processed.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_gmail_history_state():
    if not GMAIL_HISTORY_STATE_FILE.exists():
        return {}
    return json.loads(GMAIL_HISTORY_STATE_FILE.read_text(encoding="utf-8"))


def save_gmail_history_state(state):
    GMAIL_HISTORY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = GMAIL_HISTORY_STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(GMAIL_HISTORY_STATE_FILE)


def sender_address(message):
    address = message.get("From", "")
    match = re.search(r"<([^>]+)>", address)
    return (match.group(1) if match else address).strip().lower()


def message_id_for(message, raw_message):
    return message.get("Message-ID") or hashlib.sha256(raw_message).hexdigest()


def load_summarization_pipeline():
    global _summarization_pipeline

    if _summarization_pipeline is None:
        from pipeline import process_pdf_metadata

        _summarization_pipeline = process_pdf_metadata

    return _summarization_pipeline


def is_pdf_attachment(filename, content_type):
    return filename.lower().endswith(".pdf") or content_type == "application/pdf"


def process_metadata_for_attachment(file_record, filename, content):
    if not file_record or not file_record.get("file_id"):
        return

    with tempfile.TemporaryDirectory(prefix="patrarekha-metadata-") as temp_dir:
        pdf_path = Path(temp_dir) / filename
        pdf_path.write_bytes(content)

        process_pdf_metadata = load_summarization_pipeline()
        process_pdf_metadata(pdf_path=pdf_path, file_id=str(file_record["file_id"]))


def store_message(message, raw_message, state, uid, owner_email):
    message_id = message_id_for(message, raw_message)
    if message_id in state["message_ids"]:
        return {"skipped": True}

    sender = sender_address(message)
    if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
        print(f"Skipping message from non-allowed sender: {sender or 'unknown'}")
        print(f"Allowed senders: {', '.join(sorted(ALLOWED_SENDERS))}")
        state["message_ids"].append(message_id)
        save_state(state)
        return {"skipped": True, "rejected": True}

    received_at = datetime.now(timezone.utc)
    ingestion_id = f"{received_at.strftime('%Y%m%dT%H%M%SZ')}-{hashlib.sha256(message_id.encode()).hexdigest()[:12]}"
    attachments = []
    for index, attachment in enumerate(message.iter_attachments(), start=1):
        content = attachment.get_payload(decode=True) or b""
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise ValueError(f"Attachment exceeds size limit: {attachment.get_filename() or index}")

        content_hash = hashlib.sha256(content).hexdigest()
        original_name = attachment.get_filename() or f"attachment-{index}"
        content_type = attachment.get_content_type()
        stored_name = f"{content_hash[:12]}-{safe_filename(original_name, f'attachment-{index}')}"
        file_record = store_file(stored_name, content, content_type, owner_email=owner_email)

        if is_pdf_attachment(stored_name, content_type):
            try:
                process_metadata_for_attachment(file_record, stored_name, content)
            except Exception as error:
                print(f"Metadata extraction failed for {stored_name}: {error}")

        attachments.append(stored_name)

    state["message_ids"].append(message_id)
    save_state(state)
    return {"ingestion_id": ingestion_id, "attachment_count": len(attachments)}


def fetch_unread_messages(mailbox, state, owner_email):
    status, data = mailbox.uid("search", None, "UNSEEN")
    if status != "OK":
        raise RuntimeError("Unable to search the IMAP mailbox")

    message_ids = data[0].split() if data and data[0] else []
    print(f"Found {len(message_ids)} unread message(s) in {IMAP_MAILBOX} for {owner_email}")

    for uid_bytes in message_ids:
        uid = uid_bytes.decode("ascii")
        status, fetched = mailbox.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            raise RuntimeError(f"Unable to fetch IMAP message {uid}")
        raw_message = next((item[1] for item in fetched if isinstance(item, tuple)), None)
        if not raw_message:
            continue

        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        result = store_message(message, raw_message, state, uid, owner_email)
        mailbox.uid("store", uid, "+FLAGS", r"(\Seen)")
        if not result.get("skipped"):
            print(f"Stored {result['ingestion_id']} ({result['attachment_count']} attachment(s))")


def refresh_access_token(refresh_token):
    form = urlencode({
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = Request(GOOGLE_TOKEN_URL, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
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


def gmail_api_bytes(url, access_token):
    request = Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as error:
        reason, message = _read_http_error(error)
        suffix = f" ({reason})" if reason else ""
        raise RuntimeError(f"Gmail API request failed{suffix}: {message}") from error

def decode_base64url(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def gmail_list_messages(access_token, query="is:unread in:inbox"):
    url = f"{GMAIL_API_BASE}/users/me/messages?{urlencode({'q': query, 'maxResults': '20'})}"
    payload = gmail_api_request(url, access_token)
    return payload.get("messages", [])


def gmail_get_message(access_token, message_id):
    url = f"{GMAIL_API_BASE}/users/me/messages/{message_id}?format=raw"
    payload = gmail_api_request(url, access_token)
    raw = payload.get("raw", "")
    return BytesParser(policy=policy.default).parsebytes(decode_base64url(raw))


def sync_gmail_connection(connection, state):
    owner_email = connection.get("owner_email")
    refresh_token = connection.get("provider_refresh_token")
    access_token = connection.get("provider_access_token")

    if not owner_email or not refresh_token:
        print(f"Skipping Gmail connection with missing owner or refresh token: {owner_email or 'unknown'}")
        return

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

    history_state = load_gmail_history_state()
    last_history_id = history_state.get(owner_email)

    print(f"Syncing Gmail inbox for {owner_email} ({connection.get('google_email')})")
    try:
        messages = gmail_list_messages(access_token)
        print(f"Found {len(messages)} unread Gmail message(s) for {owner_email}")
        for message_ref in messages:
            message_id = message_ref.get("id")
            if not message_id:
                continue
            message = gmail_get_message(access_token, message_id)
            raw_bytes = message.as_bytes()
            result = store_message(message, raw_bytes, state, message_id, owner_email)
            if not result.get("skipped"):
                print(f"Stored {result['ingestion_id']} ({result['attachment_count']} attachment(s))")
    except Exception as error:
        print(f"Gmail sync failed for {owner_email}: {error}")
        return

    if last_history_id:
        history_state[owner_email] = last_history_id
        save_gmail_history_state(history_state)


def sync_all_connected_gmail():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    connections = list_gmail_connections()

    if not connections:
        print("No connected Gmail accounts found. Skipping sync.")
        return

    print(f"Found {len(connections)} connected Gmail account(s)")
    for connection in connections:
        sync_gmail_connection(connection, state)


def stop(_signum, _frame):
    global STOP
    STOP = True


def main():
    validate_config()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print("Watching connected Gmail accounts")
    while not STOP:
        try:
            sync_all_connected_gmail()
        except Exception as error:
            print(f"Mailbox poll failed: {error}")
        if not STOP:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
