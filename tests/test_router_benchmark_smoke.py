"""Smoke guard for the router benchmark harness: it must import, and the routing
decision/features must be JSON-serializable (the benchmark writes them out)."""

import json

import scripts.router_benchmark as rb  # import must not require heavy deps
from backend.retrieval.api.search import SearchResult
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.routing.router import AdaptiveRouterStrategy
from backend.retrieval.strategies.base import RetrievalStrategy, StrategyMetadata


class _Tagged(RetrievalStrategy):
    def __init__(self, tag):
        self._tag = tag

    def search(self, query, top_k=5, context=None):
        return [SearchResult(score=1.0, document=KnowledgeDocument(
            concept_id=self._tag, name=self._tag, subject="physics", chapter="Chapter 1"))]

    def metadata(self):
        return StrategyMetadata(name=self._tag, kind="lexical", deterministic=True)


def test_benchmark_module_exposes_expected_helpers():
    assert hasattr(rb, "run") and hasattr(rb, "build_strategies")
    assert set(rb.SUBJECTS) == {"mathematics", "physics", "chemistry"}


def test_routing_decision_is_json_serializable():
    strategies = {"bm25f": _Tagged("bm25f"), "dense": _Tagged("dense"), "hybrid": _Tagged("hybrid")}
    router = AdaptiveRouterStrategy(strategies, "A_exact_to_bm25f", concept_names=["Electric Dipole"])
    decision = router.decide("electric dipole")
    payload = decision.model_dump()
    # round-trips through JSON (what the benchmark writes)
    restored = json.loads(json.dumps(payload))
    assert restored["chosen_strategy"] == "bm25f"
    assert restored["fired_rule"] == "exact_concept->bm25f"
    assert restored["features"]["exact_concept_match"] is True
