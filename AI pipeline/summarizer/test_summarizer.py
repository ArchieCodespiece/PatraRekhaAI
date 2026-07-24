"""
test_summarizer.py

End-to-end test for the summarization pipeline.

Pipeline

PDF
    ↓
Document Preprocessing
    ↓
Semantic Chunking
    ↓
Document Summarization
        ├── Executive Summary
        └── Action Item Extraction
"""

from __future__ import annotations

import sys
import time
import importlib
from pathlib import Path

# =============================================================================
# Paths
# =============================================================================

ROOT = Path(__file__).resolve().parents[2]

DOCUMENT_PREPROCESSING_DIR = ROOT / "document preprocessing"
AI_PIPELINE_DIR = ROOT / "AI pipeline"

for directory in (DOCUMENT_PREPROCESSING_DIR, AI_PIPELINE_DIR):
    path_str = str(directory)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =============================================================================
# Environment
# =============================================================================

from dotenv import load_dotenv

load_dotenv(AI_PIPELINE_DIR / ".env")

# =============================================================================
# Stage 1 : Document Preprocessing
# =============================================================================

doc_prep = importlib.import_module("document preprocessing")
preprocess_document = doc_prep.preprocess_document

# =============================================================================
# Stage 2 : Semantic Chunking
# =============================================================================

from Chunking.pipeline import ChunkPipeline

# =============================================================================
# Stage 3 : Summarization
# =============================================================================

from summarizer.document_summarizer import process_document

# =============================================================================

DEFAULT_PDF = (
    r"E:\PatraRekha\ingestion\Grant_Application_Guidelines.pdf"
)


def run_pipeline(pdf_path: str | Path) -> None:
    """
    Execute the summarization pipeline.
    """

    pdf_path = Path(pdf_path).resolve()

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Input must be a PDF.")

    print("=" * 70)
    print("PatraRekha - Document Summary Pipeline")
    print("=" * 70)
    print(f"\nInput : {pdf_path}\n")

    # -----------------------------------------------------------------
    # Stage 1
    # -----------------------------------------------------------------

    print("-" * 70)
    print("Stage 1 / 3 : Document Preprocessing")
    print("-" * 70)

    t0 = time.perf_counter()

    json_path = preprocess_document(str(pdf_path))

    t1 = time.perf_counter()

    print(f"✓ JSON : {json_path}")
    print(f"✓ Completed in {t1 - t0:.2f}s\n")

    # -----------------------------------------------------------------
    # Stage 2
    # -----------------------------------------------------------------

    print("-" * 70)
    print("Stage 2 / 3 : Semantic Chunking")
    print("-" * 70)

    t0 = time.perf_counter()

    chunk_pipeline = ChunkPipeline()
    chunks = chunk_pipeline.process(json_path)

    t1 = time.perf_counter()

    print(f"✓ Chunks Created : {len(chunks)}")
    print(f"✓ Completed in {t1 - t0:.2f}s\n")

    if not chunks:
        raise RuntimeError("Chunking pipeline returned no chunks.")

    # -----------------------------------------------------------------
    # Prepare LLM input
    # -----------------------------------------------------------------

    chunk_texts = [chunk.text for chunk in chunks]

    document_id = chunks[0].metadata.document_id
    document_name = chunks[0].metadata.document_name

    # -----------------------------------------------------------------
    # Stage 3
    # -----------------------------------------------------------------

    print("-" * 70)
    print("Stage 3 / 3 : Document Summarization")
    print("-" * 70)

    t0 = time.perf_counter()

    executive_summary, action_items = process_document(
        document_id=document_id,
        document_name=document_name,
        chunks=chunk_texts,
    )

    t1 = time.perf_counter()

    print(f"✓ Completed in {t1 - t0:.2f}s\n")

    print("=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)
    print(executive_summary)

    print("\n" + "=" * 70)
    print("ACTIONABLE ITEMS")
    print("=" * 70)
    print(action_items)

    # -----------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------

    print("\n" + "=" * 70)
    print("Pipeline Complete")
    print("=" * 70)
    print(f"Document     : {document_name}")
    print(f"Document ID  : {document_id}")
    print(f"Chunks       : {len(chunks)}")
    print("=" * 70)


if __name__ == "__main__":

    if len(sys.argv) > 1:
        pdf = sys.argv[1]
    else:
        pdf = str(DEFAULT_PDF)

    run_pipeline(pdf)