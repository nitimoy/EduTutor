"""Session lifecycle endpoints for stateful multi-turn tutoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_session_manager
from backend.orchestrator.models import TutorResponse
from backend.session.manager import SessionManager, SessionNotFoundError
from backend.session.models import LearningSession


class StartSessionRequest(BaseModel):
    student_id: str


class AskRequest(BaseModel):
    query: str


router = APIRouter(prefix="/api/v1", tags=["session_lifecycle"])


@router.post("/session/start", response_model=LearningSession)
def start_session(
    request: StartSessionRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> LearningSession:
    """Start a new stateful learning session."""
    return manager.start(student_id=request.student_id)


@router.post("/session/{session_id}/ask", response_model=TutorResponse)
def ask_question(
    session_id: str,
    request: AskRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> TutorResponse:
    """Ask a question within the context of an active session."""
    try:
        return manager.ask(session_id, request.query)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

import asyncio
import json
from fastapi.responses import StreamingResponse

@router.post("/session/{session_id}/ask/stream")
async def ask_question_stream(
    session_id: str,
    request: AskRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    """Ask a question and stream the response via SSE."""
    try:
        # We need to make sure the session exists first
        session = manager._store.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found.")

        # Currently the engine is synchronous, so we run it in a threadpool to not block
        response = await asyncio.to_thread(manager.ask, session_id, request.query)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine error: {str(e)}")

    async def event_generator():
        try:
            text = response.rendered_response.text
            chunk_size = max(1, len(text) // 10)

            # Send text chunks
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                yield f"event: text\ndata: {json.dumps({'text': chunk})}\n\n"
                await asyncio.sleep(0.05)

            # After generation, fetch the updated session from the store
            updated_session = manager._store.get(session_id)
            if updated_session:
                try:
                    session_json = updated_session.model_dump_json()
                    yield f"event: complete\ndata: {{\"session\": {session_json}}}\n\n"
                except Exception:
                    # If serialization fails, send completion without session data
                    yield f"event: complete\ndata: {{}}\n\n"
        except Exception:
            # Generator error - send error event
            yield f"event: error\ndata: {json.dumps({'error': 'Stream interrupted'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@router.get("/session/{session_id}", response_model=LearningSession)
def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> LearningSession:
    """Retrieve the state and history of an active session."""
    try:
        return manager.get(session_id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/session", response_model=list[dict])
def list_sessions(
    manager: SessionManager = Depends(get_session_manager),
) -> list[dict]:
    """List all stateful sessions."""
    return manager.list_sessions()


@router.delete("/session/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> None:
    """Delete an active session."""
    manager.delete(session_id)
