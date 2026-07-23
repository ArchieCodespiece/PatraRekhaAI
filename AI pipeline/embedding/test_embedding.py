"""
Test script for the embedding pipeline.
"""

from pathlib import Path
import sys

# Running this file directly puts only ``embedding`` on Python's import path.
# Add its parent so the sibling ``Chunking`` package can be imported.
AI_PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(AI_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_DIR))

from embedding.pipeline import EmbeddingPipeline
from Chunking.pipeline import ChunkPipeline


def main():

    json_path = Path(r"E:\PatraRekha\ingestion\Quality_Auditor_Tender_to_be_uploaded.json")   # <-- Change this

    print("=" * 80)
    print("Generating semantic chunks...")
    print("=" * 80)

    chunk_pipeline = ChunkPipeline()
    chunks = chunk_pipeline.process(json_path)

    print(f"Generated {len(chunks)} chunks.\n")

    print("=" * 80)
    print("Generating embeddings...")
    print("=" * 80)

    embedding_pipeline = EmbeddingPipeline()
    result = embedding_pipeline.process(chunks)

    print(f"Embedded {len(result.embedded_chunks)} chunks.\n")

    print("=" * 80)
    print("Embedding Summary")
    print("=" * 80)

    for embedded_chunk in result.embedded_chunks:

        chunk = embedded_chunk.chunk
        metadata = chunk.metadata

        print(f"Chunk ID : {metadata.chunk_id}")
        print(f"Document : {metadata.document_name}")
        print(f"Pages    : {metadata.page_start}-{metadata.page_end}")
        print(f"Section  : {metadata.section}")

        print(f"Vector Dimension : {len(embedded_chunk.embedding)}")

        print(
            "First 10 Values  :",
            [round(v, 6) for v in embedded_chunk.embedding[:10]],
        )

        print("-" * 80)

    print("\nEmbedding test completed successfully.")


if __name__ == "__main__":
    main()
