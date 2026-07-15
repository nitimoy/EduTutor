"""Tests for the deterministic Tutor Brain evaluation engine + benchmark smoke."""

from backend.evaluation.tutor_eval import TutorPlanEvaluationEngine
from backend.evaluation.tutor_models import TutorCase, TutorEvalDataset
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex
from backend.retrieval.strategies.base import SearchResult


def _doc(cid, name, **kw):
    return KnowledgeDocument(concept_id=cid, name=name, subject="physics", chapter="Ch1", **kw)


class _FakeStrategy:
    """Returns a fixed 2-doc result for any query.

    Alpha lists Beta as a prerequisite, so the concept-explanation template cites Beta
    (resolved to c2) — letting the citation-validity test exercise an out-of-index id.
    """

    def search(self, query, top_k=5, context=None):
        return [SearchResult(score=2.0, document=_doc(
                    "c1", "Alpha", definition_texts=["d"], prerequisites=["Beta"])),
                SearchResult(score=1.0, document=_doc("c2", "Beta"))]


def _index(*cids):
    return KnowledgeIndex(book_id="b", documents=[_doc(c, c) for c in cids])


def _dataset(*cases):
    return TutorEvalDataset(version="1.0", subject="physics", book="b", cases=list(cases))


def test_metrics_on_correct_cases():
    engine = TutorPlanEvaluationEngine(_FakeStrategy(), _index("c1", "c2"))
    ds = _dataset(
        TutorCase(query="what is alpha", expected_intent="definition",
                  expected_primary_concept_name="Alpha"),
        TutorCase(query="what is alpha again", expected_intent="definition"),
    )
    report = engine.evaluate(ds)
    assert report.n_cases == 2
    assert report.intent_accuracy == 1.0
    assert report.primary_accuracy == 1.0
    assert report.citation_validity == 1.0
    assert report.no_hallucination_rate == 1.0
    assert report.deterministic is True


def test_intent_accuracy_aggregates_mismatches():
    engine = TutorPlanEvaluationEngine(_FakeStrategy(), _index("c1", "c2"))
    ds = _dataset(
        TutorCase(query="what is alpha", expected_intent="definition"),   # correct
        TutorCase(query="what is beta", expected_intent="formula"),        # wrong label
    )
    report = engine.evaluate(ds)
    assert report.intent_accuracy == 0.5


def test_citation_validity_flags_out_of_index_references():
    # Beta (c2) is retrieved and cited but absent from the eval index -> invalid reference.
    engine = TutorPlanEvaluationEngine(_FakeStrategy(), _index("c1"))
    report = engine.evaluate(_dataset(TutorCase(query="what is alpha")))
    assert report.citation_validity < 1.0
    assert report.no_hallucination_rate < 1.0


def test_benchmark_module_imports_and_exposes_helpers():
    import scripts.tutor_benchmark as tb  # must import without heavy deps

    assert hasattr(tb, "run") and hasattr(tb, "EXAMPLES")
    assert set(tb.SUBJECTS) == {"mathematics", "physics", "chemistry"}
