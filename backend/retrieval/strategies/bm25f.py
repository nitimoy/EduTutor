"""BM25F retrieval as a strategy.

Thin adapter over the frozen deterministic retriever in
``backend.retrieval.api.search``. The BM25F implementation itself is not modified;
this class only conforms it to the :class:`RetrievalStrategy` interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.retrieval.api.search import RetrievalAPI, SearchResult
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
)


class BM25FRetrievalStrategy(RetrievalStrategy):
    """Deterministic lexical BM25F retrieval."""

    def __init__(self, path: Path) -> None:
        self._api = RetrievalAPI(path)

    def search(
        self,
        query: str,
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[SearchResult]:
        if context is None or context.is_empty():
            return self._api.search(query, top_k)

        # The underlying retriever truncates to top_k internally, so over-fetch a
        # larger candidate pool, filter by context, then truncate — keeping the
        # BM25F ordering intact. The pool is capped at the corpus size.
        pool = min(len(self._api.documents), max(top_k * 5, 50))
        candidates = self._api.search(query, pool)
        return self._apply_context(candidates, context)[:top_k]

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="bm25f",
            kind="lexical",
            deterministic=True,
        )
