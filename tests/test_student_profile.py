"""Tests for StudentState / StudentPreferences / StudentProfile."""

from backend.student.learning_state import LearningState
from backend.student.models import (
    DifficultyPreference,
    ExamplePreference,
    ExplanationPreference,
    PacePreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)


def test_new_profile_defaults():
    p = StudentProfile()
    assert p.state.concept_mastery == {} and p.state.learning_streak == 0
    assert p.preferences.difficulty == DifficultyPreference.STANDARD
    assert p.preferences.explanation == ExplanationPreference.STANDARD
    assert p.preferences.example == ExamplePreference.STANDARD
    assert p.preferences.pace == PacePreference.STANDARD


def test_state_helpers_defaults():
    s = StudentState()
    assert s.mastery_of("c1") == 0.0
    assert s.mastery_of(None) == 0.0
    assert not s.is_completed("c1")
    assert not s.has_gap("c1")
    assert not s.has_misconception("c1")


def test_helpers_reflect_data():
    s = StudentState(concept_mastery={"c1": 0.7}, completed_concepts=["c1"],
                     prerequisite_gaps=["c0"], misconception_flags={"c1": ["swapped signs"]})
    assert s.mastery_of("c1") == 0.7
    assert s.is_completed("c1") and s.has_gap("c0") and s.has_misconception("c1")


def test_explicit_state_takes_precedence_over_derivation():
    s = StudentState(concept_states={"c1": LearningState.FORGOTTEN}, concept_mastery={"c1": 0.9})
    assert s.state_of("c1") == LearningState.FORGOTTEN


def test_state_derived_when_not_explicit():
    s = StudentState(concept_mastery={"c1": 0.9}, completed_concepts=["c1"])
    assert s.state_of("c1") == LearningState.MASTERED
    assert StudentState().state_of("c1") == LearningState.UNSEEN  # unseen


def test_profile_serialization_roundtrip():
    p = StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.5}),
        preferences=StudentPreferences(difficulty=DifficultyPreference.EASY))
    restored = StudentProfile.model_validate_json(p.model_dump_json())
    assert restored == p
