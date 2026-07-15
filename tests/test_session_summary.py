"""Tests for the derived SessionSummary."""

from backend.session.engine import LearningSessionEngine
from backend.session.events import EventType, LearningEvent, SessionEventLog
from backend.session.state_delta import StudentStateApplier
from backend.session.summary import SessionSummary, build_summary
from backend.student.learning_state import LearningState
from backend.student.models import StudentState


def _ev(t, c=None):
    return LearningEvent(type=t, concept_id=c)


def _session():
    return SessionEventLog(session_id="sum", events=[
        _ev(EventType.LESSON_STARTED, "c1"),
        _ev(EventType.EXERCISE_ATTEMPTED, "c1"),
        _ev(EventType.EXERCISE_CORRECT, "c1"),
        _ev(EventType.EXERCISE_INCORRECT, "c1"),
        _ev(EventType.CONCEPT_MASTERED, "c1"),
        _ev(EventType.PROOF_COMPLETED, "c2"),
        _ev(EventType.PROOF_SKIPPED, "c2"),
        _ev(EventType.REVIEW_COMPLETED, "c2"),
    ])


def _result():
    before = StudentState()
    return before, LearningSessionEngine().process(before, _session())


def test_studied_and_mastered():
    _, res = _result()
    assert res.summary.concepts_studied == ["c1", "c2"]
    assert "c1" in res.summary.concepts_mastered


def test_exercise_counts():
    _, res = _result()
    s = res.summary
    assert s.exercises_solved == 1 and s.exercises_failed == 1
    # attempted = explicit attempts (1) + graded (2)
    assert s.exercises_attempted == 3


def test_proof_and_review_counts():
    _, res = _result()
    s = res.summary
    assert s.proofs_completed == 1 and s.proofs_skipped == 1 and s.reviews_completed == 1


def test_needing_review_reflects_after_state():
    before = StudentState(concept_states={"c1": LearningState.FORGOTTEN})
    session = SessionEventLog(session_id="r", events=[
        _ev(EventType.REVIEW_COMPLETED, "c1")])  # forgotten + review -> needs_review
    res = LearningSessionEngine().process(before, session)
    assert "c1" in res.summary.concepts_needing_review


def test_per_concept_deltas_present():
    _, res = _result()
    pc = res.summary.per_concept["c1"]
    assert pc.mastery_after >= pc.mastery_before
    assert pc.state_after == LearningState.MASTERED


def test_summary_is_regenerable_from_before_delta_session():
    before, res = _result()
    replayed = StudentStateApplier().apply(before, res.delta)
    regenerated = build_summary(before, replayed, _session())
    assert regenerated.model_dump_json() == res.summary.model_dump_json()


def test_summary_has_no_suggested_next_field():
    # Deciding what to teach next is out of scope for the progression engine.
    assert "suggested_next_concepts" not in SessionSummary.model_fields
