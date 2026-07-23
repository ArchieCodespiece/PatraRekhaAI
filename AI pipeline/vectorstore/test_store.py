"""
Test script for the VectorStore module.
"""

from pathlib import Path
import sys

# Add the directory containing the sibling pipeline packages.
AI_PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))

from Chunking.pipeline import ChunkPipeline
from embedding.embedder import GeminiEmbedder
from embedding.pipeline import EmbeddingPipeline
from vectorstore.pipeline import VectorStorePipeline


def main():

    json_path = r"E:\PatraRekha\ingestion\Quality_Auditor_Tender_to_be_uploaded.json"  # <-- Change this

    # ---------------------------------------------------------
    # Chunking
    # ---------------------------------------------------------

    print("=" * 80)
    print("Generating semantic chunks...")
    print("=" * 80)

    chunk_pipeline = ChunkPipeline()

    chunks = chunk_pipeline.process(json_path)

    print(f"Generated {len(chunks)} chunks.\n")

    # ---------------------------------------------------------
    # Embedding
    # ---------------------------------------------------------

    print("=" * 80)
    print("Generating embeddings...")
    print("=" * 80)

    embedding_pipeline = EmbeddingPipeline()

    embedding_result = embedding_pipeline.process(chunks)

    print(
        f"Embedded {len(embedding_result.embedded_chunks)} chunks.\n"
    )

    # ---------------------------------------------------------
    # Upload
    # ---------------------------------------------------------

    print("=" * 80)
    print("Uploading to Pinecone...")
    print("=" * 80)

    vector_pipeline = VectorStorePipeline()

    vector_pipeline.upload(embedding_result)

    print("Upload completed.\n")

    # ---------------------------------------------------------
    # Index Statistics
    # ---------------------------------------------------------

    print("=" * 80)
    print("Index Statistics")
    print("=" * 80)

    stats = vector_pipeline.describe()

    print(stats)

    # ---------------------------------------------------------
    # Sample Query
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("Semantic Search")
    print("=" * 80)

    query = "What is the maximum age limit?"

    print(f"Query : {query}\n")

    embedder = GeminiEmbedder()

    query_embedding = embedder.embed_text(query)

    results = vector_pipeline.search(
        embedding=query_embedding,
        top_k=5,
    )

    for rank, match in enumerate(results.matches, start=1):

        print("-" * 80)

        print(f"Rank      : {rank}")
        print(f"Score     : {match.score:.4f}")

        metadata = match.metadata

        print(f"Document  : {metadata['document_name']}")
        print(
            f"Pages     : {metadata['page_start']}"
            f"-{metadata['page_end']}"
        )
        print(f"Section   : {metadata['section']}")

        print()
        print(metadata["text"][:500])
        print()

    print("=" * 80)
    print("VectorStore test completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()
