"""The derived session report.

``SessionSummary`` is **strictly derived** from ``(before, after, session)`` — it is never
a source of truth (that is the immutable event log + ``StudentStateDelta``) and is always
regenerable. Structured data only, no natural language, and — by design — **no
"suggested next concepts"**: deciding what to teach next is the Tutor Brain / Student
Model's job on the next query, not the progression engine's.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.session.events import EventType, SessionEventLog
from backend.student.learning_state import LearningState
from backend.student.models import StudentState


class ConceptDelta(BaseModel):
    """Per-concept before/after view for auditability."""

    concept_id: str
    mastery_before: float
    mastery_after: float
    confidence_before: float
    confidence_after: float
    state_before: LearningState
    state_after: LearningState


class SessionSummary(BaseModel):
    """A structured, deterministic report of one session's outcome."""

    session_id: str
    concepts_studied: list[str] = Field(default_factory=list)
    concepts_mastered: list[str] = Field(default_factory=list)
    concepts_needing_review: list[str] = Field(default_factory=list)
    exercises_attempted: int = 0
    exercises_solved: int = 0
    exercises_failed: int = 0
    proofs_completed: int = 0
    proofs_skipped: int = 0
    reviews_completed: int = 0
    per_concept: dict[str, ConceptDelta] = Field(default_factory=dict)


_REVIEW_STATES = {LearningState.FORGOTTEN, LearningState.NEEDS_REVIEW}


def build_summary(
    before: StudentState, after: StudentState, session: SessionEventLog
) -> SessionSummary:
    """Derive the session summary. Deterministic; no information beyond its inputs."""
    studied = session.concepts()

    # Exercise / proof / review counters from the event multiset.
    counts: dict[EventType, int] = {}
    for event in session.events:
        counts[event.type] = counts.get(event.type, 0) + 1
    solved = counts.get(EventType.EXERCISE_CORRECT, 0)
    failed = counts.get(EventType.EXERCISE_INCORRECT, 0)
    # "attempted" counts explicit attempts plus every graded exercise.
    attempted = counts.get(EventType.EXERCISE_ATTEMPTED, 0) + solved + failed

    mastered = [
        cid for cid in studied
        if after.state_of(cid) == LearningState.MASTERED
        and before.state_of(cid) != LearningState.MASTERED
    ]
    needing_review = [cid for cid in studied if after.state_of(cid) in _REVIEW_STATES]

    per_concept = {
        cid: ConceptDelta(
            concept_id=cid,
            mastery_before=before.mastery_of(cid), mastery_after=after.mastery_of(cid),
            confidence_before=before.confidence_of(cid),
            confidence_after=after.confidence_of(cid),
            state_before=before.state_of(cid), state_after=after.state_of(cid),
        )
        for cid in studied
    }

    return SessionSummary(
        session_id=session.session_id,
        concepts_studied=studied,
        concepts_mastered=mastered,
        concepts_needing_review=needing_review,
        exercises_attempted=attempted,
        exercises_solved=solved,
        exercises_failed=failed,
        proofs_completed=counts.get(EventType.PROOF_COMPLETED, 0),
        proofs_skipped=counts.get(EventType.PROOF_SKIPPED, 0),
        reviews_completed=counts.get(EventType.REVIEW_COMPLETED, 0),
        per_concept=per_concept,
    )
