"""Adaptive retrieval router.

Selects one existing retrieval strategy per query using deterministic routing
rules. Sits entirely above BM25F / Dense / Hybrid — none of them is modified or
aware of the router. Implements the ``RetrievalStrategy`` interface so it is a
drop-in for the frozen evaluation engine.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from backend.retrieval.api.search import SearchResult
from backend.retrieval.routing.analyzer import (
    QueryFeatures,
    analyze_query,
    build_concept_vocab,
)
from backend.retrieval.routing.rules import RoutingPolicy, build_policy
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
)


class RoutingDecision(BaseModel):
    """Which rule fired and which strategy was chosen for a query (for analysis)."""

    query: str
    chosen_strategy: str
    fired_rule: str  # rule name, or "default"
    features: QueryFeatures


class AdaptiveRouterStrategy(RetrievalStrategy):
    """Route each query to one of several strategies by deterministic rules."""

    def __init__(
        self,
        strategies: dict[str, RetrievalStrategy],
        policy: RoutingPolicy | str,
        concept_names: Optional[list[str]] = None,
        name: str = "adaptive_router",
    ) -> None:
        """
        Args:
            strategies: map of strategy id (e.g. "bm25f"/"dense"/"hybrid") to a
                concrete strategy. Every rule target + the policy default must be
                present here.
            policy: a RoutingPolicy or the name of a registered one.
            concept_names: optional concept names/aliases (from the Knowledge Index)
                used to detect exact-concept-lookup queries generically.
            name: router name for metadata.
        """
        self._strategies = strategies
        self._policy = build_policy(policy) if isinstance(policy, str) else policy
        self._vocab = build_concept_vocab(concept_names or {})
        self._name = name
        self._validate_targets()

    def _validate_targets(self) -> None:
        needed = {rule.target for rule in self._policy.rules} | {self._policy.default}
        missing = needed - set(self._strategies)
        if missing:
            raise ValueError(
                f"Policy '{self._policy.name}' needs strategies {sorted(missing)} "
                f"not provided (have {sorted(self._strategies)})"
            )

    # --- routing -----------------------------------------------------------
    def decide(self, query: str) -> RoutingDecision:
        """Return the routing decision for a query without executing retrieval."""
        features = analyze_query(query, self._vocab)
        for rule in self._policy.rules:
            if rule.predicate(features):
                return RoutingDecision(
                    query=query, chosen_strategy=rule.target,
                    fired_rule=rule.name, features=features,
                )
        return RoutingDecision(
            query=query, chosen_strategy=self._policy.default,
            fired_rule="default", features=features,
        )

    # --- RetrievalStrategy -------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[SearchResult]:
        decision = self.decide(query)
        return self._strategies[decision.chosen_strategy].search(query, top_k, context)

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name=self._name,
            kind="hybrid",  # composite router over multiple strategies
            deterministic=all(s.metadata().deterministic for s in self._strategies.values()),
            extra={
                "router": "adaptive",
                "policy": self._policy.name,
                "strategies": ",".join(sorted(self._strategies)),
            },
        )
