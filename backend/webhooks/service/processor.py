
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
    Process a document received through the Supabase webhook.

    Expected webhook document payload:

        {
            "file_id": "...",
            "user_id": "...",
            "owner_email": "...",
            ...
        }

    The authoritative file record is loaded from the database before
    downloading the file.
    """

    file_id = document.get("file_id")

    if not file_id:
        raise ValueError(
            "Webhook document is missing 'file_id'."
        )

    # ------------------------------------------------------------------
    # Get authoritative database record
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Make sure the record has a user_id
    # ------------------------------------------------------------------

    user_id = document_record.get("user_id")

    if not user_id:
        raise ValueError(
            f"Document {file_id} does not have a user_id."
        )

    # ------------------------------------------------------------------
    # Download the document from:
    #
    # public/documents/<user_id>/<filename>
    # ------------------------------------------------------------------

    content = await asyncio.to_thread(
        download_document_content,
        document_record["filename"],
        user_id,
    )

    # ------------------------------------------------------------------
    # Run AI/document-processing pipeline
    # ------------------------------------------------------------------

    await run_document_pipeline(
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


# ---------------------------------------------------------------------------
# Temporary PDF handling
# ---------------------------------------------------------------------------

def write_temp_pdf(
    document,
    content,
):
    """
    Write downloaded document content to a temporary PDF.

    The pipeline operates on a local PDF path.
    """

    if not content:
        raise ValueError(
            "Downloaded document is empty: "
            f"{document['file_id']}"
        )

    filename = safe_filename(
        document.get("filename")
        or f"{document['file_id']}.pdf"
    )

    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    TEMP_PDF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdf_path = (
        TEMP_PDF_DIR
        / f"{document['file_id']}-{filename}"
    )

    pdf_path.write_bytes(content)

    logger.info(
        "Temporary PDF created at %s",
        pdf_path,
    )

    return pdf_path


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

            path.unlink(
                missing_ok=True
            )

        except OSError:

            logger.warning(
                "Could not delete temporary "
                "pipeline file %s",
                path,
                exc_info=True,
            )

