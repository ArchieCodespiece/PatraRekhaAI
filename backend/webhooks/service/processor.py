
"""Business logic for documents accepted by webhooks."""

import asyncio
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from db.files import get_bucket_name, get_document
from db.supabase_client import supabase


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Project / pipeline configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

PIPELINE_ENTRYPOINT = PROJECT_ROOT / "main.py"

DEFAULT_PIPELINE_PYTHON = (
    PROJECT_ROOT / ".venv" / "bin" / "python"
)

DEFAULT_WINDOWS_PIPELINE_PYTHON = (
    PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
)

TEMP_PDF_DIR = (
    Path(tempfile.gettempdir())
    / "patrarekha-webhook-pdfs"
)


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------

async def process_document(document):
    """
    Process a document received through the document queue.

    The document record is loaded authoritatively from the
    files table before downloading and processing.
    """

    file_id = document.get("file_id")

    logger.info(
        "=================================================="
    )
    logger.info("PROCESS_DOCUMENT START")
    logger.info("file_id=%s", file_id)
    logger.info("filename=%s", document.get("filename"))
    logger.info("user_id=%s", document.get("user_id"))
    logger.info("owner_email=%s", document.get("owner_email"))
    logger.info(
        "=================================================="
    )

    if not file_id:
        raise ValueError(
            "Document is missing 'file_id'."
        )

    # ----------------------------------------------------------
    # Load authoritative DB record
    # ----------------------------------------------------------

    document_record = await asyncio.to_thread(
        get_document,
        file_id,
        user_id=document.get("user_id"),
        owner_email=document.get("owner_email"),
    )

    if not document_record:
        raise ValueError(
            f"Document not found: {file_id}"
        )

    logger.info(
        "Document found in files table: %s",
        document_record,
    )

    # ----------------------------------------------------------
    # User ID
    # ----------------------------------------------------------

    user_id = document_record.get("user_id")

    if not user_id:
        raise ValueError(
            f"Document {file_id} does not have a user_id."
        )

    # ----------------------------------------------------------
    # Download
    # ----------------------------------------------------------

    content = await asyncio.to_thread(
        download_document_content,
        document_record["filename"],
        user_id,
    )

    if not content:
        raise ValueError(
            f"Downloaded document is empty: {file_id}"
        )

    logger.info(
        "Downloaded %s bytes for document %s",
        len(content),
        file_id,
    )

    # ----------------------------------------------------------
    # Run AI pipeline
    # ----------------------------------------------------------

    await run_document_pipeline(
        document_record,
        content,
    )

    logger.info(
        "AI pipeline completed for document %s",
        file_id,
    )

    # ----------------------------------------------------------
    # Run summarization / deadline extraction
    # ----------------------------------------------------------
    #
    # The main pipeline handles OCR, chunking, embedding and
    # Pinecone upserts but does NOT extract document metadata.
    #
    # We run the summarization pipeline here so that the
    # frontend can display document details (summary + deadlines)
    # after the document finishes processing.
    #
    # If metadata already exists (e.g. from a previous run or
    # from Gmail ingestion), skip to avoid duplicate work.

    await _run_summarization_if_needed(
        document_record,
        content,
    )


# ---------------------------------------------------------------------------
# Storage download
# ---------------------------------------------------------------------------

def download_document_content(
    filename,
    user_id,
):
    """
    Download a user's document from the shared Supabase bucket.

    Storage structure:

        public/
            documents/
                <user_id>/
                    <filename>
    """

    if not user_id:
        raise ValueError(
            "user_id is required to download a document."
        )

    if not filename:
        raise ValueError(
            "filename is required to download a document."
        )

    bucket = get_bucket_name()

    # Keep the filename consistent with the storage layer.
    filename = os.path.basename(filename)

    storage_path = (
        f"documents/{user_id}/{filename}"
    )

    logger.info(
        "Downloading document from Supabase Storage: "
        "bucket=%s path=%s",
        bucket,
        storage_path,
    )

    return (
        supabase.storage
        .from_(bucket)
        .download(storage_path)
    )


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

async def run_document_pipeline(
    document,
    content,
):
    """
    Run the root PatraRekha ingestion pipeline for a webhook document.
    """

    await asyncio.to_thread(
        _run_document_pipeline_sync,
        document,
        content,
    )


def _run_document_pipeline_sync(
    document,
    content,
):
    """
    Synchronous wrapper around the root document pipeline.
    """

    pdf_path = write_temp_pdf(
        document,
        content,
    )

    logger.info(
        "Running PatraRekha pipeline for document %s at %s",
        document["file_id"],
        pdf_path,
    )

    try:

        # --------------------------------------------------------------
        # Build pipeline command
        # --------------------------------------------------------------

        cmd = [
            pipeline_python(),
            str(PIPELINE_ENTRYPOINT),
            str(pdf_path),
            "--cleanup-input",
        ]

        # --------------------------------------------------------------
        # Pass user information to the pipeline
        # --------------------------------------------------------------

        user_id = document.get("user_id")

        if user_id:
            cmd.extend(
                [
                    "--user-id",
                    str(user_id),
                ]
            )

        # --------------------------------------------------------------
        # Keep email for backwards compatibility / metadata
        # --------------------------------------------------------------

        owner_email = document.get("owner_email")

        if owner_email:
            cmd.extend(
                [
                    "--owner-email",
                    owner_email,
                ]
            )

        # --------------------------------------------------------------
        # Always pass file ID
        # --------------------------------------------------------------

        cmd.extend(
            [
                "--file-id",
                str(document["file_id"]),
            ]
        )

        logger.info(
            "Starting pipeline: %s",
            " ".join(map(str, cmd)),
        )

        # --------------------------------------------------------------
        # Run pipeline
        # --------------------------------------------------------------

        subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=pipeline_environment(),
            check=True,
        )

    finally:

        # --------------------------------------------------------------
        # Remove temporary PDF / artifacts
        # --------------------------------------------------------------

        cleanup_temp_artifacts(
            pdf_path
        )


