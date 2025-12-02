# temporal_mem/embedding/openai_embedder.py

from __future__ import annotations

import os
from typing import List, Optional

from openai import OpenAI


class OpenAIEmbedder:
    """
    Simple OpenAI embedding wrapper.

    Responsibilities:
    - Create a client
    - Embed a single text or list of texts
    - Return list[float] for single, list[list[float]] for batch
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIEmbedder")

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed_one(self, text: str) -> List[float]:
        """
        Embed a single text and return its embedding vector.
        """
        text = text or ""
        resp = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return resp.data[0].embedding

    def embed_many(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts and return list of vectors.
        """
        if not texts:
            return []
        resp = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [d.embedding for d in resp.data]
