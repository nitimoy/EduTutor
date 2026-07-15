"""API route for selecting v1 or v2 engine with session management."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["version"])

# Lazy-loaded v2 engine
_v2_engine = None


def get_v2_engine():
    """Get or create the v2 RAG engine using same config as v1."""
    global _v2_engine
    if _v2_engine is None:
        from backend.v2.rag.engine import RAGEngine
        from backend.api.config import ServiceConfig
        config = ServiceConfig()
        _v2_engine = RAGEngine(
            compiled_dir=str(config.compiled_dir or "data/compiled"),
            qdrant_path="data/v2/qdrant_full",
            llm_model=config.model_id,
            api_key=config.api_key,
        )
        _v2_engine.build_index()
    return _v2_engine


class VersionInfo(BaseModel):
    version: str
    active: bool


class SetVersionRequest(BaseModel):
    version: str  # "v1" or "v2"


class V2QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    subject: Optional[str] = None


class V2SessionRequest(BaseModel):
    student_id: str = "anonymous"


@router.get("/version")
def get_version(request: Request) -> dict:
    """Get the currently active engine version."""
    version = getattr(request.app.state, "engine_version", "v1")
    return {
        "version": version,
        "available": ["v1", "v2"],
    }


@router.post("/version")
def set_version(request: Request, body: SetVersionRequest) -> dict:
    """Switch between v1 and v2 engines."""
    if body.version not in ["v1", "v2"]:
        return {"error": "Invalid version. Must be 'v1' or 'v2'"}

    request.app.state.engine_version = body.version
    return {
        "version": body.version,
        "message": f"Switched to {body.version}",
    }


@router.post("/version/session/start")
def start_v2_session(body: V2SessionRequest) -> dict:
    """Create a new v2 session."""
    try:
        engine = get_v2_engine()
        session = engine._session_manager.create_session(body.student_id)
        return {
            "session_id": session.session_id,
            "student_id": session.student_id,
            "created_at": session.created_at,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/version/session/{session_id}")
def get_v2_session(session_id: str) -> dict:
    """Get a v2 session with full turn history."""
    try:
        engine = get_v2_engine()
        session = engine._session_manager.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        return {
            "session_id": session.session_id,
            "student_id": session.student_id,
            "turns": [
                {
                    "query": turn.query,
                    "answer": turn.answer,
                    "sources": turn.sources,
                    "citations": turn.citations,
                    "timestamp": turn.timestamp,
                }
                for turn in session.turns
            ],
            "active_concept": session.active_concept,
            "active_subject": session.active_subject,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
    except Exception as e:
        return {"error": str(e)}



@router.delete("/version/session/{session_id}")
def delete_v2_session(session_id: str) -> dict:
    """Delete a v2 session."""
    try:
        engine = get_v2_engine()
        deleted = engine._session_manager.delete_session(session_id)
        if deleted:
            return {"message": "Session deleted", "session_id": session_id}
        return {"error": "Session not found"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/version/sessions")
def list_v2_sessions(student_id: str = "anonymous") -> list:
    """List all v2 sessions for a given student directly from SQLite.
    Uses a lightweight SessionManager — does NOT require the full RAG engine."""
    try:
        from backend.v2.core.session_manager import SessionManager
        manager = SessionManager(db_path="data/sessions.db")
        return manager.list_sessions(student_id=student_id)
    except Exception as e:
        return []




@router.get("/version/session/{session_id}/history")
def get_v2_history(session_id: str) -> dict:
    """Get conversation history for a v2 session."""
    try:
        engine = get_v2_engine()
        session = engine._session_manager.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        return {
            "session_id": session.session_id,
            "turns": [
                {
                    "query": turn.query,
                    "answer": turn.answer[:200],
                    "timestamp": turn.timestamp,
                }
                for turn in session.turns
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/version/query")
def query_v2(body: V2QueryRequest) -> dict:
    """Query using v2 RAG engine with session context."""
    try:
        engine = get_v2_engine()
        response = engine.query(
            question=body.query,
            session_id=body.session_id,
            subject_filter=body.subject,
        )
        return {
            "answer": response["answer"],
            "sources": response["sources"],
            "citations": response.get("citations", []),
            "query": response["query"],
            "session_id": response.get("session_id"),
            "grounded": response.get("grounded", False),
            "verification": response.get("verification", {}),
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/version/query/stream")
async def query_v2_stream(body: V2QueryRequest):
    """Query using v2 RAG engine with real streaming response."""
    import json

    def event_generator():
        try:
            engine = get_v2_engine()

            # Use the streaming generator — yields tokens as LLM produces them
            for event in engine.query_stream(
                question=body.query,
                session_id=body.session_id,
                subject_filter=body.subject,
            ):
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