async def _run_summarization_if_needed(
    document_record,
    content,
):
    """
    Run the summarization/deadline extraction pipeline if the
    document does not already have metadata stored.
    """

    file_id = str(
        document_record.get("file_id") or ""
    )

    if not file_id:
        return

    # ------------------------------------------------------------------
    # Check whether metadata already exists
    # ------------------------------------------------------------------

    existing_metadata = await asyncio.to_thread(
        _lookup_document_metadata,
        file_id,
    )

    if existing_metadata:
        logger.info(
            "Metadata already exists for document %s; "
            "skipping summarization.",
            file_id,
        )
        return

    # ------------------------------------------------------------------
    # Write a temporary PDF for the summarization pipeline
    # ------------------------------------------------------------------

    pdf_path = write_temp_pdf(
        document_record,
        content,
    )

    logger.info(
        "Running summarization pipeline for document %s",
        file_id,
    )

    try:

        await asyncio.to_thread(
            _run_summarization_sync,
            pdf_path,
            file_id,
        )

    except Exception as exc:

        logger.error(
            "Summarization failed for document %s: %s",
            file_id,
            exc,
        )

    finally:

        cleanup_temp_artifacts(
            pdf_path
        )


def _lookup_document_metadata(file_id):
    """
    Return the existing metadata row for a file, or None.
    """

    from db.document_metadata import (
        list_document_metadata_by_file_ids,
    )

    rows = list_document_metadata_by_file_ids(
        [file_id]
    )

    return rows[0] if rows else None


def _run_summarization_sync(document_path, file_id):
    """
    Synchronous wrapper around the summarization pipeline.
    """

    import sys
    from pathlib import Path

    summarization_dir = (
        Path(__file__).resolve().parents[3]
        / "AI pipeline"
        / "summarization-deadline"
    )

    if str(summarization_dir) not in sys.path:
        sys.path.insert(0, str(summarization_dir))

    from pipeline import process_pdf_metadata

    process_pdf_metadata(
        document_path=document_path,
        file_id=file_id,
    )


# ---------------------------------------------------------------------------
# Temporary PDF handling
# ---------------------------------------------------------------------------

def write_temp_pdf(
    document,
    content,
):
    """
    Write downloaded document content to a temporary file.

    Non-PDF documents are converted to PDF so the pipeline can
    process them unchanged.
    """

    if not content:
        raise ValueError(
            "Downloaded document is empty: "
            f"{document['file_id']}"
        )

    from document_preprocessing.converter import (
        convert_to_pdf,
        is_supported_document,
    )

    filename = safe_filename(
        document.get("filename")
        or f"{document['file_id']}"
    )

    TEMP_PDF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_path = (
        TEMP_PDF_DIR
        / f"{document['file_id']}-{filename}"
    )

    original_path.write_bytes(content)

    if (
        not is_supported_document(original_path)
        or original_path.suffix.lower() != ".pdf"
    ):
        pdf_path = (
            TEMP_PDF_DIR
            / f"{document['file_id']}-{original_path.stem}.pdf"
        )
        convert_to_pdf(original_path, pdf_path)

        # On Windows the file can be temporarily locked by
        # antivirus or another process after conversion.
        # Retry a few times before giving up.
        _safe_unlink(original_path)

        return pdf_path

    return original_path


def _safe_unlink(path, attempts=3, delay=0.5):
    """
    Remove a file, retrying on Windows permission errors.
    """
    import time

    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt < attempts - 1:
                time.sleep(delay)
            else:
                pass


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

def safe_filename(value):
    """
    Sanitize a filename so it is safe for local temporary storage.
    """

    value = str(value)

    sanitized = re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        value,
    )

    sanitized = sanitized.strip("._")

    return sanitized or "document.pdf"


# ---------------------------------------------------------------------------
# Pipeline Python executable
# ---------------------------------------------------------------------------

def pipeline_python():
    """
    Determine which Python executable should run the pipeline.

    Priority:

        1. PIPELINE_PYTHON environment variable
        2. Platform-specific .venv Python
        3. Current Python interpreter
    """

    configured = os.getenv(
        "PIPELINE_PYTHON"
    )

    if configured:
        return configured

    # --------------------------------------------------------------
    # Windows
    # --------------------------------------------------------------

    if sys.platform == "win32":

        candidate = (
            DEFAULT_WINDOWS_PIPELINE_PYTHON
        )

    # --------------------------------------------------------------
    # Linux / macOS / WSL
    # --------------------------------------------------------------

    else:

        candidate = (
            DEFAULT_PIPELINE_PYTHON
        )

    if candidate.exists():
        return str(candidate)

    return sys.executable


# ---------------------------------------------------------------------------
# Pipeline environment
# ---------------------------------------------------------------------------

def pipeline_environment():
    """
    Prepare environment variables for the document pipeline.
    """

    env = os.environ.copy()

    env.setdefault(
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK",
        "True",
    )

    return env


# ---------------------------------------------------------------------------
# Temporary artifact cleanup
# ---------------------------------------------------------------------------

def cleanup_temp_artifacts(
    pdf_path,
):
    """
    Remove temporary PDF and any JSON artifact produced beside it.
    """

    for path in (
        pdf_path,
        pdf_path.with_suffix(".json"),
    ):

        try:

            _safe_unlink(path)

        except OSError:

            logger.warning(
                "Could not delete temporary "
                "pipeline file %s",
                path,
                exc_info=True,
            )

