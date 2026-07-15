"""Tests for StudentStateDelta immutability and StudentStateApplier."""

import pytest
from pydantic import ValidationError

from backend.session.event_rules import MASTERED_FLOOR
from backend.session.state_delta import (
    ConceptChange,
    StudentStateApplier,
    StudentStateDelta,
)
from backend.student.learning_state import LearningSignal, LearningState
from backend.student.models import StudentState


def _delta(*changes, streak=0):
    return StudentStateDelta(concept_changes=tuple(changes), streak_delta=streak, provenance="s")


def test_delta_is_immutable():
    d = _delta()
    with pytest.raises((ValidationError, TypeError)):
        d.streak_delta = 5


def test_apply_adds_and_clamps_mastery():
    before = StudentState(concept_mastery={"c1": 0.95})
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", mastery_delta=0.2)))
    assert after.concept_mastery["c1"] == 1.0  # clamped


def test_apply_clamps_negative_mastery_to_zero():
    before = StudentState(concept_mastery={"c1": 0.05})
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", mastery_delta=-0.5)))
    assert after.concept_mastery["c1"] == 0.0


def test_apply_replays_signals_through_transition():
    before = StudentState(concept_states={"c1": LearningState.INTRODUCED})
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", signals=(LearningSignal.PRACTICE_SUCCESS,
                                                LearningSignal.PRACTICE_SUCCESS))))
    # introduced -> practicing -> mastered
    assert after.concept_states["c1"] == LearningState.MASTERED


def test_force_mastered_completes_and_clears_gap():
    before = StudentState(prerequisite_gaps=["c1"])
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", force_mastered=True)))
    assert after.concept_states["c1"] == LearningState.MASTERED
    assert after.mastery_of("c1") >= MASTERED_FLOOR
    assert "c1" in after.completed_concepts and "c1" not in after.prerequisite_gaps


def test_crossing_mastery_floor_auto_completes():
    before = StudentState(concept_mastery={"c1": 0.7}, prerequisite_gaps=["c1"])
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", mastery_delta=0.2)))  # 0.7 -> 0.9 >= floor
    assert "c1" in after.completed_concepts and "c1" not in after.prerequisite_gaps
    assert after.concept_states["c1"] == LearningState.MASTERED


def test_revision_bump_accumulates():
    before = StudentState(revision_counts={"c1": 2})
    after = StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", revision_bump=1)))
    assert after.revision_counts["c1"] == 3


def test_streak_delta_applied():
    after = StudentStateApplier().apply(StudentState(learning_streak=4), _delta(streak=2))
    assert after.learning_streak == 6


def test_before_is_never_mutated():
    before = StudentState(concept_mastery={"c1": 0.5}, prerequisite_gaps=["c1"])
    snapshot = before.model_dump_json()
    StudentStateApplier().apply(before, _delta(
        ConceptChange(concept_id="c1", mastery_delta=0.5, force_mastered=True)))
    assert before.model_dump_json() == snapshot


def test_apply_is_deterministic():
    before = StudentState()
    d = _delta(ConceptChange(concept_id="c1", mastery_delta=0.2,
                             signals=(LearningSignal.PRACTICE_SUCCESS,)))
    a = StudentStateApplier().apply(before, d).model_dump_json()
    b = StudentStateApplier().apply(before, d).model_dump_json()
    assert a == b
