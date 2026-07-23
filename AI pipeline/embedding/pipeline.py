from typing import List

from Chunking.models import Chunk
from models import EmbeddedChunk, EmbeddingResult
from embedder import GeminiEmbedder


class EmbeddingPipeline:
    """End-to-end embedding pipeline."""

    def __init__(self):
        self.embedder = GeminiEmbedder()

    def process(self, chunks: List[Chunk]) -> EmbeddingResult:
        """
        Generate embeddings for a list of chunks.

        Parameters
        ----------
        chunks : List[Chunk]

        Returns
        -------
        EmbeddingResult
        """

        valid_chunks = []

        for chunk in chunks:
            if chunk.text and chunk.text.strip():
                valid_chunks.append(chunk)
            else:
                print(
                    f"Skipping empty chunk: "
                    f"{chunk.metadata.chunk_id}"
                )

        if not valid_chunks:
            raise ValueError("No valid chunks found for embedding.")

        texts = [chunk.text.strip() for chunk in valid_chunks]

        embeddings = self.embedder.embed_batch(texts)

        embedded_chunks = [
            EmbeddedChunk(
                chunk=chunk,
                embedding=embedding,
            )
            for chunk, embedding in zip(valid_chunks, embeddings)
        ]

        return EmbeddingResult(
            embedded_chunks=embedded_chunks
        )