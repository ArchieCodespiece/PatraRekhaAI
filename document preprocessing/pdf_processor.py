import gc
import json
import re
import pdfplumber
import numpy as np
from pdf2image import convert_from_path

try:
    from .config import POPPLER_PATH, DPI, BATCH_SIZE, CHECKPOINT
    from .preprocess import preprocess_image
    from .ocr_engine import run_paddle_ocr
    from .table_extraction import extract_tables_from_page
    from .text_cleaner import clean_text
    from .checkpoint import clear_checkpoint, load_checkpoint, save_checkpoint
    from .utils import contiguous_ranges, write_output
except ImportError:
    from config import POPPLER_PATH, DPI, BATCH_SIZE, CHECKPOINT
    from preprocess import preprocess_image
    from ocr_engine import run_paddle_ocr
    from table_extraction import extract_tables_from_page
    from text_cleaner import clean_text
    from checkpoint import clear_checkpoint, load_checkpoint, save_checkpoint
    from utils import contiguous_ranges, write_output


def process_pdf(
    pdf_path,
    output_json="paddle_output.json",
    batch_size=BATCH_SIZE,
    dpi=DPI,
    checkpoint_path=CHECKPOINT,
    resume=True,
):
    """
    Complete PDF processing pipeline.
    """

    # -------------------------
    # Resume previous execution
    # -------------------------
    done = load_checkpoint(checkpoint_path) if resume else {}

    if done:
        print(f"📂 Resuming from checkpoint ({len(done)} pages already processed).")

    results = dict(done)

    # -------------------------
    # Phase 1 : Direct Extraction
    # -------------------------
    print("\n🔍 Phase 1 : Extracting text from PDF...")

    needs_ocr = []

    with pdfplumber.open(pdf_path) as pdf:

        total_pages = len(pdf.pages)

        print(f"Total Pages : {total_pages}")

        for i, page in enumerate(pdf.pages):

            page_number = i + 1

            if page_number in results:
                continue

            text = page.extract_text()

            if text and len(text.strip()) > 50:

                print(f"✓ Page {page_number} : Direct Text")

                tables = extract_tables_from_page(page)

                text = clean_text(text)

                entry = {
                    "page_number": page_number,
                    "text": text
                }

                if tables:
                    entry["tables"] = tables

                results[page_number] = entry

            else:

                print(f"⚠ Page {page_number} : OCR Required")

                needs_ocr.append(page_number)

    save_checkpoint(results, checkpoint_path)

    print(f"\n{len(needs_ocr)} pages require OCR.")

    if not needs_ocr:
        write_output(results, output_json, total_pages)
        clear_checkpoint(checkpoint_path)
        return

    # -------------------------
    # Phase 2 : OCR
    # -------------------------

    print("\nRunning PaddleOCR...")

    for batch_start in range(0, len(needs_ocr), batch_size):

        batch_pages = needs_ocr[
            batch_start:
            batch_start + batch_size
        ]

        print(f"\nBatch : {batch_pages[0]} - {batch_pages[-1]}")

        page_images = {}

        ranges = contiguous_ranges(batch_pages)

        for first_page, last_page in ranges:

            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=first_page,
                last_page=last_page,
                poppler_path=POPPLER_PATH
            )

            for offset, img in enumerate(images):
                page_images[first_page + offset] = img

        for page_number in batch_pages:

            print(f"OCR Page {page_number}")

            img = np.array(page_images[page_number])

            processed = preprocess_image(img)

            text, tables = run_paddle_ocr(processed)

            text = clean_text(text)

            entry = {
                "page_number": page_number,
                "text": text
            }

            if tables:
                entry["tables"] = tables

            results[page_number] = entry

            del processed
            del img
            del page_images[page_number]

        page_images.clear()

        gc.collect()

        save_checkpoint(results, checkpoint_path)

        print("Checkpoint Saved.")

    # -------------------------
    # Final Output
    # -------------------------

    write_output(results, output_json, total_pages)
    clear_checkpoint(checkpoint_path)
