"""Pydantic models for the Response Verification evaluation framework."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseResult(BaseModel):
    name: str
    verdict_ok: bool = True       # overall pass/fail matched expectation
    codes_ok: bool = True         # expected issue codes were raised
    deterministic: bool = True    # report byte-identical across two runs


class VerificationEvalReport(BaseModel):
    n_cases: int = 0
    verdict_accuracy: float = 0.0
    code_detection_rate: float = 0.0
    determinism_rate: float = 0.0
    all_passed: bool = False
    case_results: list[CaseResult] = Field(default_factory=list)
