"""Embedding provider abstraction and the dependency-free hashing provider.

``EmbeddingProvider`` is the swappable model boundary: retrieval logic depends on
this interface, never on a concrete model. ``HashingEmbeddingProvider`` is a pure
Python, deterministic provider used as the default for tests and CI — it validates
the embedding/vector-store infrastructure end to end without torch or a model
download. It is NOT a quality baseline; the deterministic BM25F retriever is.
Production embeddings use ``BGEM3EmbeddingProvider`` (see ``bge_m3.py``).
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingProvider(ABC):
    """Turns text into deterministic dense vectors."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Stable provider slug, e.g. 'hashing' or 'bge-m3'."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Stable model identifier, e.g. 'BAAI/bge-m3'."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashed bag-of-words provider (offline, no dependencies).

    Tokens are hashed (via SHA-1, so results are independent of PYTHONHASHSEED)
    into a fixed-dimension vector with signed buckets, then L2-normalized. Same
    text always yields the same vector.
    """

    def __init__(self, dimension: int = 256) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def provider_id(self) -> str:
        return "hashing"

    @property
    def model_id(self) -> str:
        return f"hashing-bow-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]
