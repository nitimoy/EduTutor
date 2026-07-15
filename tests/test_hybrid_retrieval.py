"""Tests for Reciprocal Rank Fusion and HybridRetrievalStrategy."""

import pytest

from backend.evaluation.retrieval_engine import RetrievalEvaluationEngine
from backend.evaluation.retrieval_models import RetrievalQuery, RetrievalQueryDataset
from backend.retrieval.api.search import SearchResult
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
)
from backend.retrieval.strategies.fusion import (
    DEFAULT_RRF_K,
    reciprocal_rank_fusion,
)
from backend.retrieval.strategies.hybrid import HybridRetrievalStrategy


# ------------------------------------------------------------ RRF helper (pure)
def test_rrf_basic_formula():
    # doc "a": rank1 in list1 (1/61) + rank2 in list2 (1/62)
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    # a and b tie on score -> sorted by id ascending
    order = [cid for cid, _ in reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60)]
    assert order == ["a", "b"]


def test_rrf_agreement_beats_single_list_top():
    # "x" is rank1 in both lists; "y" is rank1 in one, absent in the other.
    fused = reciprocal_rank_fusion([["x", "y"], ["x"]], k=60)
    assert fused[0][0] == "x"
    assert fused[0][1] == pytest.approx(2 / 61)


def test_rrf_missing_documents_contribute_nothing():
    # "z" only appears in the second list at rank 2.
    fused = dict(reciprocal_rank_fusion([["a"], ["a", "z"]], k=60))
    assert fused["z"] == pytest.approx(1 / 62)
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 61)


def test_rrf_duplicate_ids_counted_once_per_list():
    # "a" duplicated in one list -> only its best (first) rank counts for that list.
    fused = dict(reciprocal_rank_fusion([["a", "a", "b"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)  # not 1/61 + 1/62


def test_rrf_configurable_k_changes_scores():
    low = dict(reciprocal_rank_fusion([["a", "b"]], k=1))
    high = dict(reciprocal_rank_fusion([["a", "b"]], k=1000))
    assert low["a"] == pytest.approx(1 / 2)
    assert high["a"] == pytest.approx(1 / 1001)


def test_rrf_rejects_nonpositive_k():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)


def test_rrf_deterministic_tie_break_is_id_ascending():
    # All three tie (rank1 each in its own singleton list) -> id ascending.
    order = [cid for cid, _ in reciprocal_rank_fusion([["z"], ["m"], ["a"]], k=60)]
    assert order == ["a", "m", "z"]


# ------------------------------------------------------------ weighted RRF
def test_rrf_default_weights_equal_unweighted():
    lists = [["a", "b", "c"], ["b", "c", "a"]]
    assert reciprocal_rank_fusion(lists, k=60) == \
           reciprocal_rank_fusion(lists, k=60, weights=[1.0, 1.0])


def test_rrf_weights_scale_contributions():
    # doc "a": list0 rank1 (w=2 -> 2/61) + list1 rank2 (w=1 -> 1/62)
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60, weights=[2.0, 1.0]))
    assert fused["a"] == pytest.approx(2.0 / 61 + 1.0 / 62)
    assert fused["b"] == pytest.approx(2.0 / 62 + 1.0 / 61)


def test_rrf_weight_favors_stronger_list_ordering():
    # list0 ("dense") ranks x#1,y#2; list1 ("bm25") ranks y#1,x#2.
    # Equal weights -> tie -> id order. Heavier list0 -> x wins.
    eq = [cid for cid, _ in reciprocal_rank_fusion([["x", "y"], ["y", "x"]], k=60)]
    assert eq == ["x", "y"]  # tie, id-ascending
    weighted = [cid for cid, _ in
                reciprocal_rank_fusion([["x", "y"], ["y", "x"]], k=60, weights=[2.0, 1.0])]
    assert weighted[0] == "x"  # heavier list0 lifts its #1


def test_rrf_weights_length_must_match():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], k=60, weights=[1.0])


def test_hybrid_accepts_weights_and_reports_them():
    a = FakeStrategy([("c1", "A"), ("c2", "B")], "dense")
    b = FakeStrategy([("c2", "B"), ("c1", "A")], "bm25")
    hybrid = HybridRetrievalStrategy([a, b], weights=[2.0, 1.0])
    md = hybrid.metadata()
    assert md.extra["weights"] == "2.0,1.0"
    # c1 is #1 in the heavier list -> should top fusion despite the tie under equal weights.
    assert hybrid.search("q", top_k=2)[0].document.concept_id == "c1"


def test_hybrid_weights_length_validation():
    with pytest.raises(ValueError):
        HybridRetrievalStrategy([FakeStrategy([("c1", "A")], "a")], weights=[1.0, 2.0])


# ------------------------------------------------------------ fake strategies
def _doc(cid, name="X", subject="physics"):
    return KnowledgeDocument(concept_id=cid, name=name, subject=subject, chapter="Chapter 1")


class FakeStrategy(RetrievalStrategy):
    """Returns a fixed ranked list of (concept_id, name) as SearchResults."""

    def __init__(self, ranked, name="fake"):
        self._ranked = ranked
        self._name = name

    def search(self, query, top_k=5, context=None):
        results = [
            SearchResult(score=1.0 / (i + 1), document=_doc(cid, nm))
            for i, (cid, nm) in enumerate(self._ranked)
        ]
        results = self._apply_context(results, context)
        return results[:top_k]

    def metadata(self):
        return StrategyMetadata(name=self._name, kind="lexical", deterministic=True)


