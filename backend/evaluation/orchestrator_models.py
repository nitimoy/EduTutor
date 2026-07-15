"""Pydantic models for the orchestrator evaluation framework."""

from __future__ import annotations

from pydantic import BaseModel


class OrchestratorEvalReport(BaseModel):
    deterministic: bool = False
    stage_ordering: bool = False
    metadata_propagation: bool = False
    verify_fail_handling: bool = False
    citation_preservation: bool = False
    config_propagation: bool = False
    no_mutation: bool = False
    all_passed: bool = False
