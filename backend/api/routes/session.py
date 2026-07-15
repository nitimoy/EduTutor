"""Learning session processing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_session_engine
from backend.api.schemas import SessionProcessRequest, SessionProcessResponse
from backend.session.engine import LearningSessionEngine

router = APIRouter(prefix="/api/v1", tags=["session"])


@router.post("/session/process", response_model=SessionProcessResponse)
def process_session(
    request: SessionProcessRequest,
    engine: LearningSessionEngine = Depends(get_session_engine),
) -> SessionProcessResponse:
    """Process a completed learning session.

    Folds the session events into a deterministic state delta, applies it to
    derive the after-state, and builds a structured summary.
    """
    result = engine.process(request.before, request.session)
    return SessionProcessResponse.from_engine_result(result)
