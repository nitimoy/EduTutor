"""Tests for the LearningSessionEngine fold → StudentStateDelta."""

from backend.session.engine import LearningSessionEngine
from backend.session.event_rules import (
    CONF_UP,
    MASTERY_CORRECT,
    MASTERY_PROOF,
    MASTERY_REVIEW,
)
from backend.session.events import EventType, LearningEvent, SessionEventLog
from backend.student.learning_state import LearningSignal
from backend.student.models import StudentState


def _session(*events):
    return SessionEventLog(session_id="s", events=list(events))


def _ev(t, c=None):
    return LearningEvent(type=t, concept_id=c)


def _change(delta, cid):
    return next(c for c in delta.concept_changes if c.concept_id == cid)


def test_correct_exercise_accumulates_mastery_and_confidence():
    delta = LearningSessionEngine().build_delta(
        StudentState(), _session(_ev(EventType.EXERCISE_CORRECT, "c1")))
    ch = _change(delta, "c1")
    assert ch.mastery_delta == MASTERY_CORRECT
    assert ch.confidence_delta == CONF_UP
    assert ch.signals == (LearningSignal.PRACTICE_SUCCESS,)


def test_deltas_sum_over_events_in_order():
    delta = LearningSessionEngine().build_delta(StudentState(), _session(
        _ev(EventType.EXERCISE_CORRECT, "c1"),
        _ev(EventType.PROOF_COMPLETED, "c1"),
    ))
    ch = _change(delta, "c1")
    assert round(ch.mastery_delta, 6) == round(MASTERY_CORRECT + MASTERY_PROOF, 6)
    assert ch.signals == (LearningSignal.PRACTICE_SUCCESS, LearningSignal.PRACTICE_SUCCESS)


def test_review_bumps_revision_and_small_mastery():
    delta = LearningSessionEngine().build_delta(
        StudentState(), _session(_ev(EventType.REVIEW_COMPLETED, "c1")))
    ch = _change(delta, "c1")
    assert ch.revision_bump == 1 and ch.mastery_delta == MASTERY_REVIEW
    assert ch.signals == (LearningSignal.REVIEW,)


def test_concept_mastered_sets_force_flag():
    delta = LearningSessionEngine().build_delta(
        StudentState(), _session(_ev(EventType.CONCEPT_MASTERED, "c1")))
    assert _change(delta, "c1").force_mastered is True


def test_lesson_completed_contributes_streak_only():
    delta = LearningSessionEngine().build_delta(
        StudentState(), _session(_ev(EventType.LESSON_COMPLETED)))
    assert delta.streak_delta == 1 and delta.concept_changes == ()


def test_neutral_events_have_no_effect():
    delta = LearningSessionEngine().build_delta(StudentState(), _session(
        _ev(EventType.EXERCISE_ATTEMPTED, "c1"),
        _ev(EventType.PROOF_SKIPPED, "c1"),
    ))
    ch = _change(delta, "c1")
    assert ch.mastery_delta == 0.0 and ch.confidence_delta == 0.0 and ch.signals == ()


def test_concept_change_order_is_first_touch():
    delta = LearningSessionEngine().build_delta(StudentState(), _session(
        _ev(EventType.EXERCISE_CORRECT, "c2"),
        _ev(EventType.EXERCISE_CORRECT, "c1"),
        _ev(EventType.EXERCISE_CORRECT, "c2"),
    ))
    assert [c.concept_id for c in delta.concept_changes] == ["c2", "c1"]


def test_provenance_is_session_id():
    delta = LearningSessionEngine().build_delta(
        StudentState(), SessionEventLog(session_id="abc", events=[]))
    assert delta.provenance == "abc"
