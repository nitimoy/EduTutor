"""Storage interface for Learning Sessions."""

from __future__ import annotations

import threading
from typing import Protocol

from backend.session.models import LearningSession


class SessionStore(Protocol):
    """Protocol for persisting and retrieving learning sessions."""

    def get(self, session_id: str) -> LearningSession | None:
        """Retrieve a session by ID."""
        ...

    def save(self, session: LearningSession) -> None:
        """Save a session."""
        ...

    def delete(self, session_id: str) -> None:
        """Delete a session by ID."""
        ...

    def list_sessions(self) -> list[dict[str, str]]:
        """List all sessions, returning lightweight metadata."""
        ...


class InMemorySessionStore:
    """A lightweight, thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._store: dict[str, LearningSession] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> LearningSession | None:
        with self._lock:
            session = self._store.get(session_id)
            if session:
                return session.model_copy(deep=True)
            return None

    def save(self, session: LearningSession) -> None:
        with self._lock:
            self._store[session.session_id] = session.model_copy(deep=True)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._store.pop(session_id, None)

    def list_sessions(self) -> list[dict[str, str]]:
        with self._lock:
            sessions = []
            for s_id, session in self._store.items():
                title = "New Session"
                if session.history:
                    title = session.history[0].user_query[:50]
                sessions.append({
                    "session_id": s_id,
                    "title": title,
                    "updated_at": session.last_updated if hasattr(session, 'last_updated') else "",
                })
            return sessions


import sqlite3
import json

class SQLiteSessionStore:
    """A SQLite-backed session store."""

    def __init__(self, db_path: str = "sessions.db") -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def get(self, session_id: str) -> LearningSession | None:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM sessions WHERE session_id = ?", 
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return LearningSession.model_validate_json(row[0])
            return None

    def save(self, session: LearningSession) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, data, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET 
                data=excluded.data, updated_at=CURRENT_TIMESTAMP
                """,
                (session.session_id, session.model_dump_json())
            )

    def delete(self, session_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def list_sessions(self) -> list[dict[str, str]]:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("SELECT session_id, data, updated_at FROM sessions ORDER BY updated_at DESC")
            sessions = []
            for row in cursor.fetchall():
                session_id, data_str, updated_at = row
                try:
                    data = json.loads(data_str)
                    history = data.get("history", [])
                    # Skip sessions with no messages
                    if not history:
                        continue
                    title = history[0].get("user_query", "New Session")[:50]
                    sessions.append({
                        "session_id": session_id,
                        "title": title,
                        "updated_at": updated_at,
                        "turn_count": len(history),
                    })
                except Exception:
                    continue
            return sessions

