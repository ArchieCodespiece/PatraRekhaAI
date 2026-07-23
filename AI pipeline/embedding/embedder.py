"""
Gemini embedding wrapper.
"""

from __future__ import annotations

from typing import List

from google import genai

from .config import GEMINI_API_KEY, EMBEDDING_MODEL


class GeminiEmbedder:
    """
    Wrapper around Gemini's embedding API.
    """

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for a single piece of text.
        """

        text = text.strip()

        if not text:
            raise ValueError("Cannot embed empty text.")

        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )

        return response.embeddings[0].values

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Currently embeds sequentially to avoid batch formatting
        issues with the Gemini SDK.
        """

        embeddings = []

        for i, text in enumerate(texts):

            text = text.strip()

            if not text:
                print(f"Skipping empty text at index {i}")
                continue

            embeddings.append(self.embed_text(text))

        return embeddings
