"""Real embeddings and an explicitly non-semantic offline test vectorizer."""

import asyncio
import hashlib
import math
import re
from typing import Protocol

from openai import AsyncOpenAI

from opspilot.core.config import Settings


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Deterministic lexical feature hashing. NOT a trained semantic model."""

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    async def embed(self, texts):
        results = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in re.findall(r"[a-z0-9_]+", text.lower()):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[index] += 1 if digest[4] & 1 else -1
            norm = math.sqrt(sum(x * x for x in vector)) or 1
            results.append([x / norm for x in vector])
        return results


class OpenAIEmbedder:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def embed(self, texts):
        async with AsyncOpenAI(
            api_key=self.settings.openai_api_key.get_secret_value(),
            timeout=self.settings.provider_timeout_seconds,
            max_retries=0,
        ) as client:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                result = await client.embeddings.create(
                    input=texts,
                    model=self.settings.embedding_model,
                    dimensions=self.settings.embedding_dimensions,
                )
        vectors = [r.embedding for r in sorted(result.data, key=lambda r: r.index)]
        if len(vectors) != len(texts) or any(
            len(v) != self.settings.embedding_dimensions or not all(math.isfinite(x) for x in v)
            for v in vectors
        ):
            raise ValueError("Embedding provider returned invalid dimensions or values")
        return vectors


def make_embedder(settings: Settings) -> Embedder:
    return (
        HashingEmbedder(settings.embedding_dimensions)
        if settings.mode == "demo"
        else OpenAIEmbedder(settings)
    )
