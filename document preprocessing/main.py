from pathlib import Path

from pdf_processor import process_pdf
from config import BATCH_SIZE, DPI

if __name__ == "__main__":

    pdf_path = Path(r"E:\PatraRekha\ingestion\Quality_Auditor_Tender_to_be_uploaded.pdf")

    output_json = pdf_path.with_suffix(".json")

    process_pdf(
        str(pdf_path),
        output_json=str(output_json),
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=False
    )