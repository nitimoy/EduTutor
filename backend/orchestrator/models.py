"""Result IRs for the orchestrator — the single TutorResponse and its metadata."""

from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.generation.models import RenderedResponse
from backend.orchestrator.tracing import ExecutionTrace
from backend.student.models import TeachingPlanDelta
from backend.tutor.models import Citation, TutorPlan
from backend.verification.models import VerificationReport
from backend.evidence.models import EvidenceReport


class RetrievedConceptMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    concept_id: str
    name: str
    score: float
    breakdown: Optional[dict] = None


class RetrievalMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_name: str
    top_k: int
    n_results: int
    result_concept_ids: tuple[str, ...] = ()
    retrieved_concepts: list[RetrievedConceptMetadata] = Field(default_factory=list)
    subject: Optional[str] = None
    chapter: Optional[str] = None


class ExecutionMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model_id: str
    style_preset: str
    intent: str
    teaching_strategy: str
    primary_concept_name: str = ""
    personalization_decisions: int = 0
    verification_passed: bool = True
    strict_verification: bool = False


class TimingInfo(BaseModel):
    """Wall-clock timing — excluded from the determinism fingerprint."""

    model_config = ConfigDict(frozen=True)

    total_ms: float = 0.0
    per_stage_ms: dict[str, float] = Field(default_factory=dict)


class TutorResponse(BaseModel):
    """The single end-to-end result of the educational pipeline."""

    model_config = ConfigDict(frozen=True)

    query: str
    rendered_response: RenderedResponse
    tutor_plan: TutorPlan
    verification_report: VerificationReport
    personalization: TeachingPlanDelta
    citations: tuple[Citation, ...] = ()
    retrieval_metadata: RetrievalMetadata
    execution_metadata: ExecutionMetadata
    execution_trace: ExecutionTrace
    timing: TimingInfo
    passed: bool = True
    evidence_report: Optional[EvidenceReport] = None

    def deterministic_fingerprint(self) -> str:
        """Everything except wall-clock timing — identical inputs → identical fingerprint.

        Excludes ``timing`` and the trace's timing fields, but keeps the trace *structure*
        (stage names + statuses + order), which is deterministic.
        """
        payload = self.model_dump(mode="json", exclude={"timing", "execution_trace"})
        payload["trace_structure"] = list(self.execution_trace.structure())
        return json.dumps(payload, sort_keys=True)


class UnsupportedQueryResponse(TutorResponse):
    """Deterministic failure response when evidence is insufficient."""
    
    passed: bool = False
    reason: str = ""
    evidence_report: Optional[EvidenceReport] = None

