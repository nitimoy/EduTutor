"""Integration: personalize → apply → frozen Tutor Brain composer → TutorPlan."""

from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult
from backend.student.applier import TeachingPlanApplier
from backend.student.engine import StudentModel
from backend.student.models import (
    DifficultyPreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)
from backend.tutor.composer import TutorBrain
from backend.tutor.models import SectionStatus, TutorPlan


def _results():
    primary = KnowledgeDocument(
        concept_id="c1", name="Alpha", subject="physics", chapter="Ch1",
        definition_texts=["Alpha is first."], example_texts=["worked ex"],
        prerequisites=["Beta"])
    beta = KnowledgeDocument(concept_id="c2", name="Beta", subject="physics", chapter="Ch1")
    return [SearchResult(score=2.0, document=primary), SearchResult(score=1.0, document=beta)]


def test_full_path_yields_valid_tutorplan():
    brain = TutorBrain()
    results = _results()
    base = brain.build_teaching_plan("give a worked example of alpha", results)
    profile = StudentProfile(state=StudentState(concept_mastery={"c1": 0.1}))
    tutor = StudentModel().personalize_and_compose(base, profile, results, brain)
    assert isinstance(tutor, TutorPlan)
    assert tutor.primary_concept_id == "c1"


def test_suppressed_section_becomes_empty_slot():
    brain = TutorBrain()
    results = _results()
    # worked-example intent keeps its template (examples present); low mastery suppresses
    # proof via the difficulty rule -> proof slot ends up EMPTY.
    base = brain.build_teaching_plan("give a worked example of alpha", results)
    profile = StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}),
        preferences=StudentPreferences(difficulty=DifficultyPreference.EASY))
    model = StudentModel()
    applier = TeachingPlanApplier()
    delta = model.personalize(base, profile)
    tutor = brain.compose_from(applier.apply(delta), results)
    assert tutor.proof.status in (SectionStatus.EMPTY, SectionStatus.UNSUPPORTED_BY_INDEX)


def test_personalization_changes_nothing_in_retrieved_content():
    brain = TutorBrain()
    results = _results()
    base = brain.build_teaching_plan("what is alpha", results)
    baseline = brain.compose_from(base, results)
    profile = StudentProfile(state=StudentState(concept_mastery={"c1": 0.1}))
    personalized = StudentModel().personalize_and_compose(base, profile, results, brain)
    # Same underlying facts: main explanation items are unchanged by personalization.
    assert personalized.main_explanation.items == baseline.main_explanation.items


def test_full_path_is_deterministic():
    brain = TutorBrain()
    results = _results()
    base = brain.build_teaching_plan("what is alpha", results)
    profile = StudentProfile(state=StudentState(concept_mastery={"c1": 0.1}))
    a = StudentModel().personalize_and_compose(base, profile, results, brain).model_dump_json()
    b = StudentModel().personalize_and_compose(base, profile, results, brain).model_dump_json()
    assert a == b
