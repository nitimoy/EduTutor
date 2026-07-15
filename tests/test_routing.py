"""Tests for the deterministic adaptive retrieval router."""

import pytest

from backend.evaluation.retrieval_engine import RetrievalEvaluationEngine
from backend.evaluation.retrieval_models import RetrievalQuery, RetrievalQueryDataset
from backend.retrieval.api.search import SearchResult
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.routing.analyzer import (
    analyze_query,
    build_concept_vocab,
)
from backend.retrieval.routing.router import AdaptiveRouterStrategy
from backend.retrieval.routing.rules import (
    POLICIES,
    RoutingPolicy,
    RoutingRule,
    build_policy,
)
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
)


# ---------------------------------------------------------------- analyzer
def test_analyze_definition_query():
    f = analyze_query("What is an electric dipole?")
    assert f.is_definition and not f.is_explanation and not f.is_comparison


def test_analyze_explanation_query():
    f = analyze_query("How does flux relate to charge?")
    assert f.is_explanation and not f.is_definition


def test_analyze_comparison_takes_precedence():
    f = analyze_query("What is the difference between AC and DC?")
    assert f.is_comparison
    assert not f.is_definition  # comparison suppresses definition/explanation


def test_analyze_math_notation():
    assert analyze_query("solve x = 2 + 3").has_math_notation
    assert analyze_query("what is E = mc^2").has_math_notation
    assert not analyze_query("what is energy").has_math_notation


def test_analyze_quoted_phrase():
    f = analyze_query('define "electric dipole"')
    assert f.has_quoted_phrase and f.quoted_phrases == ["electric dipole"]


def test_exact_concept_match_uses_vocab_not_hardcoding():
    vocab = build_concept_vocab(["Electric Dipole", "Gauss's Law"])
    # word-order / stop-words don't matter (frozenset of content words)
    f = analyze_query("electric dipole", vocab)
    assert f.exact_concept_match and f.matched_concept == "Electric Dipole"
    f2 = analyze_query("what is thermodynamics", vocab)
    assert not f2.exact_concept_match


def test_analyze_length():
    assert analyze_query("what is the of a").length_tokens == 0  # all stop words
    assert analyze_query("electric dipole moment").length_tokens == 3


# ---------------------------------------------------------------- rules / policies
def test_named_policies_exist():
    for name in ("A_exact_to_bm25f", "B_formula_bm25f_explain_dense",
                 "C_exact_bm25f_else_dense", "D_exact_to_hybrid"):
        assert name in POLICIES
        assert build_policy(name).name == name


def test_build_policy_rejects_unknown():
    with pytest.raises(ValueError):
        build_policy("nonexistent")


# ---------------------------------------------------------------- fake strategies
def _doc(cid, name, subject="physics"):
    return KnowledgeDocument(concept_id=cid, name=name, subject=subject, chapter="Chapter 1")


class Tagged(RetrievalStrategy):
    """Returns a single result whose concept_id is the strategy tag, so tests can
    see which strategy the router invoked."""

    def __init__(self, tag):
        self._tag = tag

    def search(self, query, top_k=5, context=None):
        res = [SearchResult(score=1.0, document=_doc(self._tag, self._tag))]
        return self._apply_context(res, context)[:top_k]

    def metadata(self):
        return StrategyMetadata(name=self._tag, kind="lexical", deterministic=True)


def _router(policy, concept_names=None):
    strategies = {"bm25f": Tagged("bm25f"), "dense": Tagged("dense"), "hybrid": Tagged("hybrid")}
    return AdaptiveRouterStrategy(strategies, policy, concept_names=concept_names or [])


# ---------------------------------------------------------------- routing behavior
def test_policy_a_routes_definition_to_dense_default():
    r = _router("A_exact_to_bm25f")
    # "what is energy" -> definition, no exact match -> default Dense
    assert r.search("what is energy")[0].document.concept_id == "dense"


def test_policy_a_routes_exact_concept_to_bm25f():
    r = _router("A_exact_to_bm25f", concept_names=["Electric Dipole"])
    d = r.decide("electric dipole")
    assert d.fired_rule == "exact_concept->bm25f" and d.chosen_strategy == "bm25f"


def test_policy_a_math_to_bm25f():
    r = _router("A_exact_to_bm25f")
    d = r.decide("compute x = 2 + 2")
    assert d.chosen_strategy == "bm25f" and d.fired_rule == "math_notation->bm25f"


def test_rule_precedence_first_match_wins():
    # A query that is BOTH an exact concept AND math: exact_concept rule is first.
    r = _router("A_exact_to_bm25f", concept_names=["Sigma"])
    # "sigma = 5" is math and, if "sigma" were the whole content, exact.
    d = r.decide("sigma")
    assert d.fired_rule == "exact_concept->bm25f"


def test_policy_d_routes_exact_to_hybrid():
    r = _router("D_exact_to_hybrid", concept_names=["Electric Field"])
    assert r.decide("electric field").chosen_strategy == "hybrid"


def test_default_fires_when_no_rule_matches():
    r = _router("C_exact_bm25f_else_dense")
    d = r.decide("explain the significance of fields")  # explanation, no exact -> default
    assert d.fired_rule == "default" and d.chosen_strategy == "dense"


def test_router_is_deterministic():
    r = _router("A_exact_to_bm25f", concept_names=["Electric Dipole"])
    a = [r.decide("electric dipole").chosen_strategy for _ in range(5)]
    assert len(set(a)) == 1


def test_router_validates_missing_target_strategy():
    # Policy A needs bm25f + dense; omit bm25f -> error.
    with pytest.raises(ValueError):
        AdaptiveRouterStrategy({"dense": Tagged("dense")}, "A_exact_to_bm25f")


def test_router_is_retrieval_strategy_and_metadata():
    r = _router("A_exact_to_bm25f")
    assert isinstance(r, RetrievalStrategy)
    md = r.metadata()
    assert md.extra["router"] == "adaptive" and md.extra["policy"] == "A_exact_to_bm25f"


def test_router_context_propagates():
    class SubjTagged(Tagged):
        def search(self, query, top_k=5, context=None):
            res = [SearchResult(score=1.0, document=_doc(self._tag, self._tag, "physics"))]
            return self._apply_context(res, context)[:top_k]
    strategies = {"bm25f": SubjTagged("bm25f"), "dense": SubjTagged("dense")}
    r = AdaptiveRouterStrategy(strategies, RoutingPolicy(
        "x", (RoutingRule("exact->bm25f", lambda f: f.exact_concept_match, "bm25f"),), "dense"),
        concept_names=[])
    out = r.search("anything", context=RetrievalContext(subject="chemistry"))
    assert out == []  # physics doc filtered out by chemistry context


def test_router_interchangeable_through_eval_engine():
    r = _router("A_exact_to_bm25f", concept_names=["Electric Charge"])
    dataset = RetrievalQueryDataset(
        version="1.0", subject="physics", book="b",
        queries=[RetrievalQuery(query="what is momentum", expected_concept_names=["Dense"])],
    )
    report = RetrievalEvaluationEngine(r).evaluate(dataset)
    assert 0.0 <= report.overall_mrr <= 1.0
