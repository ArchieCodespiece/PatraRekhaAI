from pathlib import Path

from .config import BATCH_SIZE, DPI
from .pdf_processor import process_pdf


def preprocess_document(pdf_path: str) -> str:
    pdf_path = Path(pdf_path)

    output_json = pdf_path.with_suffix(".json")
    checkpoint_path = pdf_path.with_suffix(".checkpoint.json")

    process_pdf(
        str(pdf_path),
        output_json=str(output_json),
        checkpoint_path=str(checkpoint_path),
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=True,
    )

    return str(output_json)
