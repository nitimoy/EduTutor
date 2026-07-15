"""Vector store abstraction and backends.

Vector stores are *caches* over the canonical EmbeddingIndex — disposable and
rebuildable. Retrieval depends only on the ``VectorStore`` interface; concrete
backends (local, Qdrant) never leak their types past it.
"""

from backend.retrieval.vectorstore.base import VectorHit, VectorRecord, VectorStore
from backend.retrieval.vectorstore.local import LocalVectorStore

__all__ = ["VectorStore", "VectorRecord", "VectorHit", "LocalVectorStore"]
