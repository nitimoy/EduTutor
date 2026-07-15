"""The Learning Session Engine.

Folds an ordered :class:`SessionEventLog` into a **canonical** :class:`StudentStateDelta`
(the source-of-truth update), then applies it to derive the after-state and a derived
:class:`SessionSummary`. Deterministic and replayable: the same ``(before, session)`` always
yields byte-identical outputs, and applying the delta to ``before`` reproduces the exact
after-state. No LLM, no scheduling, no probability.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.session.event_rules import effect_for
from backend.session.events import SessionEventLog
from backend.session.state_delta import (
    ConceptChange,
    StudentStateApplier,
    StudentStateDelta,
)
from backend.session.summary import SessionSummary, build_summary
from backend.student.learning_state import LearningSignal
from backend.student.models import StudentState


class SessionResult(BaseModel):
    """Engine output. ``delta`` is canonical; ``after`` and ``summary`` are derived from it."""

    model_config = ConfigDict(frozen=True)

    delta: StudentStateDelta
    after: StudentState
    summary: SessionSummary


# Mutable per-concept accumulator used only while folding.
class _Acc:
    __slots__ = ("mastery_delta", "confidence_delta", "signals", "force_mastered", "revision_bump")

    def __init__(self) -> None:
        self.mastery_delta = 0.0
        self.confidence_delta = 0.0
        self.signals: list[LearningSignal] = []
        self.force_mastered = False
        self.revision_bump = 0


class LearningSessionEngine:
    """Turn a completed session into a deterministic state update + summary."""

    def __init__(self, applier: StudentStateApplier | None = None) -> None:
        self._applier = applier or StudentStateApplier()

    def build_delta(
        self, before: StudentState, session: SessionEventLog
    ) -> StudentStateDelta:
        """Pure fold of the ordered events into the canonical delta. ``before`` is read-only."""
        # First-touch order preserved for deterministic output.
        order: list[str] = []
        accs: dict[str, _Acc] = {}
        streak_delta = 0

        for event in session.events:
            effect = effect_for(event.type)
            streak_delta += effect.streak_delta

            cid = event.concept_id
            if cid is None:
                continue  # session-level only (e.g. streak)

            if cid not in accs:
                accs[cid] = _Acc()
                order.append(cid)
            acc = accs[cid]
            acc.mastery_delta += effect.mastery_delta
            acc.confidence_delta += effect.confidence_delta
            if effect.signal is not None:
                acc.signals.append(effect.signal)
            acc.force_mastered = acc.force_mastered or effect.force_mastered
            acc.revision_bump += effect.revision_bump

        changes = tuple(
            ConceptChange(
                concept_id=cid,
                mastery_delta=round(accs[cid].mastery_delta, 6),
                confidence_delta=round(accs[cid].confidence_delta, 6),
                signals=tuple(accs[cid].signals),
                force_mastered=accs[cid].force_mastered,
                revision_bump=accs[cid].revision_bump,
            )
            for cid in order
        )
        return StudentStateDelta(
            concept_changes=changes, streak_delta=streak_delta,
            provenance=session.session_id,
        )

    def process(self, before: StudentState, session: SessionEventLog) -> SessionResult:
        """Build the canonical delta, apply it, and derive the summary."""
        delta = self.build_delta(before, session)
        after = self._applier.apply(before, delta)
        summary = build_summary(before, after, session)
        return SessionResult(delta=delta, after=after, summary=summary)
