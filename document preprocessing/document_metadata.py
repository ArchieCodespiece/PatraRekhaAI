"""
Extract minimal document metadata and save it as JSON.

Output:
    KMRL.metadata.json

Example:
{
    "document_id": "...",
    "document_name": "KMRL.pdf",
    "document_type": "pdf",
    "page_count": 145,
    "language": "en",
    "checksum": "..."
}
"""

from pathlib import Path
import hashlib
import json
import uuid

try:
    from langdetect import detect
except ImportError:
    detect = None


# ---------------------------------------------------------
# SHA256
# ---------------------------------------------------------

def sha256_file(file_path: str) -> str:
    """Return SHA256 checksum of a file."""

    h = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(8192)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


# ---------------------------------------------------------
# Extract Text
# ---------------------------------------------------------

def collect_text(document_json: list) -> str:
    """
    Collect text from OCR JSON list of pages.
    """

    texts = []

    for page in document_json:

        text = page.get("text", "")

        if text:
            texts.append(text)

    return "\n".join(texts)


# ---------------------------------------------------------
# Language
# ---------------------------------------------------------

def detect_language(text: str) -> str:

    if detect is None:
        return "unknown"

    if not text.strip():
        return "unknown"

    try:
        return detect(text)

    except Exception:
        return "unknown"


# ---------------------------------------------------------
# Metadata Extraction
# ---------------------------------------------------------

def extract_document_metadata(
    document_path: str,
    document_json: list,
) -> dict:
    """
    Create metadata dictionary.
    """

    path = Path(document_path)

    full_text = collect_text(document_json)

    metadata = {

        "document_id": str(uuid.uuid4()),

        "document_name": path.name,

        "document_type": path.suffix.lower().replace(".", ""),

        "page_count": len(document_json),

        "language": detect_language(full_text),

        "checksum": sha256_file(document_path),

    }

    return metadata


# ---------------------------------------------------------
# Save
# ---------------------------------------------------------

def save_document_metadata(
    metadata: dict,
    output_path: str,
):
    """
    Save metadata JSON.
    """

    with open(output_path, "w", encoding="utf-8") as f:

        json.dump(
            metadata,
            f,
            indent=4,
            ensure_ascii=False,
        )


# ---------------------------------------------------------
# Convenience Function
# ---------------------------------------------------------

def generate_document_metadata(
    document_path: str,
    json_path: str,
):
    """
    Reads OCR JSON, extracts metadata,
    and writes:

        filename.metadata.json
    """

    with open(json_path, "r", encoding="utf-8") as f:

        document_json = json.load(f)

    metadata = extract_document_metadata(
        document_path,
        document_json,
    )

    output = Path(json_path).with_suffix(".metadata.json")

    save_document_metadata(
        metadata,
        str(output),
    )

    return metadata