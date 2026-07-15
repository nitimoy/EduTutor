"""Tests for the learning event vocabulary."""

from backend.session.events import EventType, LearningEvent, SessionEventLog


def test_event_defaults():
    e = LearningEvent(type=EventType.LESSON_STARTED)
    assert e.concept_id is None and e.detail == {}


def test_session_concepts_ordered_unique():
    s = SessionEventLog(session_id="s", events=[
        LearningEvent(type=EventType.LESSON_STARTED, concept_id="c1"),
        LearningEvent(type=EventType.EXERCISE_CORRECT, concept_id="c2"),
        LearningEvent(type=EventType.EXERCISE_CORRECT, concept_id="c1"),  # dup
        LearningEvent(type=EventType.LESSON_COMPLETED),  # no concept
    ])
    assert s.concepts() == ["c1", "c2"]


def test_empty_session_has_no_concepts():
    assert SessionEventLog(session_id="s", events=[]).concepts() == []


def test_all_event_types_present():
    names = {e.value for e in EventType}
    assert names == {
        "lesson_started", "lesson_completed", "exercise_attempted", "exercise_correct",
        "exercise_incorrect", "proof_completed", "proof_skipped", "review_completed",
        "concept_mastered",
    }


def test_session_serialization_roundtrip():
    s = SessionEventLog(session_id="s", events=[
        LearningEvent(type=EventType.EXERCISE_CORRECT, concept_id="c1", detail={"k": "v"})])
    assert SessionEventLog.model_validate_json(s.model_dump_json()) == s
