"""Pydantic models for the Learning Session Engine evaluation framework."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.session.events import SessionEventLog
from backend.student.models import StudentState


class SessionCase(BaseModel):
    """A before-state + session run, with expected structural outcomes."""

    name: str
    before: StudentState = Field(default_factory=StudentState)
    session: SessionEventLog
    expected_mastered: list[str] = Field(default_factory=list)
    expected_needing_review: list[str] = Field(default_factory=list)
    expected_streak_delta: int = 0


class TransitionCase(BaseModel):
    """A single (before learning-state, event type, expected after learning-state)."""

    concept_id: str = "c1"
    from_state: str
    event_type: str
    to_state: str


class CaseResult(BaseModel):
    name: str
    deterministic: bool = True
    replay_ok: bool = True          # apply(before, delta) == after
    canonical_delta_ok: bool = True  # summary regenerable from (before, delta, session)
    outcome_ok: bool = True          # expected mastered/review/streak matched
    invariants_ok: bool = True       # clamped ranges, before unchanged, counts consistent


class SessionEvalReport(BaseModel):
    n_cases: int = 0
    determinism_rate: float = 0.0
    replay_rate: float = 0.0
    canonical_delta_rate: float = 0.0
    outcome_rate: float = 0.0
    invariant_rate: float = 0.0
    n_transition_cases: int = 0
    transition_correctness_rate: float = 0.0
    all_passed: bool = False
    case_results: list[CaseResult] = Field(default_factory=list)
