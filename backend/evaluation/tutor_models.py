"""Pydantic models for the Tutor Brain evaluation framework."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TutorCase(BaseModel):
    """One labeled evaluation case. Expected labels are optional per dimension."""

    query: str
    expected_intent: Optional[str] = None
    expected_strategy: Optional[str] = None
    expected_primary_concept_name: Optional[str] = None


class TutorEvalDataset(BaseModel):
    version: str
    subject: str
    book: str
    cases: list[TutorCase] = Field(default_factory=list)


class CaseResult(BaseModel):
    """Per-case outcome recorded by the engine."""

    query: str
    intent: str
    expected_intent: Optional[str] = None
    intent_ok: Optional[bool] = None
    strategy: str
    expected_strategy: Optional[str] = None
    strategy_ok: Optional[bool] = None
    primary_concept_name: str = ""
    expected_primary_concept_name: Optional[str] = None
    primary_ok: Optional[bool] = None
    n_references: int = 0
    invalid_references: int = 0
    deterministic: bool = True


class TutorEvalReport(BaseModel):
    """Aggregate deterministic metrics for a dataset."""

    dataset_version: str
    subject: str
    n_cases: int = 0
    intent_accuracy: float = 0.0
    strategy_accuracy: float = 0.0
    primary_accuracy: float = 0.0
    citation_validity: float = 0.0  # fraction of references whose concept id ∈ index
    no_hallucination_rate: float = 0.0  # fraction of cases with zero invalid references
    deterministic: bool = True  # every case byte-identical across two runs
    case_results: list[CaseResult] = Field(default_factory=list)
