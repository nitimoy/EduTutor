"""Pydantic models for the Student Model evaluation framework (architectural correctness)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.student.models import StudentProfile


class StudentPersonalizationCase(BaseModel):
    """A profile run against the reference plan, with expected structural outcomes."""

    name: str
    profile: StudentProfile
    expected_actions: list[str] = Field(default_factory=list)      # ⊆ produced actions
    expected_suppressed: list[str] = Field(default_factory=list)   # section kinds removed
    expected_front: list[str] = Field(default_factory=list)        # applied plan's leading kinds


class StateTransitionCase(BaseModel):
    """One expected state-machine transition."""

    from_state: str
    signal: str
    to_state: str


class CaseResult(BaseModel):
    name: str
    deterministic: bool = True
    decision_ok: bool = True
    priority_ordered: bool = True
    invariants_ok: bool = True
    produced_actions: list[str] = Field(default_factory=list)


class StudentEvalReport(BaseModel):
    n_cases: int = 0
    determinism_rate: float = 0.0
    decision_correctness_rate: float = 0.0
    priority_ordering_rate: float = 0.0
    invariant_pass_rate: float = 0.0
    n_transition_cases: int = 0
    transition_correctness_rate: float = 0.0
    all_passed: bool = False
    case_results: list[CaseResult] = Field(default_factory=list)
