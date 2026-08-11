
"""PDF preprocessing and OCR pipeline."""

from __future__ import annotations

import gc
import json
import os

import numpy as np
import pdfplumber
from pdf2image import convert_from_path

try:
    from .config import (
        POPPLER_PATH,
        DPI,
        BATCH_SIZE,
        get_checkpoint_path,
    )
    from .preprocess import preprocess_image
    from .ocr_engine import run_paddle_ocr
    from .table_extraction import extract_tables_from_page
    from .text_cleaner import clean_text
    from .utils import contiguous_ranges, write_output

except ImportError:
    from config import (
        POPPLER_PATH,
        DPI,
        BATCH_SIZE,
        get_checkpoint_path,
    )
    from preprocess import preprocess_image
    from ocr_engine import run_paddle_ocr
    from table_extraction import extract_tables_from_page
    from text_cleaner import clean_text
    from utils import contiguous_ranges, write_output


# ============================================================================
# Checkpoint helpers
# ============================================================================

def load_checkpoint(checkpoint_path: str) -> dict:
    """Load previously processed pages from a checkpoint file."""

    try:
        with open(
            checkpoint_path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except FileNotFoundError:
        return {}

    except json.JSONDecodeError:
        return {}


def save_checkpoint(
    results: dict,
    checkpoint_path: str,
) -> None:
    """Save processed pages to a checkpoint file."""

    parent = os.path.dirname(checkpoint_path)

    if parent:
        os.makedirs(
            parent,
            exist_ok=True,
        )

    with open(
        checkpoint_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            indent=4,
            ensure_ascii=False,
        )


def clear_checkpoint(
    checkpoint_path: str,
) -> None:
    """Delete a completed checkpoint file."""

    try:
        os.remove(checkpoint_path)

    except FileNotFoundError:
        pass


# ============================================================================
# PDF processing pipeline
# ============================================================================

def process_pdf(
    pdf_path,
    output_json="paddle_output.json",
    batch_size=BATCH_SIZE,
    dpi=DPI,
    checkpoint_path=None,
    resume=True,
    owner_email=None,
    user_id=None,
    file_id=None,
):
    """
    Complete PDF processing pipeline.

    Parameters
    ----------
    pdf_path : str
        Path to the input PDF.

    output_json : str
        Path where the final JSON output will be written.

    batch_size : int
        Number of pages processed in one OCR batch.

    dpi : int
        DPI used when rendering PDF pages for OCR.

    checkpoint_path : str | None
        Explicit checkpoint path. If None, a unique checkpoint
        path is generated using file_id and owner_email.

    resume : bool
        Whether to resume from a previous checkpoint.

    owner_email : str | None
        Owner email used for per-user checkpoint isolation.

    user_id : str | None
        Supabase Auth user UUID.

        The user_id is carried through the processing pipeline so
        downstream stages can identify the document owner if needed.

    file_id : str | None
        Supabase file_id used to create a unique checkpoint path.
    """

    # =========================================================================
    # Validate input
    # =========================================================================

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if not str(pdf_path).lower().endswith(".pdf"):
        raise ValueError(
            f"Expected a PDF file: {pdf_path}"
        )

    # =========================================================================
    # Checkpoint configuration
    # =========================================================================

    if checkpoint_path is None:
        checkpoint_path = get_checkpoint_path(
            file_id=file_id,
            owner_email=owner_email,
        )

    # =========================================================================
    # Resume previous execution
    # =========================================================================

    done = (
        load_checkpoint(checkpoint_path)
        if resume
        else {}
    )

    if done:
        print(
            f"Resuming from checkpoint "
            f"({len(done)} pages already processed)."
        )

    results = dict(done)

    # =========================================================================
    # Phase 1 - Direct PDF text extraction
    # =========================================================================

    print()
    print("Phase 1 : Extracting text from PDF...")

    needs_ocr = []

    with pdfplumber.open(pdf_path) as pdf:

        total_pages = len(pdf.pages)

        print(
            f"Total Pages : {total_pages}"
        )

        for index, page in enumerate(pdf.pages):

            page_number = index + 1

            # Already processed in checkpoint.
            if page_number in results:
                continue

            text = page.extract_text()

            # -------------------------------------------------------------
            # Direct text extraction succeeded
            # -------------------------------------------------------------

            if text and len(text.strip()) > 50:

                print(
                    f"Page {page_number} : Direct Text"
                )

                tables = extract_tables_from_page(
                    page
                )

                text = clean_text(text)

                entry = {
                    "page_number": page_number,
                    "text": text,
                }

                if tables:
                    entry["tables"] = tables

                results[page_number] = entry

            # -------------------------------------------------------------
            # OCR required
            # -------------------------------------------------------------

            else:

                print(
                    f"Page {page_number} : OCR Required"
                )

                needs_ocr.append(
                    page_number
                )

    # Save direct extraction results before OCR.
    save_checkpoint(
        results,
        checkpoint_path,
    )

    print(
        f"\n{len(needs_ocr)} pages require OCR."
    )

    # =========================================================================
    # No OCR required
    # =========================================================================

    if not needs_ocr:

        write_output(
            results,
            output_json,
            total_pages,
        )

        clear_checkpoint(
            checkpoint_path
        )

        return

    # =========================================================================
    # Phase 2 - OCR
    # =========================================================================

    print()
    print("Running PaddleOCR...")

    # If PaddleOCR fails because of a Windows DLL/AppControl issue,
    # don't repeatedly initialize it for every remaining page.
    ocr_unavailable = False

    # =========================================================================
    # OCR batches
    # =========================================================================

    for batch_start in range(
        0,
        len(needs_ocr),
        batch_size,
    ):

        batch_pages = needs_ocr[
            batch_start:
            batch_start + batch_size
        ]

        if not batch_pages:
            continue

        print()
        print(
            f"Batch : "
            f"{batch_pages[0]} - "
            f"{batch_pages[-1]}"
        )

        page_images = {}

        # ---------------------------------------------------------------------
        # Render PDF pages
        # ---------------------------------------------------------------------

        ranges = contiguous_ranges(
            batch_pages
        )

        for first_page, last_page in ranges:

            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=first_page,
                last_page=last_page,
                poppler_path=POPPLER_PATH,
            )

            for offset, image in enumerate(images):

                page_number = (
                    first_page + offset
                )

                page_images[page_number] = image

        # ---------------------------------------------------------------------
        # Process each page
        # ---------------------------------------------------------------------

        for page_number in batch_pages:

            print(
                f"OCR Page {page_number}"
            )

            image = page_images.get(
                page_number
            )

            if image is None:

                print(
                    f"Warning: image for page "
                    f"{page_number} was not generated."
                )

                results[page_number] = {
                    "page_number": page_number,
                    "text": "",
                }

                continue

            # Convert PIL image to NumPy array.
            img = np.array(image)

            # -------------------------------------------------------------
            # Image preprocessing
            # -------------------------------------------------------------

            processed = preprocess_image(
                img
            )

            # -------------------------------------------------------------
            # OCR
            # -------------------------------------------------------------

            if ocr_unavailable:

                print(
                    f"Skipping page {page_number}: "
                    "PaddleOCR unavailable."
                )

                text = ""
                tables = []

            else:

                try:

                    text, tables = run_paddle_ocr(
                        processed
                    )

                except (
                    RuntimeError,
                    ImportError,
                ) as ocr_error:

                    print(
                        f"PaddleOCR unavailable on "
                        f"page {page_number}: "
                        f"{ocr_error}"
                    )

                    print(
                        "This is usually caused by a "
                        "Windows AppControl policy "
                        "blocking the required DLL."
                    )

                    print(
                        "Pages requiring OCR will be "
                        "stored with empty text."
                    )

                    ocr_unavailable = True

                    text = ""
                    tables = []

            # -------------------------------------------------------------
            # Clean OCR text
            # -------------------------------------------------------------

            text = clean_text(
                text
            )

            entry = {
                "page_number": page_number,
                "text": text,
            }

            if tables:
                entry["tables"] = tables

            results[page_number] = entry

            # Free page memory immediately.
            del processed
            del img
            del page_images[page_number]

        # ---------------------------------------------------------------------
        # Free batch memory
        # ---------------------------------------------------------------------

        page_images.clear()

        gc.collect()

        # ---------------------------------------------------------------------
        # Save checkpoint
        # ---------------------------------------------------------------------

        save_checkpoint(
            results,
            checkpoint_path,
        )

        print(
            "Checkpoint Saved."
        )

    # =========================================================================
    # Final output
    # =========================================================================

    write_output(
        results,
        output_json,
        total_pages,
    )

    clear_checkpoint(
        checkpoint_path
    )