# ------------------------------------------------------------ HybridRetrievalStrategy
def test_hybrid_fuses_two_strategies():
    a = FakeStrategy([("c1", "Alpha"), ("c2", "Beta")], name="a")
    b = FakeStrategy([("c2", "Beta"), ("c3", "Gamma")], name="b")
    hybrid = HybridRetrievalStrategy([a, b])
    results = hybrid.search("q", top_k=3)
    ids = [r.document.concept_id for r in results]
    # c2 appears in both (rank2+rank1) -> should top the fusion.
    assert ids[0] == "c2"
    assert set(ids) == {"c1", "c2", "c3"}


def test_hybrid_is_retrieval_strategy_and_metadata():
    h = HybridRetrievalStrategy([FakeStrategy([("c1", "A")], "a"),
                                 FakeStrategy([("c1", "A")], "b")], k=42)
    assert isinstance(h, RetrievalStrategy)
    md = h.metadata()
    assert md.kind == "hybrid" and md.deterministic is True
    assert md.extra["fusion"] == "rrf" and md.extra["k"] == "42"
    assert md.extra["components"] == "a,b"


def test_hybrid_determinism_and_tiebreak():
    a = FakeStrategy([("cz", "Z"), ("ca", "A")], "a")
    b = FakeStrategy([("ca", "A"), ("cz", "Z")], "b")
    hybrid = HybridRetrievalStrategy([a, b])
    r1 = [(r.document.concept_id, r.score) for r in hybrid.search("q", top_k=2)]
    r2 = [(r.document.concept_id, r.score) for r in hybrid.search("q", top_k=2)]
    assert r1 == r2
    # ca and cz tie -> id ascending
    assert [cid for cid, _ in r1] == ["ca", "cz"]


def test_hybrid_top_k_bounds():
    h = HybridRetrievalStrategy([FakeStrategy([("c1", "A"), ("c2", "B"), ("c3", "C")], "a"),
                                 FakeStrategy([("c2", "B")], "b")])
    assert h.search("q", top_k=0) == []
    assert len(h.search("q", top_k=2)) == 2


def test_hybrid_candidate_k_enables_deep_fusion():
    # Target "deep" is rank 8 in strategy A, absent in B. With candidate_k>=8 it is
    # pulled into the pool and can be fused; final top_k stays small.
    ranked = [(f"c{i}", f"N{i}") for i in range(7)] + [("deep", "Deep")]
    a = FakeStrategy(ranked, "a")
    b = FakeStrategy([("deep", "Deep")], "b")  # B ranks it #1
    hybrid = HybridRetrievalStrategy([a, b], candidate_k=10)
    ids = [r.document.concept_id for r in hybrid.search("q", top_k=5)]
    assert "deep" in ids  # fused from both despite being deep in A


def test_hybrid_requires_at_least_one_strategy():
    with pytest.raises(ValueError):
        HybridRetrievalStrategy([])


def test_hybrid_batch_search_matches_search():
    a = FakeStrategy([("c1", "A"), ("c2", "B")], "a")
    b = FakeStrategy([("c2", "B"), ("c3", "C")], "b")
    hybrid = HybridRetrievalStrategy([a, b])
    queries = ["q1", "q2"]
    batched = hybrid.batch_search(queries, top_k=3)
    for q, br in zip(queries, batched):
        sr = hybrid.search(q, top_k=3)
        assert [(r.document.concept_id, r.score) for r in br] == \
               [(r.document.concept_id, r.score) for r in sr]


def test_hybrid_context_filter_propagates():
    a = FakeStrategy([("c1", "A"), ("c2", "B")], "a")
    a._ranked = [("c1", "A"), ("c2", "B")]
    # make c2 chemistry so a subject filter drops it
    class SubjStrategy(FakeStrategy):
        def search(self, query, top_k=5, context=None):
            results = [
                SearchResult(score=1.0, document=_doc("c1", "A", "physics")),
                SearchResult(score=0.5, document=_doc("c2", "B", "chemistry")),
            ]
            results = self._apply_context(results, context)
            return results[:top_k]
    hybrid = HybridRetrievalStrategy([SubjStrategy([], "a"), SubjStrategy([], "b")])
    phys = hybrid.search("q", top_k=5, context=RetrievalContext(subject="physics"))
    assert all(r.document.subject == "physics" for r in phys)
    assert "c2" not in [r.document.concept_id for r in phys]


def test_hybrid_interchangeable_through_eval_engine():
    a = FakeStrategy([("c1", "Electric Charge")], "a")
    b = FakeStrategy([("c1", "Electric Charge")], "b")
    hybrid = HybridRetrievalStrategy([a, b])
    dataset = RetrievalQueryDataset(
        version="1.0", subject="physics", book="book.1",
        queries=[RetrievalQuery(query="charge", expected_concept_names=["Electric Charge"])],
    )
    report = RetrievalEvaluationEngine(hybrid).evaluate(dataset)
    assert report.overall_mrr == pytest.approx(1.0)
