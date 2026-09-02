"""
Gemini embedding wrapper.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path
from typing import List

from google import genai

from .config import (
    GEMINI_API_KEY,
    EMBEDDING_MODEL,
    ENABLE_CACHE,
    CACHE_DIR,
    CACHE_EXTENSION,
)


class GeminiEmbedder:
    """
    Wrapper around Gemini's embedding API with optional file-based caching.
    """

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self._cache_path = Path(CACHE_DIR)
        if ENABLE_CACHE:
            self._cache_path.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_cached(self, text: str) -> List[float] | None:
        if not ENABLE_CACHE:
            return None
        key = self._cache_key(text)
        cache_file = self._cache_path / f"{key}{CACHE_EXTENSION}"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                return None
        return None

    def _set_cached(self, text: str, embedding: List[float]) -> None:
        if not ENABLE_CACHE:
            return
        key = self._cache_key(text)
        cache_file = self._cache_path / f"{key}{CACHE_EXTENSION}"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(embedding, f)
        except Exception:
            pass

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for a single piece of text.
        """

        text = text.strip()

        if not text:
            raise ValueError("Cannot embed empty text.")

        cached = self._get_cached(text)
        if cached is not None:
            return cached

        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )

        embedding = response.embeddings[0].values
        self._set_cached(text, embedding)
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        """

        embeddings = []

        for i, text in enumerate(texts):

            text = text.strip()

            if not text:
                print(f"Skipping empty text at index {i}")
                continue

            embeddings.append(self.embed_text(text))

        return embeddings
