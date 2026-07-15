"""Chat session API endpoints.

Simple, clean API for session management:
- POST /api/v2/sessions — Create new session
- GET /api/v2/sessions — List all sessions
- GET /api/v2/sessions/{id} — Get session
- DELETE /api/v2/sessions/{id} — Delete session
- POST /api/v2/sessions/{id}/messages — Add message to session
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.v2.core.session_store import SessionStore, Message

router = APIRouter(prefix="/api/v2", tags=["sessions"])

# Global store instance
_store: Optional[SessionStore] = None


def get_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


# === Request/Response models ===

class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


class CreateSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str


class SessionResponse(BaseModel):
    id: str
    title: str
    messages: list[dict]
    created_at: str
    updated_at: str


class AddMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    sources: list[dict] = []
    citations: list[dict] = []


# === Endpoints ===

@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest):
    """Create a new chat session."""
    store = get_store()
    session = store.create(req.title)
    return CreateSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
    )


@router.get("/sessions")
def list_sessions():
    """List all sessions (only those with messages)."""
    store = get_store()
    return store.list()


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    """Get a session by ID."""
    store = get_store()
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        id=session.id,
        title=session.title,
        messages=[m.model_dump() for m in session.messages],
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a session."""
    store = get_store()
    deleted = store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


@router.post("/sessions/{session_id}/messages")
def add_message(session_id: str, req: AddMessageRequest):
    """Add a message to a session."""
    store = get_store()
    message = Message(
        role=req.role,
        content=req.content,
        sources=req.sources,
        citations=req.citations,
    )
    session = store.add_message(session_id, message)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Message added", "session_id": session_id}
