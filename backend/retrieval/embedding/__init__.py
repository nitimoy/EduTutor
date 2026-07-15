"""Embedding layer: providers, document-text builder, provenance, and the
canonical versioned EmbeddingIndex.

The Knowledge Index is the only input. Vectors are a derived, rebuildable
representation; vector stores are caches hydrated from the EmbeddingIndex.
"""

from backend.retrieval.embedding.builder import EmbeddingBuilder, document_text
from backend.retrieval.embedding.index import BuildResult, EmbeddingIndex
from backend.retrieval.embedding.provider import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
)
from backend.retrieval.embedding.provenance import (
    EmbeddingManifest,
    EmbeddingProvenance,
)

__all__ = [
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "EmbeddingBuilder",
    "document_text",
    "EmbeddingProvenance",
    "EmbeddingManifest",
    "EmbeddingIndex",
    "BuildResult",
]
