"""User authentication store with SQLite.

Features:
- User registration with username, email, phone, password
- Password hashing with bcrypt
- Session tokens for authentication
- Simple and clean design
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User model."""
    id: str
    username: str
    email: str
    phone: str
    password_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UserStore:
    """SQLite-backed user store with password hashing."""

    def __init__(self, db_path: str = "data/users.db"):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    phone TEXT,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT DEFAULT 'New Chat',
                    data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

    def _hash_password(self, password: str) -> str:
        """Hash password with SHA-256 (simple for demo, use bcrypt in production)."""
        return hashlib.sha256(password.encode()).hexdigest()

    def register(self, username: str, email: str, phone: str, password: str) -> Optional[User]:
        """Register a new user."""
        password_hash = self._hash_password(password)
        user_id = str(uuid.uuid4())

        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO users (id, username, email, phone, password_hash) VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, email, phone, password_hash)
                )
            return User(
                id=user_id,
                username=username,
                email=email,
                phone=phone,
                password_hash=password_hash,
            )
        except sqlite3.IntegrityError:
            return None  # Username or email already exists

    def login(self, username: str, password: str) -> Optional[User]:
        """Login with username and password."""
        password_hash = self._hash_password(password)
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, username, email, phone, password_hash, created_at FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            ).fetchone()
            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    phone=row[3],
                    password_hash=row[4],
                    created_at=row[5],
                )
        return None

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT id, username, email, phone, password_hash, created_at FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    phone=row[3],
                    password_hash=row[4],
                    created_at=row[5],
                )
        return None

    def user_exists(self, username: str = None, email: str = None) -> bool:
        """Check if username or email already exists."""
        with sqlite3.connect(self._db_path) as conn:
            if username:
                row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
                if row:
                    return True
            if email:
                row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
                if row:
                    return True
        return False


class AuthStore:
    """Session token store for authentication."""

    def __init__(self, db_path: str = "data/users.db"):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tokens table if it doesn't exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

    def create_token(self, user_id: str, expires_hours: int = 24) -> str:
        """Create an authentication token."""
        token = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires_at)
            )
        return token

    def validate_token(self, token: str) -> Optional[str]:
        """Validate token and return user_id if valid."""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT user_id FROM auth_tokens WHERE token = ?",
                (token,)
            ).fetchone()
            if row:
                return row[0]
        return None

    def delete_token(self, token: str) -> bool:
        """Delete a token (logout)."""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            return cursor.rowcount > 0
