from pathlib import Path

from .config import BATCH_SIZE, DPI
from .pdf_processor import process_pdf


def preprocess_document(pdf_path: str) -> str:
    pdf_path = Path(pdf_path)

    output_json = pdf_path.with_suffix(".json")

    process_pdf(
        str(pdf_path),
        output_json=str(output_json),
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=True,
    )

    return str(output_json)