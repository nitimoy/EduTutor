"""Session manager for v2 with SQLite persistence.

Robust session management inspired by chatbot-ui's Supabase pattern:
- Sessions are created when user navigates to chat (not on first message)
- Session IDs are server-generated (no client-side temp UUIDs)
- Sessions persist across refreshes
- Empty sessions are automatically cleaned up
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class SessionTurn(BaseModel):
    """A single turn in a conversation."""
    query: str
    answer: str
    sources: list[dict]
    citations: list[dict]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Session(BaseModel):
    """A conversation session."""
    session_id: str
    student_id: str
    turns: list[SessionTurn] = Field(default_factory=list)
    active_concept: Optional[str] = None
    active_subject: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionManager:
    """Manage sessions with SQLite persistence.

    Key design decisions:
    1. create_session() generates server-side UUIDs (no client temp IDs)
    2. get_session() returns None if session doesn't exist (no auto-creation)
    3. add_turn() always saves to database
    4. list_sessions() filters out empty sessions
    5. cleanup_empty_sessions() removes stale sessions
    """

    def __init__(self, db_path: str = "data/sessions.db"):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS v2_sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def create_session(self, student_id: str = "anonymous") -> Session:
        """Create a new session with server-generated ID.

        This should be called when user navigates to chat, NOT on first message.
        """
        session = Session(
            session_id=str(uuid.uuid4()),
            student_id=student_id,
        )
        self._save_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID. Returns None if not found."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM v2_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return Session.model_validate_json(row[0])
        return None

    def add_turn(
        self,
        session_id: str,
        query: str,
        answer: str,
        sources: list[dict],
        citations: list[dict],
    ) -> Optional[Session]:
        """Add a turn to the session and save."""
        session = self.get_session(session_id)
        if not session:
            return None

        turn = SessionTurn(
            query=query,
            answer=answer,
            sources=sources,
            citations=citations,
        )
        session.turns.append(turn)
        session.updated_at = datetime.now(timezone.utc).isoformat()

        # Update active concept from sources
        if sources:
            session.active_concept = sources[0].get("concept_name", "")
            session.active_subject = sources[0].get("subject", "")

        self._save_session(session)
        return session

    def list_sessions(self, student_id: str = "anonymous") -> list[dict]:
        """List all sessions with at least 1 turn, matching v1 behavior."""
        sessions = []
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT session_id, data FROM v2_sessions ORDER BY updated_at DESC"
            )
            for row in cursor.fetchall():
                session = Session.model_validate_json(row[1])
                if len(session.turns) > 0:
                    title = session.turns[0].query[:50] if session.turns else "New Session"
                    sessions.append({
                        "session_id": session.session_id,
                        "title": title,
                        "updated_at": session.updated_at,
                        "turn_count": len(session.turns),
                        "active_concept": session.active_concept,
                    })
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM v2_sessions WHERE session_id = ?",
                (session_id,)
            )
            return cursor.rowcount > 0

    def cleanup_empty_sessions(self) -> int:
        """Delete all sessions with no turns. Returns count of deleted sessions."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT session_id, data FROM v2_sessions")
            deleted = 0
            for row in cursor.fetchall():
                session = Session.model_validate_json(row[1])
                if len(session.turns) == 0:
                    conn.execute(
                        "DELETE FROM v2_sessions WHERE session_id = ?",
                        (session.session_id,)
                    )
                    deleted += 1
            return deleted

    def _save_session(self, session: Session) -> None:
        """Save session to SQLite."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO v2_sessions (session_id, data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                data=excluded.data, updated_at=CURRENT_TIMESTAMP
                """,
                (session.session_id, session.model_dump_json())
            )

    def get_conversation_history(self, session_id: str, max_turns: int = 10) -> str:
        """Get formatted conversation history for context."""
        session = self.get_session(session_id)
        if not session or not session.turns:
            return ""

        history_parts = []
        for turn in session.turns[-max_turns:]:
            history_parts.append(f"Student: {turn.query}")
            history_parts.append(f"Tutor: {turn.answer[:200]}...")

        return "\n".join(history_parts)
