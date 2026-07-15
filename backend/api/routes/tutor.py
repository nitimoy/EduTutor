"""Tutor ask endpoint — the primary educational API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_tutor_engine
from backend.api.schemas import TutorAskRequest, TutorAskResponse
from backend.orchestrator.engine import EducationalTutorEngine

router = APIRouter(prefix="/api/v1", tags=["tutor"])


@router.post("/tutor/ask", response_model=TutorAskResponse)
def ask(
    request: TutorAskRequest,
    engine: EducationalTutorEngine = Depends(get_tutor_engine),
) -> TutorAskResponse:
    """Ask the educational tutor a question.

    Runs the full deterministic pipeline: retrieval → planning → personalization →
    composition → generation → verification. Returns a flat, projected response.
    """
    response = engine.answer(
        request.query, request.student_profile, request.retrieval_context,
    )
    return TutorAskResponse.from_engine_response(response)
