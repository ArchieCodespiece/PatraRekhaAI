"""Single-entrypoint pipeline that processes a document end-to-end."""

from __future__ import annotations

import argparse
import inspect
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv


# ============================================================================
# PROJECT PATHS
# ============================================================================

ROOT = Path(__file__).resolve().parent

DOCUMENT_PREPROCESSING_DIR = ROOT / "document_preprocessing"
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

from document_preprocessing import preprocess_document


# ============================================================================
# PIPELINE IMPORTS
# ============================================================================

from Chunking.pipeline import ChunkPipeline
from embedding.pipeline import EmbeddingPipeline
from retrieval.pipeline import RetrievalPipeline
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
    input_path: str | Path,
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

    from document_preprocessing.converter import (
        convert_to_pdf,
        is_supported_document,
    )

    input_path = Path(input_path).resolve()

    if not is_supported_document(input_path):
        raise ValueError(
            f"Unsupported file type: {input_path.suffix}. "
            f"Supported: .pdf, .docx, .doc, .pptx, .ppt, "
            f".xlsx, .xls, .txt, .csv"
        )

    temp_pdf = None
    processing_path = input_path

    if input_path.suffix.lower() != ".pdf":
        temp_dir = (
            Path(tempfile.gettempdir())
            / "patrarekha-pipeline"
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_pdf = temp_dir / f"{input_path.stem}.pdf"
        convert_to_pdf(input_path, temp_pdf)
        processing_path = temp_pdf

    json_path: Path | None = None

    if not processing_path.exists():
        raise FileNotFoundError(
            f"Document not found: {processing_path}"
        )

    try:

        # ====================================================================
        # PIPELINE HEADER
        # ====================================================================

        print("=" * 65)
        print("  PatraRekha - Document Ingestion Pipeline")
        print("=" * 65)

        print(f"\n  Input : {processing_path}")

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
            pdf_path=processing_path,
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
            f"  Document : {processing_path.name}"
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

        if temp_pdf and temp_pdf.exists():

            for attempt in range(3):

                try:

                    temp_pdf.unlink(
                        missing_ok=True
                    )

                    break

                except PermissionError:

                    if attempt < 2:
                        time.sleep(0.5)

        if cleanup_input:

            cleanup_pipeline_input(
                input_path,
                json_path,
            )


def run_retrieval(
    query: str,
    document_ids: list[str],
    top_k: int = 5,
    score_threshold: float | None = None,
) -> None:
    """
    Run the retrieval pipeline against the vector store.

    Parameters
    ----------
    query : str
        User search question.
    document_ids : list[str]
        IDs of documents to restrict the search to.
    top_k : int
        Number of chunks to retrieve.
    score_threshold : float | None
        Minimum similarity score to include a chunk.
    """

    pipeline = RetrievalPipeline()

    result = pipeline.retrieve(
        query=query,
        document_ids=document_ids,
    )

    print("=" * 65)
    print("  PatraRekha - Retrieval")
    print("=" * 65)
    print(f"\n  Query   : {query}")
    print(f"  Documents: {', '.join(result.documents_queried)}")
    print(f"  Top K   : {top_k}")
    print()

    chunks = result.chunks

    if score_threshold is not None:
        chunks = [
            chunk
            for chunk in chunks
            if chunk.score >= score_threshold
        ]

    if not chunks:
        print("  No chunks matched the query.")
        return

    for rank, chunk in enumerate(chunks, start=1):
        print("-" * 65)
        print(
            f"  [{rank}] {chunk.document_name} "
            f"(pages {chunk.page_start}-{chunk.page_end})"
        )
        print(f"       Score : {chunk.score:.4f}")
        print(f"       Chunk : {chunk.chunk_id}")
        print()
        print(f"  {chunk.text[:500]}")
        print("...")

    print()
    print("=" * 65)
    print(f"  Retrieved {len(chunks)} chunks")
    print("=" * 65)


# ============================================================================
# CLEANUP
# ============================================================================

def cleanup_pipeline_input(
    input_path: Path,
    json_path: Path | None = None,
) -> None:
    """Delete temporary pipeline input/output files."""

    import time

    paths = [input_path]

    if json_path:
        paths.append(json_path)

    for path in paths:

        for attempt in range(3):

            try:

                path.unlink(
                    missing_ok=True
                )

                break

            except PermissionError:

                if attempt < 2:
                    time.sleep(0.5)
                else:
                    pass


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
            "Path to the document to process. "
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
            "Delete the input document and generated "
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
    # RETRIEVAL MODE
    # ------------------------------------------------------------------------

    parser.add_argument(
        "--query",
        default="",
        help=(
            "Run retrieval mode with this query "
            "instead of the ingestion pipeline."
        ),
    )

    parser.add_argument(
        "--document-ids",
        nargs="+",
        default=[],
        help=(
            "Document IDs to restrict retrieval to "
            "when using --query."
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "Number of chunks to retrieve in "
            "retrieval mode."
        ),
    )

    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help=(
            "Minimum similarity score for retrieved "
            "chunks in retrieval mode."
        ),
    )


    # ------------------------------------------------------------------------
    # PARSE ARGUMENTS
    # ------------------------------------------------------------------------

    args = parser.parse_args()


    # ------------------------------------------------------------------------
    # RUN PIPELINE

    if args.query:

        if not args.document_ids:
            raise SystemExit(
                "Error: --document-ids is required when using --query."
            )

        run_retrieval(
            query=args.query,
            document_ids=args.document_ids,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
        )

    else:
        run_pipeline(
            args.pdf_path,
            cleanup_input=args.cleanup_input,
            owner_email=args.owner_email or None,
            user_id=args.user_id or None,
            file_id=args.file_id or None,
        )