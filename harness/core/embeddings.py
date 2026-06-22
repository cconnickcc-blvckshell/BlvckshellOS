"""Embedding client abstraction.

Mirrors :mod:`harness.core.llm`: stores never call vendor SDKs directly, they
call an :class:`EmbeddingClient`. Embeddings are stored as plain float lists
(no pgvector dependency) and ranked by cosine similarity in Python over a
bounded candidate set, the same fallback shape already used for ``ilike``
keyword search elsewhere in this codebase.

- :class:`OpenAIEmbeddingClient` — ``text-embedding-3-small`` (optional ``openai`` package)
- :class:`HashEmbeddingClient` — deterministic offline fallback (tests/no-keys mode)
"""

from __future__ import annotations

import abc
import hashlib
import math

from harness.config import Settings
from harness.logging_config import get_logger

logger = get_logger("embeddings")


class EmbeddingClient(abc.ABC):
    """Abstract text-to-vector embedding client."""

    @abc.abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for ``text``."""


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI-backed embedding client."""

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # type: ignore[assignment]

    def _require(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Embed ``text`` via the OpenAI embeddings API."""
        resp = await self._require().embeddings.create(model=self._model, input=text)
        return list(resp.data[0].embedding)


_HASH_DIMS = 256


class HashEmbeddingClient(EmbeddingClient):
    """Deterministic offline embedding client (tests/no-keys mode).

    Hashes overlapping word shingles into a fixed-size bag-of-features vector.
    Not semantically meaningful, but stable and good enough to exercise the
    full retrieval pipeline (storage, ranking, recall) without any API key.
    """

    async def embed(self, text: str) -> list[float]:
        """Return a deterministic pseudo-embedding for ``text``."""
        vec = [0.0] * _HASH_DIMS
        words = text.lower().split()
        for word in words:
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % _HASH_DIMS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_embedding_client(settings: Settings) -> EmbeddingClient:
    """Build the configured embedding client, falling back to the offline hash client."""
    if settings.openai_enabled:
        logger.info("embedding_client_selected", provider="openai")
        return OpenAIEmbeddingClient(settings.openai_api_key, settings.openai_embedding_model)
    logger.info("embedding_client_selected", provider="hash")
    return HashEmbeddingClient()
