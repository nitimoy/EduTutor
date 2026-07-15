"""Strategy-based retrieval layer.

Every retrieval implementation (deterministic BM25F, dense embeddings, and future
hybrid / reranker strategies) implements the same :class:`RetrievalStrategy`
interface so they are interchangeable behind the retrieval evaluation framework.
"""

from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    SearchResult,
    StrategyMetadata,
)
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.retrieval.strategies.dense import DenseRetrievalStrategy
from backend.retrieval.strategies.fusion import (
    DEFAULT_RRF_K,
    reciprocal_rank_fusion,
)
from backend.retrieval.strategies.hybrid import HybridRetrievalStrategy

__all__ = [
    "RetrievalContext",
    "RetrievalStrategy",
    "SearchResult",
    "StrategyMetadata",
    "BM25FRetrievalStrategy",
    "DenseRetrievalStrategy",
    "HybridRetrievalStrategy",
    "reciprocal_rank_fusion",
    "DEFAULT_RRF_K",
]
