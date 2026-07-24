"""
main.py

Single-entrypoint pipeline that processes a PDF end-to-end:

    PDF file
        ↓  Document Preprocessing  (OCR → structured JSON)
    JSON file
        ↓  Chunking Pipeline       (semantic sections → chunks)
    List[Chunk]
        ↓  Embedding Pipeline      (Gemini embeddings)
    EmbeddingResult
        ↓  VectorStore Pipeline    (upsert into Pinecone)
    ✓  Stored in Vector DB

Usage
-----
    python main.py <path-to-pdf>
    python main.py <path-to-pdf> --cleanup-input
    python main.py                     # uses the default sample PDF
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# ── Make both parent directories importable ──────────────────────────
# "document preprocessing" and sub-packages inside "AI pipeline"
# live in directories whose names contain spaces.  We add them to
# sys.path so their internal relative imports resolve correctly.

ROOT = Path(__file__).resolve().parent

DOCUMENT_PREPROCESSING_DIR = ROOT / "document preprocessing"
AI_PIPELINE_DIR = ROOT / "AI pipeline"

for directory in (DOCUMENT_PREPROCESSING_DIR, AI_PIPELINE_DIR):
    path_str = str(directory)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Also need the root itself for any cross-package references
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Load environment variables from AI pipeline/.env ─────────────────
from dotenv import load_dotenv

load_dotenv(AI_PIPELINE_DIR / ".env")

# ── Pipeline imports ─────────────────────────────────────────────────
# Stage 1: Document Preprocessing
import importlib
doc_prep = importlib.import_module("document preprocessing")
preprocess_document = doc_prep.preprocess_document

# Stage 2: Chunking
from Chunking.pipeline import ChunkPipeline  # noqa: E402

# Stage 3: Embedding
from embedding.pipeline import EmbeddingPipeline  # noqa: E402

# Stage 4: VectorStore
from vectorstore.pipeline import VectorStorePipeline  # noqa: E402


# ── Default sample PDF ──────────────────────────────────────────────
DEFAULT_PDF = (
    Path("/home/user/Projects/PatraRekha/PatraRekhaAI/high-school-research-paper-example.pdf")
)


def run_pipeline(pdf_path: str | Path, cleanup_input: bool = False) -> None:
    """
    Execute the full ingestion pipeline for a single PDF.

    Parameters
    ----------
    pdf_path : str | Path
        Absolute or relative path to the input PDF file.
    cleanup_input : bool
        Delete the input PDF and generated sidecar JSON after the pipeline ends.
        Use this for temporary webhook downloads, not for normal CLI files.
    """

    pdf_path = Path(pdf_path).resolve()
    json_path = None

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path.suffix}")

    try:
        print("=" * 65)
        print("  PatraRekha — Document Ingestion Pipeline")
        print("=" * 65)
        print(f"\n  Input : {pdf_path}\n")

        # ── Stage 1: Document Preprocessing (OCR → JSON) ────────────────
        print("─" * 65)
        print("  Stage 1 / 4 : Document Preprocessing (OCR)")
        print("─" * 65)

        t0 = time.perf_counter()

        json_path = Path(preprocess_document(str(pdf_path))).resolve()

        t1 = time.perf_counter()
        print(f"  ✓ JSON output : {json_path}")
        print(f"  ✓ Completed in {t1 - t0:.1f}s\n")

        # ── Stage 2: Chunking ────────────────────────────────────────────
        print("─" * 65)
        print("  Stage 2 / 4 : Semantic Chunking")
        print("─" * 65)

        t0 = time.perf_counter()

        chunk_pipeline = ChunkPipeline()
        chunks = chunk_pipeline.process(json_path)

        t1 = time.perf_counter()
        print(f"  ✓ Chunks created : {len(chunks)}")
        print(f"  ✓ Completed in {t1 - t0:.1f}s\n")

        # ── Stage 3: Embedding ───────────────────────────────────────────
        print("─" * 65)
        print("  Stage 3 / 4 : Embedding (Gemini)")
        print("─" * 65)

        t0 = time.perf_counter()

        embedding_pipeline = EmbeddingPipeline()
        embedding_result = embedding_pipeline.process(chunks)

        t1 = time.perf_counter()
        print(
            f"  ✓ Embeddings generated : "
            f"{len(embedding_result.embedded_chunks)}"
        )
        print(f"  ✓ Completed in {t1 - t0:.1f}s\n")

        # ── Stage 4: Vector Store (Pinecone) ─────────────────────────────
        print("─" * 65)
        print("  Stage 4 / 4 : Vector Store (Pinecone)")
        print("─" * 65)

        t0 = time.perf_counter()

        vectorstore_pipeline = VectorStorePipeline()
        vectorstore_pipeline.upload(embedding_result)

        t1 = time.perf_counter()
        print(f"  ✓ Upserted to Pinecone")
        print(f"  ✓ Completed in {t1 - t0:.1f}s\n")

        # ── Summary ──────────────────────────────────────────────────────
        stats = vectorstore_pipeline.describe()

        print("=" * 65)
        print("  Pipeline Complete")
        print("=" * 65)
        print(f"  Document : {pdf_path.name}")
        print(f"  Chunks   : {len(chunks)}")
        print(
            f"  Embedded : "
            f"{len(embedding_result.embedded_chunks)}"
        )
        print(f"  Index    : {stats}")
        print("=" * 65)
    finally:
        if cleanup_input:
            cleanup_pipeline_input(pdf_path, json_path)


def cleanup_pipeline_input(pdf_path: Path, json_path: Path | None = None) -> None:
    """Delete temporary pipeline input files created by webhook processing."""
    paths = [pdf_path]
    if json_path:
        paths.append(json_path)

    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"Warning: could not delete temporary file {path}: {exc}")


# ── CLI entrypoint ───────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the PatraRekha document ingestion pipeline.")
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(DEFAULT_PDF),
        help="Path to the PDF to process. Uses the sample PDF when omitted.",
    )
    parser.add_argument(
        "--cleanup-input",
        action="store_true",
        help="Delete the input PDF and generated sidecar JSON after the pipeline ends.",
    )
    args = parser.parse_args()

    run_pipeline(args.pdf_path, cleanup_input=args.cleanup_input)
