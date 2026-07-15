"""Deterministic per-event effects.

Each :class:`EventType` maps to a fixed :class:`EventEffect`: a mastery delta, a
confidence delta, an optional :class:`LearningSignal` for the frozen state machine, and
flags for completion / revision / streak. All magnitudes are module constants (one place
to tune), so every state update is a fixed, explainable transform — no probability, no ML.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.session.events import EventType
from backend.student.learning_state import LearningSignal

# Fixed update magnitudes (documented, tunable here only).
MASTERY_CORRECT = 0.2
MASTERY_INCORRECT = -0.1
MASTERY_PROOF = 0.15
MASTERY_REVIEW = 0.05
CONF_UP = 0.15
CONF_DOWN = -0.1
MASTERED_FLOOR = 0.8


@dataclass(frozen=True)
class EventEffect:
    """The deterministic effect of one event on a single concept (+ session streak)."""

    mastery_delta: float = 0.0
    confidence_delta: float = 0.0
    signal: LearningSignal | None = None
    force_mastered: bool = False
    revision_bump: int = 0
    streak_delta: int = 0


# The single source of truth mapping events to their effects.
_EFFECTS: dict[EventType, EventEffect] = {
    EventType.LESSON_STARTED: EventEffect(signal=LearningSignal.INTRODUCE),
    EventType.LESSON_COMPLETED: EventEffect(streak_delta=1),
    EventType.EXERCISE_ATTEMPTED: EventEffect(),  # counter only
    EventType.EXERCISE_CORRECT: EventEffect(
        mastery_delta=MASTERY_CORRECT, confidence_delta=CONF_UP,
        signal=LearningSignal.PRACTICE_SUCCESS),
    EventType.EXERCISE_INCORRECT: EventEffect(
        mastery_delta=MASTERY_INCORRECT, confidence_delta=CONF_DOWN,
        signal=LearningSignal.PRACTICE_FAILURE),
    EventType.PROOF_COMPLETED: EventEffect(
        mastery_delta=MASTERY_PROOF, confidence_delta=CONF_UP,
        signal=LearningSignal.PRACTICE_SUCCESS),
    EventType.PROOF_SKIPPED: EventEffect(),  # no state change
    EventType.REVIEW_COMPLETED: EventEffect(
        mastery_delta=MASTERY_REVIEW, signal=LearningSignal.REVIEW, revision_bump=1),
    EventType.CONCEPT_MASTERED: EventEffect(
        signal=LearningSignal.PRACTICE_SUCCESS, force_mastered=True),
}

# Convenience view: event -> signal (or None).
EVENT_SIGNAL: dict[EventType, LearningSignal | None] = {
    et: eff.signal for et, eff in _EFFECTS.items()
}


def effect_for(event_type: EventType) -> EventEffect:
    """Return the fixed effect for an event type."""
    return _EFFECTS[event_type]
