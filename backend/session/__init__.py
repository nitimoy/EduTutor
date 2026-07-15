"""Learning Session Engine — deterministic learning progression (Phase 5.1).

Folds an ordered log of ``LearningEvent``s (a ``LearningSession``) into a canonical,
immutable ``StudentStateDelta``; ``StudentStateApplier`` turns that delta into a new
``StudentState``. A derived, structured ``SessionSummary`` reports the outcome. No LLM, no
scheduling, no ML — every update is a fixed, replayable transform.
"""

from backend.session.engine import LearningSessionEngine, SessionResult
from backend.session.event_rules import (
    CONF_DOWN,
    CONF_UP,
    MASTERED_FLOOR,
    MASTERY_CORRECT,
    MASTERY_INCORRECT,
    MASTERY_PROOF,
    MASTERY_REVIEW,
    EventEffect,
    effect_for,
)
from backend.session.events import EventType, LearningEvent, SessionEventLog
from backend.session.state_delta import (
    ConceptChange,
    StudentStateApplier,
    StudentStateDelta,
)
from backend.session.summary import ConceptDelta, SessionSummary, build_summary

__all__ = [
    "LearningSessionEngine",
    "SessionResult",
    "StudentStateApplier",
    # events
    "EventType",
    "LearningEvent",
    "SessionEventLog",
    # delta IR
    "StudentStateDelta",
    "ConceptChange",
    # summary
    "SessionSummary",
    "ConceptDelta",
    "build_summary",
    # effect table
    "EventEffect",
    "effect_for",
    "MASTERY_CORRECT",
    "MASTERY_INCORRECT",
    "MASTERY_PROOF",
    "MASTERY_REVIEW",
    "CONF_UP",
    "CONF_DOWN",
    "MASTERED_FLOOR",
]
