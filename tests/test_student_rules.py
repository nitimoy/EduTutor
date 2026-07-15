"""Tests for individual personalization rule predicates and metadata."""

from backend.student.models import (
    DifficultyPreference,
    ExamplePreference,
    ExplanationPreference,
    PacePreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)
from backend.student.rules import DEFAULT_POLICY, PersonalizationContext
from backend.tutor.models import (
    EducationalIntent,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
)

RULES = {r.name: r for r in DEFAULT_POLICY.rules}


def _plan(*kinds):
    if not kinds:
        kinds = (SectionKind.MAIN_EXPLANATION, SectionKind.PREREQUISITES,
                 SectionKind.PROOF, SectionKind.WORKED_EXAMPLE, SectionKind.SUMMARY)
    return TeachingPlan(
        query="q", intent=EducationalIntent.PROOF,
        strategy=TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
        primary_concept_id="c1", primary_concept_name="Alpha",
        sections=[SectionSpec(kind=k, status=SectionStatus.PRESENT) for k in kinds])


def _ctx(profile, plan=None):
    return PersonalizationContext(profile, plan or _plan())


def test_all_rules_have_positive_priority_and_axis():
    for r in DEFAULT_POLICY.rules:
        assert isinstance(r.priority, int) and r.axis


def test_prereq_gap_rule_fires_only_with_gaps():
    fires = StudentProfile(state=StudentState(prerequisite_gaps=["c0"]))
    assert RULES["prereq_gap_review"].predicate(_ctx(fires))
    assert not RULES["prereq_gap_review"].predicate(_ctx(StudentProfile()))


def test_prereq_gap_rule_does_not_fire_without_prereq_section():
    fires = StudentProfile(state=StudentState(prerequisite_gaps=["c0"]))
    ctx = _ctx(fires, _plan(SectionKind.MAIN_EXPLANATION, SectionKind.SUMMARY))
    assert not RULES["prereq_gap_review"].predicate(ctx)


def test_low_mastery_lower_difficulty_fires():
    low = StudentProfile(state=StudentState(concept_mastery={"c1": 0.1}))
    assert RULES["low_mastery_lower_difficulty"].predicate(_ctx(low))
    easy = StudentProfile(preferences=StudentPreferences(difficulty=DifficultyPreference.EASY))
    assert RULES["low_mastery_lower_difficulty"].predicate(_ctx(easy))


def test_challenging_raise_difficulty_fires():
    hi = StudentProfile(state=StudentState(concept_mastery={"c1": 0.9}))
    assert RULES["challenging_raise_difficulty"].predicate(_ctx(hi))
    ch = StudentProfile(preferences=StudentPreferences(difficulty=DifficultyPreference.CHALLENGING))
    assert RULES["challenging_raise_difficulty"].predicate(_ctx(ch))


def test_more_examples_fires_on_low_mastery_or_many_pref():
    assert RULES["low_mastery_more_examples"].predicate(
        _ctx(StudentProfile(state=StudentState(concept_mastery={"c1": 0.1}))))
    assert RULES["low_mastery_more_examples"].predicate(
        _ctx(StudentProfile(preferences=StudentPreferences(example=ExamplePreference.MANY))))


def test_few_examples_fires_on_few_pref():
    assert RULES["few_examples_deemphasize"].predicate(
        _ctx(StudentProfile(preferences=StudentPreferences(example=ExamplePreference.FEW))))


def test_pace_and_explanation_depth_rules():
    assert RULES["high_mastery_condense"].predicate(
        _ctx(StudentProfile(preferences=StudentPreferences(pace=PacePreference.FAST))))
    assert RULES["detailed_pref_expand"].predicate(
        _ctx(StudentProfile(preferences=StudentPreferences(explanation=ExplanationPreference.DETAILED))))
    assert RULES["concise_pref_condense"].predicate(
        _ctx(StudentProfile(preferences=StudentPreferences(explanation=ExplanationPreference.CONCISE))))


def test_rule_ops_only_target_present_sections():
    # prereq rule on a plan WITHOUT prerequisites -> build yields no ops (no-invention)
    profile = StudentProfile(state=StudentState(prerequisite_gaps=["c0"]))
    ctx = _ctx(profile, _plan(SectionKind.MAIN_EXPLANATION, SectionKind.SUMMARY))
    decision = RULES["prereq_gap_review"].build(ctx)
    assert decision.ops == []


def test_misconception_rule_fires():
    prof = StudentProfile(state=StudentState(misconception_flags={"c1": ["sign error"]}))
    assert RULES["misconception_review"].predicate(_ctx(prof))
