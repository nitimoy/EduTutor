"""Tests for the TeachingPlan → TutorPlan seam (what Phase 5 will edit)."""

from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult
from backend.tutor.composer import TutorBrain
from backend.tutor.models import (
    SectionKind,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
)


def _results():
    primary = KnowledgeDocument(
        concept_id="c1", name="Alpha", subject="physics", chapter="Ch1",
        definition_texts=["Alpha is the first."], prerequisites=["Beta"],
        related_concepts=["Gamma"])
    beta = KnowledgeDocument(concept_id="c2", name="Beta", subject="physics", chapter="Ch1")
    return [SearchResult(score=2.0, document=primary), SearchResult(score=1.0, document=beta)]


def test_build_teaching_plan_is_intermediate_and_mutable():
    tp = TutorBrain().build_teaching_plan("what is alpha", _results())
    assert isinstance(tp, TeachingPlan)
    assert tp.primary_concept_id == "c1"
    assert any(s.kind == SectionKind.MAIN_EXPLANATION for s in tp.sections)


def test_editing_plan_then_composing_reflects_edit_without_retrieval():
    brain = TutorBrain()
    results = _results()
    tp = brain.build_teaching_plan("what is alpha", results)

    # Student-Model-style edit: keep only the main explanation, change the strategy.
    tp.sections = [s for s in tp.sections if s.kind == SectionKind.MAIN_EXPLANATION]
    tp.strategy = TeachingStrategyKind.REVISION_SUMMARY

    # compose_from takes only the (edited) plan + results — no re-retrieval.
    plan = brain.compose_from(tp, results)
    assert plan.strategy == TeachingStrategyKind.REVISION_SUMMARY
    assert plan.main_explanation.status == SectionStatus.PRESENT
    assert plan.main_explanation.items == ["Alpha is the first."]
    # dropped sections become empty slots in the final plan
    assert plan.prerequisites.status == SectionStatus.EMPTY
    assert plan.related_concepts.status == SectionStatus.EMPTY


def test_compose_from_is_deterministic():
    brain = TutorBrain()
    results = _results()
    tp = brain.build_teaching_plan("what is alpha", results)
    a = brain.compose_from(tp, results).model_dump_json()
    b = brain.compose_from(tp, results).model_dump_json()
    assert a == b
