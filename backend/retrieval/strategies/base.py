"""Retrieval strategy interface shared by every retrieval implementation.

See ``docs/retrieval_strategy_contract.md`` for the formal guarantees (determinism,
immutability, ordering, interface semantics) that every implementation must uphold.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field

# Reused, not redefined: the deterministic BM25F retriever already defines the
# canonical result type and the retrieval stop-word set, and the frozen evaluation
# engine consumes ``.document``. Reusing them keeps a single source of truth.
from backend.retrieval.api.search import SearchResult, _STOP_WORDS
from backend.retrieval.index.models import KnowledgeDocument

__all__ = [
    "RetrievalContext",
    "StrategyMetadata",
    "RetrievalStrategy",
    "SearchResult",
    "query_has_content",
]

_WORD_RE = re.compile(r"[a-z0-9]+")


def query_has_content(query: str) -> bool:
    """True if the query has at least one non-stop-word content token.

    Empty, whitespace/punctuation-only, and stop-word-only queries return False,
    so every strategy can uniformly honor the contract's "no content -> []" rule
    regardless of whether its backend happens to embed stop words.
    """
    return any(
        len(token) > 1 and token not in _STOP_WORDS
        for token in _WORD_RE.findall(query.lower())
    )


class RetrievalContext(BaseModel):
    """Optional query-time filters.

    Every field defaults to ``None`` so an empty context is a no-op — this keeps
    the ``search`` signature backward compatible with callers (including the frozen
    evaluation engine) that pass only ``query`` and ``top_k``. New filter
    dimensions are added here without changing the interface.
    """

    subject: Optional[str] = None
    chapter: Optional[str] = None
    concept_ids: Optional[list[str]] = None  # allowlist of concept ids

    def is_empty(self) -> bool:
        return self.subject is None and self.chapter is None and self.concept_ids is None

    def matches(self, document: KnowledgeDocument) -> bool:
        """Return True if ``document`` satisfies every active filter."""
        if self.subject is not None and document.subject != self.subject:
            return False
        if self.chapter is not None and document.chapter != self.chapter:
            return False
        if self.concept_ids is not None and document.concept_id not in self.concept_ids:
            return False
        return True


class StrategyMetadata(BaseModel):
    """Self-description of a retrieval strategy for reports and provenance."""

    name: str
    kind: str  # "lexical" | "dense" | "hybrid" | "reranker"
    deterministic: bool
    provider: Optional[str] = None
    model_id: Optional[str] = None
    dimension: Optional[int] = None
    extra: dict[str, str] = Field(default_factory=dict)


class RetrievalStrategy(ABC):
    """Common interface for all retrieval strategies.

    Implementations return ``list[SearchResult]`` (score + ``document``) so they
    plug directly into the frozen ``RetrievalEvaluationEngine`` and carry the
    scores that hybrid fusion / rerankers will need.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[SearchResult]:
        """Return up to ``top_k`` results, highest score first, deterministically."""

    def batch_search(
        self,
        queries: list[str],
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[list[SearchResult]]:
        """Run several queries.

        The default is a sequential loop; strategies with batched backends (e.g.
        dense embedding of all queries at once) override this for efficiency. The
        *results* must be identical to calling ``search`` per query — batching is
        an implementation optimization only.
        """
        return [self.search(query, top_k, context) for query in queries]

    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Describe this strategy (name, kind, determinism, model info)."""

    @staticmethod
    def _apply_context(
        results: list[SearchResult], context: Optional[RetrievalContext]
    ) -> list[SearchResult]:
        """Deterministically drop results that fail the context filter.

        Order-preserving, so applying it to an already-ranked list keeps the rank.
        """
        if context is None or context.is_empty():
            return results
        return [r for r in results if context.matches(r.document)]
