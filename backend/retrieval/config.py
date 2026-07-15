"""Configuration for the retrieval layer (strategies, embeddings, vector store)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Default embedding provider is the dependency-free hashing model. It exists to
# validate the embedding/vector-store infrastructure end to end without pulling in
# torch or downloading a model; the deterministic BM25F retriever remains the
# retrieval-quality baseline. Switch to "bge-m3" for the production backend.
DEFAULT_PROVIDER: Literal["hashing", "bge-m3"] = "hashing"
DEFAULT_HASHING_DIMENSION = 256
DEFAULT_BGE_M3_DIMENSION = 1024


class EmbeddingConfig(BaseModel):
    """Which embedding provider to use and its shape."""

    provider: str = DEFAULT_PROVIDER
    model_id: str = ""  # empty => provider's own default model id
    dimension: int = DEFAULT_HASHING_DIMENSION


class VectorStoreConfig(BaseModel):
    """Which vector store backend to hydrate embeddings into."""

    backend: Literal["local", "qdrant"] = "local"
    # Qdrant-only settings, ignored by the local store.
    qdrant_url: str = "http://localhost:6333"
    collection: str = "knowledge_index"


# RRF defaults for the hybrid strategy.
DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_K = 50


class HybridConfig(BaseModel):
    """Reciprocal Rank Fusion settings for the hybrid strategy."""

    k: int = DEFAULT_RRF_K            # RRF damping constant
    candidate_k: int = DEFAULT_CANDIDATE_K  # depth pulled from each component


class RetrievalConfig(BaseModel):
    """Top-level retrieval configuration."""

    strategy: Literal["bm25f", "dense", "hybrid"] = "bm25f"
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    hybrid: HybridConfig = Field(default_factory=HybridConfig)
    # Directory (under a compiled book dir) that holds versioned embedding artifacts.
    embeddings_dirname: str = "embeddings"
