"""Tests for deterministic replay of the Learning Session Engine."""

from backend.session.engine import LearningSessionEngine
from backend.session.events import EventType, LearningEvent, SessionEventLog
from backend.session.state_delta import StudentStateApplier
from backend.student.models import StudentState


def _ev(t, c=None):
    return LearningEvent(type=t, concept_id=c)


def _session():
    return SessionEventLog(session_id="replay", events=[
        _ev(EventType.LESSON_STARTED, "c1"),
        _ev(EventType.EXERCISE_ATTEMPTED, "c1"),
        _ev(EventType.EXERCISE_CORRECT, "c1"),
        _ev(EventType.EXERCISE_INCORRECT, "c1"),
        _ev(EventType.EXERCISE_CORRECT, "c1"),
        _ev(EventType.CONCEPT_MASTERED, "c1"),
        _ev(EventType.LESSON_COMPLETED),
    ])


def test_process_is_deterministic():
    before = StudentState(prerequisite_gaps=["c1"])
    a = LearningSessionEngine().process(before, _session()).model_dump_json()
    b = LearningSessionEngine().process(before, _session()).model_dump_json()
    assert a == b


def test_apply_delta_reproduces_after_state():
    before = StudentState(prerequisite_gaps=["c1"])
    result = LearningSessionEngine().process(before, _session())
    replayed = StudentStateApplier().apply(before, result.delta)
    assert replayed.model_dump_json() == result.after.model_dump_json()


def test_rebuilding_delta_is_identical():
    before = StudentState()
    engine = LearningSessionEngine()
    d1 = engine.build_delta(before, _session()).model_dump_json()
    d2 = engine.build_delta(before, _session()).model_dump_json()
    assert d1 == d2


def test_event_order_matters():
    before = StudentState(concept_mastery={"c1": 0.5})
    engine = LearningSessionEngine()
    forward = SessionEventLog(session_id="s", events=[
        _ev(EventType.EXERCISE_CORRECT, "c1"), _ev(EventType.EXERCISE_INCORRECT, "c1")])
    # Same multiset, different order — deltas sum commutatively for mastery, but the
    # replayed state signal order differs; assert the engine respects order in signals.
    reverse = SessionEventLog(session_id="s", events=list(reversed(forward.events)))
    df = engine.build_delta(before, forward).concept_changes[0]
    dr = engine.build_delta(before, reverse).concept_changes[0]
    assert df.signals != dr.signals  # order preserved in the signal sequence


def test_initial_state_never_mutated_by_process():
    before = StudentState(concept_mastery={"c1": 0.5}, prerequisite_gaps=["c1"])
    snapshot = before.model_dump_json()
    LearningSessionEngine().process(before, _session())
    assert before.model_dump_json() == snapshot
