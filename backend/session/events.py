"""Learning event vocabulary for the deterministic session engine.

Events are the immutable, ordered record of what happened during one tutoring
interaction. They carry no timestamps — order is positional (list index), so replaying a
session is exact and independent of ``PYTHONHASHSEED``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """The deterministic events a tutoring interaction can emit."""

    LESSON_STARTED = "lesson_started"
    LESSON_COMPLETED = "lesson_completed"
    EXERCISE_ATTEMPTED = "exercise_attempted"
    EXERCISE_CORRECT = "exercise_correct"
    EXERCISE_INCORRECT = "exercise_incorrect"
    PROOF_COMPLETED = "proof_completed"
    PROOF_SKIPPED = "proof_skipped"
    REVIEW_COMPLETED = "review_completed"
    CONCEPT_MASTERED = "concept_mastered"


class LearningEvent(BaseModel):
    """A single event. ``concept_id`` is optional (e.g. a bare ``lesson_started``).

    ``detail`` is an opaque bag of string metadata for auditability — it never carries
    educational content and never influences state updates.
    """

    type: EventType
    concept_id: str | None = None
    detail: dict[str, str] = Field(default_factory=dict)


class SessionEventLog(BaseModel):
    """An ordered, immutable-in-spirit log of events for one interaction."""

    session_id: str
    events: list[LearningEvent] = Field(default_factory=list)

    def concepts(self) -> list[str]:
        """Ordered, de-duplicated concept ids touched by the session (first-seen order)."""
        seen: dict[str, None] = {}
        for event in self.events:
            if event.concept_id:
                seen.setdefault(event.concept_id, None)
        return list(seen)
