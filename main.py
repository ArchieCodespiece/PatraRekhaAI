"""Single-entrypoint pipeline that processes a PDF end-to-end."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


# ============================================================================
# PROJECT PATHS
# ============================================================================

ROOT = Path(__file__).resolve().parent

DOCUMENT_PREPROCESSING_DIR = ROOT / "document preprocessing"
AI_PIPELINE_DIR = ROOT / "AI pipeline"

for directory in (
    DOCUMENT_PREPROCESSING_DIR,
    AI_PIPELINE_DIR,
    ROOT,
):
    directory_str = str(directory)

    if directory_str not in sys.path:
        sys.path.insert(0, directory_str)


# ============================================================================
# CONSOLE ENCODING
# ============================================================================

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )


# ============================================================================
# ENVIRONMENT
# ============================================================================

load_dotenv(AI_PIPELINE_DIR / ".env")
load_dotenv(ROOT / ".env")


# ============================================================================
# LOAD DOCUMENT PREPROCESSING PACKAGE
# ============================================================================

DOC_PREPROCESSING_INIT = (
    DOCUMENT_PREPROCESSING_DIR / "__init__.py"
)

spec = importlib.util.spec_from_file_location(
    "document_preprocessing",
    DOC_PREPROCESSING_INIT,
    submodule_search_locations=[
        str(DOCUMENT_PREPROCESSING_DIR)
    ],
)

if spec is None or spec.loader is None:
    raise RuntimeError(
        "Unable to load document preprocessing package."
    )

doc_prep = importlib.util.module_from_spec(spec)

doc_prep.__package__ = "document_preprocessing"

sys.modules["document_preprocessing"] = doc_prep

spec.loader.exec_module(doc_prep)

preprocess_document = doc_prep.preprocess_document


# ============================================================================
# PIPELINE IMPORTS
# ============================================================================

from Chunking.pipeline import ChunkPipeline
from embedding.pipeline import EmbeddingPipeline
from vectorstore.pipeline import VectorStorePipeline


# ============================================================================
# DEFAULTS
# ============================================================================

DEFAULT_PDF = (
    ROOT
    / "ingestion"
    / "Quality_Auditor_Tender_to_be_uploaded.pdf"
)


# ============================================================================
# PREPROCESSOR COMPATIBILITY HELPER
# ============================================================================

def run_document_preprocessing(
    pdf_path: Path,
    owner_email: str | None = None,
    user_id: str | None = None,
    file_id: str | None = None,
) -> Path:
    """
    Call preprocess_document using only the keyword arguments
    supported by the currently installed preprocessing function.

    This keeps the main pipeline compatible with older preprocessing
    implementations while still passing user_id/file_id when supported.
    """

    kwargs = {}

    try:
        signature = inspect.signature(preprocess_document)
        parameters = signature.parameters
    except (TypeError, ValueError):
        parameters = {}

    if (
        owner_email is not None
        and "owner_email" in parameters
    ):
        kwargs["owner_email"] = owner_email

    if (
        user_id is not None
        and "user_id" in parameters
    ):
        kwargs["user_id"] = user_id

    if (
        file_id is not None
        and "file_id" in parameters
    ):
        kwargs["file_id"] = file_id

    result = preprocess_document(
        str(pdf_path),
        **kwargs,
    )

    return Path(result).resolve()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(
    pdf_path: str | Path,
    cleanup_input: bool = False,
    owner_email: str | None = None,
    user_id: str | None = None,
    file_id: str | None = None,
) -> None:
    """
    Run the complete PatraRekha document pipeline.

    Stages:

        1. Document preprocessing / OCR
        2. Semantic chunking
        3. Embedding
        4. Pinecone vector storage

    user_id:
        Supabase Auth user UUID.

    owner_email:
        User email retained for backwards compatibility.

    file_id:
        Supabase file UUID.

    IMPORTANT:
        Pinecone namespace is based on user_id.
        This must match the namespace used by the FastAPI API.
    """

    pdf_path = Path(pdf_path).resolve()

    json_path: Path | None = None

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a .pdf file, got: {pdf_path.suffix}"
        )

    try:

        # ====================================================================
        # PIPELINE HEADER
        # ====================================================================

        print("=" * 65)
        print("  PatraRekha - Document Ingestion Pipeline")
        print("=" * 65)

        print(f"\n  Input : {pdf_path}")

        if user_id:
            print(f"  User  : {user_id}")

        if owner_email:
            print(f"  Owner : {owner_email}")

        if file_id:
            print(f"  File  : {file_id}")

        print()


        # ====================================================================
        # VALIDATE USER ID
        # ====================================================================

        if not user_id:
            print(
                "  [WARN] No user_id supplied."
            )

            print(
                "  [WARN] Falling back to owner_email "
                "for Pinecone namespace."
            )

        # New multi-user architecture uses user_id.
        # Keep email as a fallback for older manual executions.
        pinecone_namespace = (
            user_id
            or owner_email
        )

        if not pinecone_namespace:
            raise ValueError(
                "A user_id or owner_email is required "
                "for Pinecone namespace isolation."
            )


        # ====================================================================
        # STAGE 1 - DOCUMENT PREPROCESSING / OCR
        # ====================================================================

        print("-" * 65)
        print("  Stage 1 / 4 : Document Preprocessing (OCR)")
        print("-" * 65)

        t0 = time.perf_counter()

        json_path = run_document_preprocessing(
            pdf_path=pdf_path,
            owner_email=owner_email,
            user_id=user_id,
            file_id=file_id,
        )

        t1 = time.perf_counter()

        print(
            f"  [OK] JSON output : {json_path}"
        )

        print(
            f"  [OK] Completed in {t1 - t0:.1f}s\n"
        )


        # ====================================================================
        # STAGE 2 - SEMANTIC CHUNKING
        # ====================================================================

        print("-" * 65)
        print("  Stage 2 / 4 : Semantic Chunking")
        print("-" * 65)

        t0 = time.perf_counter()

        chunk_pipeline = ChunkPipeline()

        chunks = chunk_pipeline.process(
            json_path
        )

        t1 = time.perf_counter()

        print(
            f"  [OK] Chunks created : {len(chunks)}"
        )

        print(
            f"  [OK] Completed in {t1 - t0:.1f}s\n"
        )


        # ====================================================================
        # STAGE 3 - EMBEDDING
        # ====================================================================

        print("-" * 65)
        print("  Stage 3 / 4 : Embedding (Gemini)")
        print("-" * 65)

        t0 = time.perf_counter()

        embedding_pipeline = EmbeddingPipeline()

        embedding_result = embedding_pipeline.process(
            chunks
        )

        t1 = time.perf_counter()

        print(
            "  [OK] Embeddings generated : "
            f"{len(embedding_result.embedded_chunks)}"
        )

        print(
            f"  [OK] Completed in {t1 - t0:.1f}s\n"
        )


        # ====================================================================
        # STAGE 4 - VECTOR STORE
        # ====================================================================

        print("-" * 65)
        print("  Stage 4 / 4 : Vector Store (Pinecone)")
        print("-" * 65)

        t0 = time.perf_counter()

        vectorstore_pipeline = VectorStorePipeline(
            namespace=pinecone_namespace
        )

        vectorstore_pipeline.upload(
            embedding_result,
            namespace=pinecone_namespace,
        )

        t1 = time.perf_counter()

        print(
            "  [OK] Upserted to Pinecone"
        )

        print(
            f"  [OK] Namespace : {pinecone_namespace}"
        )

        print(
            f"  [OK] Completed in {t1 - t0:.1f}s\n"
        )


        # ====================================================================
        # FINAL STATISTICS
        # ====================================================================

        stats = vectorstore_pipeline.describe()

        print("=" * 65)
        print("  Pipeline Complete")
        print("=" * 65)

        print(
            f"  Document : {pdf_path.name}"
        )

        print(
            f"  Chunks   : {len(chunks)}"
        )

        print(
            "  Embedded : "
            f"{len(embedding_result.embedded_chunks)}"
        )

        print(
            f"  Namespace: {pinecone_namespace}"
        )

        print(
            f"  Index    : {stats}"
        )

        print("=" * 65)


        # ====================================================================
        # MARK DOCUMENT AS PROCESSED
        # ====================================================================

        if file_id:

            try:

                from db.files import mark_file_summarized

                mark_file_summarized(
                    str(file_id)
                )

                print(
                    f"  [OK] Marked file {file_id} "
                    "as summarized"
                )

            except Exception as exc:

                print(
                    "  [WARN] Could not mark file "
                    f"as summarized: {exc}"
                )

        print()


    finally:

        if cleanup_input:

            cleanup_pipeline_input(
                pdf_path,
                json_path,
            )


# ============================================================================
# CLEANUP
# ============================================================================

def cleanup_pipeline_input(
    pdf_path: Path,
    json_path: Path | None = None,
) -> None:
    """Delete temporary pipeline input/output files."""

    paths = [pdf_path]

    if json_path:
        paths.append(json_path)

    for path in paths:

        try:

            path.unlink(
                missing_ok=True
            )

        except OSError as exc:

            print(
                "Warning: could not delete "
                f"temporary file {path}: {exc}"
            )


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Run the PatraRekha document "
            "ingestion pipeline."
        )
    )


    # ------------------------------------------------------------------------
    # PDF PATH
    # ------------------------------------------------------------------------

    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(DEFAULT_PDF),
        help=(
            "Path to the PDF to process. "
            "Uses the sample PDF when omitted."
        ),
    )


    # ------------------------------------------------------------------------
    # CLEANUP
    # ------------------------------------------------------------------------

    parser.add_argument(
        "--cleanup-input",
        action="store_true",
        help=(
            "Delete the input PDF and generated "
            "sidecar JSON after the pipeline ends."
        ),
    )


    # ------------------------------------------------------------------------
    # USER ID
    # ------------------------------------------------------------------------

    parser.add_argument(
        "--user-id",
        default="",
        help=(
            "Supabase Auth user UUID used for "
            "user-specific document processing."
        ),
    )


    # ------------------------------------------------------------------------
    # OWNER EMAIL
    # ------------------------------------------------------------------------

    parser.add_argument(
        "--owner-email",
        default="",
        help=(
            "Owner email used for application-level "
            "ownership."
        ),
    )


    # ------------------------------------------------------------------------
    # FILE ID
    # ------------------------------------------------------------------------

    parser.add_argument(
        "--file-id",
        default="",
        help=(
            "Supabase file_id used for document "
            "tracking and processing."
        ),
    )


    # ------------------------------------------------------------------------
    # PARSE ARGUMENTS
    # ------------------------------------------------------------------------

    args = parser.parse_args()


    # ------------------------------------------------------------------------
    # RUN PIPELINE
    # ------------------------------------------------------------------------

    run_pipeline(
        args.pdf_path,
        cleanup_input=args.cleanup_input,
        owner_email=args.owner_email or None,
        user_id=args.user_id or None,
        file_id=args.file_id or None,
    )