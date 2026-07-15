"""Tests for the Answer Composer + TutorBrain full pipeline."""

import pytest

from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult
from backend.tutor.composer import TutorBrain, _assert_no_invention
from backend.tutor.models import (
    Citation,
    EducationalIntent,
    SectionStatus,
    TeachingStrategyKind,
    TutorPlan,
)
from backend.tutor.repository import KnowledgeRepository, RecoveredObject


def _doc(cid, name, **kw):
    return KnowledgeDocument(concept_id=cid, name=name, subject="physics", chapter="Ch1", **kw)


def _results(*docs):
    return [SearchResult(score=float(len(docs) - i), document=d) for i, d in enumerate(docs)]


class _ProofRepo(KnowledgeRepository):
    def get_concept(self, concept_id):
        return None

    def recover_objects(self, concept_id, kinds):
        return [RecoveredObject(object_id=f"{k}-obj", type=k, text=f"{k} body")
                for k in kinds if k == "proof"]


def test_full_plan_is_deterministic():
    brain = TutorBrain()
    results = _results(_doc("c1", "Alpha", definition_texts=["d"]), _doc("c2", "Beta"))
    a = brain.plan("what is alpha", results).model_dump_json()
    b = brain.plan("what is alpha", results).model_dump_json()
    assert a == b


def test_empty_retrieval_yields_minimal_valid_plan():
    plan = TutorBrain().plan("what is nothing", [])
    assert isinstance(plan, TutorPlan)
    assert plan.primary_concept_id is None
    assert plan.main_explanation.status == SectionStatus.EMPTY
    assert plan.references == []


def test_proof_present_with_repository():
    results = _results(_doc("c1", "Alpha", definition_texts=["d"]))
    plan = TutorBrain().plan("prove alpha", results, _ProofRepo())
    assert plan.intent == EducationalIntent.PROOF
    assert plan.strategy == TeachingStrategyKind.STEP_BY_STEP_DERIVATION
    assert plan.proof.status == SectionStatus.PRESENT
    assert plan.proof.citations[0].object_type == "proof"


def test_proof_without_repository_falls_back_and_notes_it():
    results = _results(_doc("c1", "Alpha", definition_texts=["d"]))
    plan = TutorBrain().plan("prove alpha", results)  # no repository
    assert plan.intent == EducationalIntent.PROOF
    assert plan.strategy == TeachingStrategyKind.CONCEPT_EXPLANATION  # fell back
    assert plan.proof.status == SectionStatus.EMPTY  # proof not in the fallback template
    assert any("proof" in n for n in plan.notes)  # fallback reason is recorded


def test_unsupported_by_index_surfaces_for_exercise_without_repo():
    # worked-example intent with examples present -> worked_example_walkthrough (no fallback);
    # its template includes EXERCISE, which is unsupported without a repository.
    results = _results(_doc("c1", "Alpha", example_texts=["worked ex"]))
    plan = TutorBrain().plan("give a worked example of alpha", results)
    assert plan.strategy == TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH
    assert plan.exercise.status == SectionStatus.UNSUPPORTED_BY_INDEX
    assert any("Misconceptions and derivations" in n for n in plan.notes)


def test_no_invention_invariant_passes_for_normal_plan():
    results = _results(_doc("c1", "Alpha", definition_texts=["d"]), _doc("c2", "Beta"))
    plan = TutorBrain().plan("what is alpha", results)
    valid = {"c1", "c2"}
    for c in plan.references:
        assert c.concept_id is None or c.concept_id in valid


def test_no_invention_invariant_raises_on_fabricated_id():
    plan = TutorBrain().plan("what is alpha", _results(_doc("c1", "Alpha", definition_texts=["d"])))
    plan.references.append(Citation(
        concept_id="c-ghost", concept_name="Ghost", source_field="definition_texts", locator="0"))
    with pytest.raises(AssertionError):
        _assert_no_invention(plan, {"c1"})


def test_tutorplan_has_no_synthesized_application_slot():
    # Structural guarantee: compiler-backed slots only, no synthesized 'application'.
    assert "application" not in TutorPlan.model_fields


def test_plan_for_query_wires_a_strategy():
    class FakeStrategy:
        def search(self, query, top_k=5, context=None):
            return _results(_doc("c1", "Alpha", definition_texts=["d"]))

    plan = TutorBrain().plan_for_query("what is alpha", FakeStrategy())
    assert plan.primary_concept_id == "c1"
