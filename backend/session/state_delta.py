"""The canonical state-update IR (``StudentStateDelta``) and its applier.

Mirrors Phase 5.0's ``TeachingPlanDelta`` / ``TeachingPlanApplier``: the session engine
produces an **immutable** delta (the source of truth for a progression), and a dedicated
:class:`StudentStateApplier` turns ``(before_state, delta)`` into a new ``StudentState``.
The delta is pure data; all execution logic lives in the applier. The frozen Phase-5.0
``StudentState`` schema and ``transition`` state machine are reused, never modified.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.session.event_rules import MASTERED_FLOOR
from backend.student.learning_state import LearningSignal, LearningState, transition
from backend.student.models import StudentState


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class ConceptChange(BaseModel):
    """The accumulated change for one concept across a session.

    Deltas are summed in event order; ``signals`` preserves the ordered signals so the
    frozen ``transition`` machine is replayed faithfully.
    """

    concept_id: str
    mastery_delta: float = 0.0
    confidence_delta: float = 0.0
    signals: tuple[LearningSignal, ...] = ()
    force_mastered: bool = False
    revision_bump: int = 0


class StudentStateDelta(BaseModel):
    """Immutable, canonical description of a session's effect on the student state."""

    model_config = ConfigDict(frozen=True)

    concept_changes: tuple[ConceptChange, ...] = ()
    streak_delta: int = 0
    provenance: str = ""  # session id


class StudentStateApplier:
    """Apply a :class:`StudentStateDelta` to a ``StudentState`` (mirrors TeachingPlanApplier)."""

    def apply(self, before: StudentState, delta: StudentStateDelta) -> StudentState:
        """Return a new ``StudentState`` = ``before`` + ``delta``. ``before`` is never mutated."""
        state = before.model_copy(deep=True)

        for change in delta.concept_changes:
            cid = change.concept_id

            # Mastery / confidence, clamped to [0, 1].
            if change.mastery_delta:
                state.concept_mastery[cid] = _clamp(
                    state.concept_mastery.get(cid, 0.0) + change.mastery_delta)
            if change.confidence_delta:
                state.concept_confidence[cid] = _clamp(
                    state.concept_confidence.get(cid, 0.0) + change.confidence_delta)

            # Replay signals through the frozen state machine.
            current = state.concept_states.get(cid) or state.state_of(cid)
            for signal in change.signals:
                current, _reason = transition(current, signal)
            state.concept_states[cid] = current

            # Revision history (no scheduling).
            if change.revision_bump:
                state.revision_counts[cid] = (
                    state.revision_counts.get(cid, 0) + change.revision_bump)

            # Explicit mastery, or crossing the mastery floor, completes the concept.
            mastery = state.concept_mastery.get(cid, 0.0)
            if change.force_mastered:
                state.concept_mastery[cid] = _clamp(max(mastery, MASTERED_FLOOR))
                mastery = state.concept_mastery[cid]
            if change.force_mastered or mastery >= MASTERED_FLOOR:
                state.concept_states[cid] = LearningState.MASTERED
                if cid not in state.completed_concepts:
                    state.completed_concepts.append(cid)
                if cid in state.prerequisite_gaps:
                    state.prerequisite_gaps.remove(cid)

        if delta.streak_delta:
            state.learning_streak = state.learning_streak + delta.streak_delta

        return state
