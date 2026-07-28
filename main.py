"""Single-entrypoint pipeline that processes a PDF end-to-end."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DOCUMENT_PREPROCESSING_DIR = ROOT / "document preprocessing"
AI_PIPELINE_DIR = ROOT / "AI pipeline"

for directory in (DOCUMENT_PREPROCESSING_DIR, AI_PIPELINE_DIR):
    path_str = str(directory)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(AI_PIPELINE_DIR / ".env")

DOC_PREPROCESSING_INIT = DOCUMENT_PREPROCESSING_DIR / "__init__.py"
spec = importlib.util.spec_from_file_location(
    "document_preprocessing",
    DOC_PREPROCESSING_INIT,
    submodule_search_locations=[str(DOCUMENT_PREPROCESSING_DIR)],
)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load document preprocessing package.")

doc_prep = importlib.util.module_from_spec(spec)
doc_prep.__package__ = "document_preprocessing"
sys.modules["document_preprocessing"] = doc_prep
spec.loader.exec_module(doc_prep)
preprocess_document = doc_prep.preprocess_document

from Chunking.pipeline import ChunkPipeline  # noqa: E402
from embedding.pipeline import EmbeddingPipeline  # noqa: E402
from vectorstore.pipeline import VectorStorePipeline  # noqa: E402


DEFAULT_PDF = ROOT / "ingestion" / "Quality_Auditor_Tender_to_be_uploaded.pdf"


def run_pipeline(pdf_path: str | Path, cleanup_input: bool = False) -> None:
    pdf_path = Path(pdf_path).resolve()
    json_path = None

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path.suffix}")

    try:
        print("=" * 65)
        print("  PatraRekha - Document Ingestion Pipeline")
        print("=" * 65)
        print(f"\n  Input : {pdf_path}\n")

        print("-" * 65)
        print("  Stage 1 / 4 : Document Preprocessing (OCR)")
        print("-" * 65)
        t0 = time.perf_counter()
        json_path = Path(preprocess_document(str(pdf_path))).resolve()
        t1 = time.perf_counter()
        print(f"  [OK] JSON output : {json_path}")
        print(f"  [OK] Completed in {t1 - t0:.1f}s\n")

        print("-" * 65)
        print("  Stage 2 / 4 : Semantic Chunking")
        print("-" * 65)
        t0 = time.perf_counter()
        chunk_pipeline = ChunkPipeline()
        chunks = chunk_pipeline.process(json_path)
        t1 = time.perf_counter()
        print(f"  [OK] Chunks created : {len(chunks)}")
        print(f"  [OK] Completed in {t1 - t0:.1f}s\n")

        print("-" * 65)
        print("  Stage 3 / 4 : Embedding (Gemini)")
        print("-" * 65)
        t0 = time.perf_counter()
        embedding_pipeline = EmbeddingPipeline()
        embedding_result = embedding_pipeline.process(chunks)
        t1 = time.perf_counter()
        print(f"  [OK] Embeddings generated : {len(embedding_result.embedded_chunks)}")
        print(f"  [OK] Completed in {t1 - t0:.1f}s\n")

        print("-" * 65)
        print("  Stage 4 / 4 : Vector Store (Pinecone)")
        print("-" * 65)
        t0 = time.perf_counter()
        vectorstore_pipeline = VectorStorePipeline()
        vectorstore_pipeline.upload(embedding_result)
        t1 = time.perf_counter()
        print("  [OK] Upserted to Pinecone")
        print(f"  [OK] Completed in {t1 - t0:.1f}s\n")

        stats = vectorstore_pipeline.describe()
        print("=" * 65)
        print("  Pipeline Complete")
        print("=" * 65)
        print(f"  Document : {pdf_path.name}")
        print(f"  Chunks   : {len(chunks)}")
        print(f"  Embedded : {len(embedding_result.embedded_chunks)}")
        print(f"  Index    : {stats}")
        print("=" * 65)
    finally:
        if cleanup_input:
            cleanup_pipeline_input(pdf_path, json_path)


def cleanup_pipeline_input(pdf_path: Path, json_path: Path | None = None) -> None:
    paths = [pdf_path]
    if json_path:
        paths.append(json_path)

    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"Warning: could not delete temporary file {path}: {exc}")


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
