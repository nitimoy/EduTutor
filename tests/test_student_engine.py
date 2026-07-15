"""Tests for the StudentModel engine: decisions, priority order, axis conflicts."""

from backend.student.engine import StudentModel
from backend.student.models import (
    DifficultyPreference,
    ExamplePreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)
from backend.tutor.models import (
    EducationalIntent,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
)


def _plan():
    kinds = (SectionKind.MAIN_EXPLANATION, SectionKind.PREREQUISITES, SectionKind.PROOF,
             SectionKind.WORKED_EXAMPLE, SectionKind.SUMMARY)
    return TeachingPlan(
        query="q", intent=EducationalIntent.PROOF,
        strategy=TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
        primary_concept_id="c1", primary_concept_name="Alpha",
        sections=[SectionSpec(kind=k, status=SectionStatus.PRESENT) for k in kinds])


def test_beginner_decisions():
    profile = StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}, prerequisite_gaps=["c0"]),
        preferences=StudentPreferences(difficulty=DifficultyPreference.EASY,
                                       example=ExamplePreference.MANY))
    delta = StudentModel().personalize(_plan(), profile)
    actions = [d.action.value for d in delta.decisions]
    assert "insert_prerequisite_review" in actions
    assert "lower_difficulty" in actions
    assert "increase_worked_examples" in actions


def test_decisions_are_priority_ordered():
    profile = StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}, prerequisite_gaps=["c0"]))
    delta = StudentModel().personalize(_plan(), profile)
    priorities = [d.priority for d in delta.decisions]
    assert priorities == sorted(priorities)


def test_axis_conflict_only_one_difficulty_decision():
    # low mastery (lower) AND challenging pref (raise) both fire on axis 'difficulty'.
    profile = StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}),
        preferences=StudentPreferences(difficulty=DifficultyPreference.CHALLENGING))
    delta = StudentModel().personalize(_plan(), profile)
    difficulty_actions = [d.action.value for d in delta.decisions
                          if d.action.value in ("lower_difficulty", "raise_difficulty")]
    assert difficulty_actions == ["lower_difficulty"]  # declared first at equal priority
    assert any("already decided" in n for n in delta.notes)


def test_new_student_is_deterministic():
    profile = StudentProfile()
    a = StudentModel().personalize(_plan(), profile).model_dump_json()
    b = StudentModel().personalize(_plan(), profile).model_dump_json()
    assert a == b


def test_source_plan_never_mutated():
    plan = _plan()
    before = plan.model_dump_json()
    StudentModel().personalize(plan, StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}, prerequisite_gaps=["c0"])))
    assert plan.model_dump_json() == before


def test_every_decision_records_rule_name_and_priority():
    profile = StudentProfile(state=StudentState(prerequisite_gaps=["c0"]))
    delta = StudentModel().personalize(_plan(), profile)
    assert delta.decisions
    for d in delta.decisions:
        assert d.rule_name and isinstance(d.priority, int)
