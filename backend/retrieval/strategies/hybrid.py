"""Hybrid retrieval via Reciprocal Rank Fusion.

Orchestrates two or more existing ``RetrievalStrategy`` instances (in production:
frozen BM25F + Dense) and fuses their rankings with RRF. It sits entirely above the
component strategies — neither BM25F nor Dense is aware Hybrid exists, and no code
inside them is touched. Documents are fused by ``concept_id``; the resulting
``SearchResult.score`` is the RRF score.
"""

from __future__ import annotations

from typing import Optional

from backend.retrieval.api.search import SearchResult
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
)
from backend.retrieval.strategies.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion


class HybridRetrievalStrategy(RetrievalStrategy):
    """Fuse several retrieval strategies with Reciprocal Rank Fusion."""

    def __init__(
        self,
        strategies: list[RetrievalStrategy],
        k: int = DEFAULT_RRF_K,
        candidate_k: int = 50,
        weights: Optional[list[float]] = None,
        name: str = "hybrid_rrf",
    ) -> None:
        """
        Args:
            strategies: component strategies to fuse (order-independent for RRF).
            k: RRF damping constant.
            candidate_k: how deep to pull from each component before fusing. Must be
                >= the top_k you intend to request so a document ranked outside a
                strategy's top_k can still be fused from the other. Capped per call
                to at least the requested top_k.
            weights: optional per-strategy RRF weights, positionally aligned with
                ``strategies``. Defaults to equal (all 1.0) = standard RRF. Fixed
                configuration constants, not learned.
            name: strategy name reported in metadata / benchmarks.
        """
        if not strategies:
            raise ValueError("HybridRetrievalStrategy needs at least one strategy")
        if k <= 0:
            raise ValueError("RRF k must be positive")
        if candidate_k <= 0:
            raise ValueError("candidate_k must be positive")
        if weights is not None and len(weights) != len(strategies):
            raise ValueError("weights length must match number of strategies")
        self._strategies = strategies
        self._k = k
        self._candidate_k = candidate_k
        self._weights = weights
        self._name = name

    def search(
        self,
        query: str,
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            return []
        component_results = [
            strategy.search(query, self._pool(top_k), context)
            for strategy in self._strategies
        ]
        return self._fuse(component_results, top_k)

    def batch_search(
        self,
        queries: list[str],
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[list[SearchResult]]:
        if top_k <= 0:
            return [[] for _ in queries]
        # Delegate to each component's batch_search (Dense embeds all queries in one
        # pass), then fuse per query — results match calling search() per query.
        pool = self._pool(top_k)
        per_strategy = [
            strategy.batch_search(queries, pool, context) for strategy in self._strategies
        ]
        out: list[list[SearchResult]] = []
        for q_index in range(len(queries)):
            out.append(self._fuse([per_strategy[s][q_index] for s in range(len(self._strategies))], top_k))
        return out

    def metadata(self) -> StrategyMetadata:
        weights = self._weights if self._weights is not None else [1.0] * len(self._strategies)
        return StrategyMetadata(
            name=self._name,
            kind="hybrid",
            deterministic=all(s.metadata().deterministic for s in self._strategies),
            extra={
                "fusion": "rrf",
                "k": str(self._k),
                "candidate_k": str(self._candidate_k),
                "weights": ",".join(str(w) for w in weights),
                "components": ",".join(s.metadata().name for s in self._strategies),
            },
        )

    # --- internals ---------------------------------------------------------
    def _pool(self, top_k: int) -> int:
        return max(self._candidate_k, top_k)

    def _fuse(
        self, component_results: list[list[SearchResult]], top_k: int
    ) -> list[SearchResult]:
        ranked_id_lists: list[list[str]] = []
        docs_by_id: dict[str, KnowledgeDocument] = {}
        for results in component_results:
            ids: list[str] = []
            for res in results:
                cid = res.document.concept_id
                ids.append(cid)
                docs_by_id.setdefault(cid, res.document)
            ranked_id_lists.append(ids)

        fused = reciprocal_rank_fusion(ranked_id_lists, k=self._k, weights=self._weights)

        # Ensure BM25F top results are always included (they're more reliable)
        if len(ranked_id_lists) >= 1:
            bm25f_ids = set(ranked_id_lists[0][:top_k])
            fused_ids = {cid for cid, _ in fused[:top_k]}
            # Add any BM25F top results that aren't in the fused set
            for cid in ranked_id_lists[0][:top_k]:
                if cid not in fused_ids and cid in docs_by_id:
                    fused.append((cid, 0.001))  # Add with minimal score

        return [
            SearchResult(score=round(score, 6), document=docs_by_id[cid])
            for cid, score in fused[:top_k]
        ]
