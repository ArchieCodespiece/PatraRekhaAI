from pathlib import Path
import tempfile
import time

from .config import BATCH_SIZE, DPI
from .converter import convert_to_pdf, is_supported_document
from .pdf_processor import process_pdf


def preprocess_document(
    document_path: str,
    owner_email: str | None = None,
    file_id: str | None = None,
) -> str:
    """
    Run the OCR/preprocessing pipeline on a single document.

    Supported formats: PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS, TXT, CSV.
    Non-PDF documents are converted to PDF before processing.

    Parameters
    ----------
    document_path : str
        Path to the input document.
    owner_email : str | None
        Owner email used to namespace the checkpoint file (per-user isolation).
    file_id : str | None
        Supabase file_id — used to build a unique checkpoint path so that
        concurrent pipeline runs don't collide on the same checkpoint file.

    Returns
    -------
    str
        Path to the generated output JSON.
    """
    document_path = Path(document_path)

    if not is_supported_document(document_path):
        raise ValueError(
            f"Unsupported file type: {document_path.suffix}. "
            f"Supported: .pdf, .docx, .doc, .pptx, .ppt, "
            f".xlsx, .xls, .txt, .csv"
        )

    temp_pdf = None
    processing_path = document_path

    if document_path.suffix.lower() != ".pdf":
        temp_dir = (
            Path(tempfile.gettempdir())
            / "patrarekha-preprocessing"
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_pdf = temp_dir / f"{document_path.stem}.pdf"
        convert_to_pdf(document_path, temp_pdf)
        processing_path = temp_pdf

    output_json = processing_path.with_suffix(".json")

    # Derive a unique checkpoint path from file_id + owner_email.
    # This avoids the WinError 32 file-lock issue when multiple pipelines
    # run concurrently against the shared "paddle2_checkpoint.json".
    from .config import get_checkpoint_path

    checkpoint_path = get_checkpoint_path(
        file_id=file_id,
        owner_email=owner_email,
    )

    try:
        process_pdf(
            str(processing_path),
            output_json=str(output_json),
            checkpoint_path=checkpoint_path,
            batch_size=BATCH_SIZE,
            dpi=DPI,
            resume=True,
            owner_email=owner_email,
            file_id=file_id,
        )
    finally:
        if temp_pdf and temp_pdf.exists():
            for attempt in range(3):
                try:
                    temp_pdf.unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.5)

    return str(output_json)
