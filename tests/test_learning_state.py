"""Tests for the deterministic learning-state machine."""

import pytest

from backend.student.learning_state import (
    LearningSignal,
    LearningState,
    derive_state,
    transition,
)


@pytest.mark.parametrize("state,signal,expected", [
    (LearningState.UNSEEN, LearningSignal.INTRODUCE, LearningState.INTRODUCED),
    (LearningState.INTRODUCED, LearningSignal.PRACTICE_SUCCESS, LearningState.PRACTICING),
    (LearningState.PRACTICING, LearningSignal.PRACTICE_SUCCESS, LearningState.MASTERED),
    (LearningState.PRACTICING, LearningSignal.PRACTICE_FAILURE, LearningState.PRACTICING),
    (LearningState.MASTERED, LearningSignal.DECAY, LearningState.FORGOTTEN),
    (LearningState.FORGOTTEN, LearningSignal.REVIEW, LearningState.NEEDS_REVIEW),
    (LearningState.FORGOTTEN, LearningSignal.INTRODUCE, LearningState.INTRODUCED),
    (LearningState.NEEDS_REVIEW, LearningSignal.PRACTICE_SUCCESS, LearningState.MASTERED),
])
def test_transition_table(state, signal, expected):
    nxt, reason = transition(state, signal)
    assert nxt == expected and reason


def test_reset_from_any_state_returns_unseen():
    for s in LearningState:
        nxt, _ = transition(s, LearningSignal.RESET)
        assert nxt == LearningState.UNSEEN


def test_undefined_transition_leaves_state_unchanged():
    nxt, reason = transition(LearningState.UNSEEN, LearningSignal.DECAY)
    assert nxt == LearningState.UNSEEN and "unchanged" in reason


def test_transition_is_deterministic():
    outs = {transition(LearningState.PRACTICING, LearningSignal.PRACTICE_SUCCESS)[0]
            for _ in range(5)}
    assert outs == {LearningState.MASTERED}


def test_derive_state_thresholds():
    assert derive_state(0.0, seen=False, completed=False) == LearningState.UNSEEN
    assert derive_state(0.0, seen=True, completed=False) == LearningState.INTRODUCED
    assert derive_state(0.5, seen=True, completed=False) == LearningState.PRACTICING
    assert derive_state(0.9, seen=True, completed=True) == LearningState.MASTERED
    assert derive_state(0.9, seen=True, completed=False) == LearningState.MASTERED


def test_derive_state_needs_review_flag_wins():
    assert derive_state(0.9, seen=True, completed=True, needs_review=True) == LearningState.NEEDS_REVIEW
