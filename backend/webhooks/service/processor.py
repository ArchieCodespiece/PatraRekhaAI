"""Business logic for documents accepted by webhooks."""

import asyncio
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from db.files import FILE_STORAGE_BUCKET, get_document
from db.supabase_client import supabase


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_ENTRYPOINT = PROJECT_ROOT / "main.py"
DEFAULT_PIPELINE_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
TEMP_PDF_DIR = Path(tempfile.gettempdir()) / "patrarekha-webhook-pdfs"


async def process_document(document):
    document_record = await asyncio.to_thread(get_document, document["file_id"])
    if not document_record:
        raise ValueError(f"Document not found: {document['file_id']}")

    content = await asyncio.to_thread(download_document_content, document_record["filename"])
    await run_document_pipeline(document_record, content)


def download_document_content(filename):
    return supabase.storage.from_(FILE_STORAGE_BUCKET).download(filename)


async def run_document_pipeline(document, content):
    """Run the root PatraRekha ingestion pipeline for a webhook document."""
    await asyncio.to_thread(_run_document_pipeline_sync, document, content)


def _run_document_pipeline_sync(document, content):
    pdf_path = write_temp_pdf(document, content)
    logger.info("Running PatraRekha pipeline for document %s at %s", document["file_id"], pdf_path)
    try:
        subprocess.run(
            [
                pipeline_python(),
                str(PIPELINE_ENTRYPOINT),
                str(pdf_path),
                "--cleanup-input",
            ],
            cwd=PROJECT_ROOT,
            env=pipeline_environment(),
            check=True,
        )
    finally:
        cleanup_temp_artifacts(pdf_path)


def write_temp_pdf(document, content):
    if not content:
        raise ValueError(f"Downloaded document is empty: {document['file_id']}")

    filename = safe_filename(document.get("filename") or f"{document['file_id']}.pdf")
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    TEMP_PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = TEMP_PDF_DIR / f"{document['file_id']}-{filename}"
    pdf_path.write_bytes(content)
    return pdf_path


def safe_filename(value):
    return re.sub(r"[^a-zA-Z0-9._-]", "_", value).strip("._") or "document.pdf"


def pipeline_python():
    configured = os.getenv("PIPELINE_PYTHON")
    if configured:
        return configured

    if DEFAULT_PIPELINE_PYTHON.exists():
        return str(DEFAULT_PIPELINE_PYTHON)

    return sys.executable


def pipeline_environment():
    env = os.environ.copy()
    env.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    return env


def cleanup_temp_artifacts(pdf_path):
    for path in (pdf_path, pdf_path.with_suffix(".json")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete temporary pipeline file %s", path, exc_info=True)
