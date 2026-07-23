"""Poll an IMAP inbox and upload email attachments to Supabase."""

import hashlib
import imaplib
import json
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(Path(__file__).with_name(".env"), override=True)

from db.files import store_file


STOP = False


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


def sender_address(message):
    address = message.get("From", "")
    match = re.search(r"<([^>]+)>", address)
    return (match.group(1) if match else address).strip().lower()


def message_id_for(message, raw_message):
    return message.get("Message-ID") or hashlib.sha256(raw_message).hexdigest()


def store_message(message, raw_message, state, uid):
    message_id = message_id_for(message, raw_message)
    if message_id in state["message_ids"]:
        return {"skipped": True}

    sender = sender_address(message)
    if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
        print(f"Skipping message from non-allowed sender: {sender or 'unknown'}")
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
        stored_name = f"{content_hash[:12]}-{safe_filename(original_name, f'attachment-{index}')}"
        store_file(stored_name, content, attachment.get_content_type())
        attachments.append(stored_name)

    state["message_ids"].append(message_id)
    save_state(state)
    return {"ingestion_id": ingestion_id, "attachment_count": len(attachments)}


def fetch_unread_messages(mailbox, state):
    status, data = mailbox.uid("search", None, "UNSEEN")
    if status != "OK":
        raise RuntimeError("Unable to search the IMAP mailbox")

    for uid_bytes in data[0].split():
        uid = uid_bytes.decode("ascii")
        status, fetched = mailbox.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            raise RuntimeError(f"Unable to fetch IMAP message {uid}")
        raw_message = next((item[1] for item in fetched if isinstance(item, tuple)), None)
        if not raw_message:
            continue

        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        result = store_message(message, raw_message, state, uid)
        mailbox.uid("store", uid, "+FLAGS", "(\\Seen)")
        if not result.get("skipped"):
            print(f"Stored {result['ingestion_id']} ({result['attachment_count']} attachment(s))")


def poll_once():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    mailbox = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    try:
        mailbox.login(IMAP_USER, IMAP_PASSWORD)
        status, _ = mailbox.select(IMAP_MAILBOX)
        if status != "OK":
            raise RuntimeError(f"Unable to select mailbox: {IMAP_MAILBOX}")
        fetch_unread_messages(mailbox, state)
    finally:
        try:
            mailbox.logout()
        except imaplib.IMAP4.error:
            pass


def stop(_signum, _frame):
    global STOP
    STOP = True


def main():
    validate_config()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"Watching {IMAP_MAILBOX} on {IMAP_HOST}")
    while not STOP:
        try:
            poll_once()
        except Exception as error:  # Keep polling after transient network failures.
            print(f"Mailbox poll failed: {error}")
        if not STOP:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
