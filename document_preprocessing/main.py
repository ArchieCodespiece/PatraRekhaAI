from pathlib import Path

try:
    from .pdf_processor import process_pdf
    from .document_metadata import generate_document_metadata
    from .config import BATCH_SIZE, DPI
except ImportError:
    from pdf_processor import process_pdf
    from document_metadata import generate_document_metadata
    from config import BATCH_SIZE, DPI


if __name__ == "__main__":

    pdf_path = Path(
        r"E:\PatraRekha\ingestion\Quality_Auditor_Tender_to_be_uploaded.pdf"
    )

    output_json = pdf_path.with_suffix(".json")

    # OCR + JSON generation
    process_pdf(
        str(pdf_path),
        output_json=str(output_json),
        batch_size=BATCH_SIZE,
        dpi=DPI,
        resume=True,
    )

    # Document metadata generation
    metadata = generate_document_metadata(
        document_path=str(pdf_path),
        json_path=str(output_json),
    )

    print("Document metadata generated successfully.")
    print(metadata)