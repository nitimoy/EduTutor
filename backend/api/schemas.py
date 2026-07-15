"""Request/response schemas for the API layer.

Request schemas reuse frozen Pydantic models directly (``StudentProfile``,
``RetrievalContext``, ``LearningSession``, ``StudentState``) — no duplication.

Response schemas are **projections**: they flatten the deeply nested
``TutorResponse`` and ``SessionResult`` into clean, frontend-friendly JSON shapes.
Internal IRs (``TutorPlan``, ``VerificationReport``, ``ExecutionTrace``) are not
exposed — the API returns only what clients need.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.orchestrator.models import TutorResponse
from backend.retrieval.strategies.base import RetrievalContext
from backend.session.engine import SessionResult
from backend.session.events import SessionEventLog
from backend.session.state_delta import StudentStateDelta
from backend.session.summary import SessionSummary
from backend.student.models import StudentProfile, StudentState


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TutorAskRequest(BaseModel):
    """Request body for ``POST /api/v1/tutor/ask``."""

    query: str = Field(min_length=1, description="The student's question.")
    student_profile: StudentProfile = Field(
        default_factory=StudentProfile,
        description="Optional student profile for personalization.",
    )
    retrieval_context: Optional[RetrievalContext] = Field(
        default=None,
        description="Optional retrieval filters (subject, chapter, concept ids).",
    )


class SessionProcessRequest(BaseModel):
    """Request body for ``POST /api/v1/session/process``."""

    before: StudentState = Field(
        default_factory=StudentState,
        description="Student state before the session.",
    )
    session: SessionEventLog = Field(
        description="The learning session to process.",
    )


# ---------------------------------------------------------------------------
# Response sub-models (projections)
# ---------------------------------------------------------------------------

class CitationOut(BaseModel):
    """Projected citation for the API response."""

    concept_id: Optional[str]
    concept_name: str
    source_field: str
    locator: str
    object_type: Optional[str] = None


class RetrievalMetadataOut(BaseModel):
    """Projected retrieval metadata."""

    strategy_name: str
    top_k: int
    n_results: int
    result_concept_ids: list[str] = Field(default_factory=list)
    subject: Optional[str] = None
    chapter: Optional[str] = None


class ExecutionMetadataOut(BaseModel):
    """Projected execution metadata."""

    provider: str
    model_id: str
    style_preset: str
    intent: str
    teaching_strategy: str
    primary_concept_name: str = ""
    personalization_decisions: int = 0
    verification_passed: bool = True
    strict_verification: bool = False


class TimingOut(BaseModel):
    """Projected timing information."""

    total_ms: float = 0.0
    per_stage_ms: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level response schemas
# ---------------------------------------------------------------------------

class TutorAskResponse(BaseModel):
    """Response body for ``POST /api/v1/tutor/ask``.

    A flat, frontend-friendly projection of the internal ``TutorResponse``.
    """

    query: str
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    intent: str
    teaching_strategy: str
    primary_concept: str
    verification_passed: bool
    retrieval: RetrievalMetadataOut
    execution: ExecutionMetadataOut
    timing: TimingOut
    deterministic_fingerprint: str

    @classmethod
    def from_engine_response(cls, resp: TutorResponse) -> TutorAskResponse:
        """Project a frozen ``TutorResponse`` into the API response shape."""
        return cls(
            query=resp.query,
            answer=resp.rendered_response.text,
            citations=[
                CitationOut(
                    concept_id=c.concept_id,
                    concept_name=c.concept_name,
                    source_field=c.source_field,
                    locator=c.locator,
                    object_type=c.object_type,
                )
                for c in resp.citations
            ],
            intent=resp.execution_metadata.intent,
            teaching_strategy=resp.execution_metadata.teaching_strategy,
            primary_concept=resp.execution_metadata.primary_concept_name,
            verification_passed=resp.passed,
            retrieval=RetrievalMetadataOut(
                strategy_name=resp.retrieval_metadata.strategy_name,
                top_k=resp.retrieval_metadata.top_k,
                n_results=resp.retrieval_metadata.n_results,
                result_concept_ids=list(resp.retrieval_metadata.result_concept_ids),
                subject=resp.retrieval_metadata.subject,
                chapter=resp.retrieval_metadata.chapter,
            ),
            execution=ExecutionMetadataOut(
                provider=resp.execution_metadata.provider,
                model_id=resp.execution_metadata.model_id,
                style_preset=resp.execution_metadata.style_preset,
                intent=resp.execution_metadata.intent,
                teaching_strategy=resp.execution_metadata.teaching_strategy,
                primary_concept_name=resp.execution_metadata.primary_concept_name,
                personalization_decisions=resp.execution_metadata.personalization_decisions,
                verification_passed=resp.execution_metadata.verification_passed,
                strict_verification=resp.execution_metadata.strict_verification,
            ),
            timing=TimingOut(
                total_ms=resp.timing.total_ms,
                per_stage_ms=dict(resp.timing.per_stage_ms),
            ),
            deterministic_fingerprint=resp.deterministic_fingerprint(),
        )


class SessionProcessResponse(BaseModel):
    """Response body for ``POST /api/v1/session/process``."""

    delta: StudentStateDelta
    after: StudentState
    summary: SessionSummary

    @classmethod
    def from_engine_result(cls, result: SessionResult) -> SessionProcessResponse:
        """Project a frozen ``SessionResult`` into the API response shape."""
        return cls(
            delta=result.delta,
            after=result.after,
            summary=result.summary,
        )


# ---------------------------------------------------------------------------
# Legacy /chat compatibility
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single chat message."""

    role: str
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """Legacy ``/chat`` request — kept for backward compatibility."""

    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    """Legacy ``/chat`` response — kept for backward compatibility."""

    answer: str
    model: str

