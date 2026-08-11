from pathlib import Path

from .config import BATCH_SIZE, DPI
from .pdf_processor import process_pdf


def preprocess_document(pdf_path: str, owner_email: str | None = None, file_id: str | None = None) -> str:
    """
    Run the OCR/preprocessing pipeline on a single PDF.

    Parameters
    ----------
    pdf_path : str
        Path to the input PDF.
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
    pdf_path = Path(pdf_path)

    output_json = pdf_path.with_suffix(".json")

    # Derive a unique checkpoint path from file_id + owner_email.
    # This avoids the WinError 32 file-lock issue when multiple pipelines
    # run concurrently against the shared "paddle2_checkpoint.json".
    from .config import get_checkpoint_path

    checkpoint_path = get_checkpoint_path(file_id=file_id, owner_email=owner_email)

    process_pdf(
        str(pdf_path),
        output_json=str(output_json),
        checkpoint_path=checkpoint_path,
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=True,
        owner_email=owner_email,
        file_id=file_id,
    )

    return str(output_json)
