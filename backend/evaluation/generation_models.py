"""Pydantic models for the Language Generation evaluation framework."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.tutor.models import TutorPlan


class GenerationCase(BaseModel):
    """A TutorPlan to render + expected structural facts."""

    name: str
    tutor_plan: TutorPlan
    expected_unit_kinds: list[str] = Field(default_factory=list)  # in order


class CaseResult(BaseModel):
    name: str
    prompt_deterministic: bool = True
    order_preserved: bool = True
    unit_ids_stable: bool = True
    no_added_concepts: bool = True
    citations_preserved: bool = True
    grounded: bool = True
    response_deterministic: bool = True


class GenerationEvalReport(BaseModel):
    n_cases: int = 0
    prompt_determinism_rate: float = 0.0
    order_preserved_rate: float = 0.0
    unit_id_stability_rate: float = 0.0
    no_added_concepts_rate: float = 0.0
    citation_preservation_rate: float = 0.0
    grounding_rate: float = 0.0
    response_determinism_rate: float = 0.0
    template_purity_ok: bool = False
    adapter_equivalence_ok: bool = False
    all_passed: bool = False
    case_results: list[CaseResult] = Field(default_factory=list)
