"""Authentication API endpoints.

- POST /api/v2/auth/register — Register new user
- POST /api/v2/auth/login — Login
- POST /api/v2/auth/logout — Logout
- GET /api/v2/auth/me — Get current user
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional

from backend.v2.core.user_store import UserStore, AuthStore

router = APIRouter(prefix="/api/v2/auth", tags=["auth"])

_user_store: Optional[UserStore] = None
_auth_store: Optional[AuthStore] = None


def get_stores():
    global _user_store, _auth_store
    if _user_store is None:
        _user_store = UserStore()
    if _auth_store is None:
        _auth_store = AuthStore()
    return _user_store, _auth_store


# === Request/Response models ===

class RegisterRequest(BaseModel):
    username: str
    email: str
    phone: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    username: str
    email: str
    phone: str
    token: str


# === Endpoints ===

@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest):
    """Register a new user."""
    user_store, auth_store = get_stores()

    # Check if username or email already exists
    if user_store.user_exists(username=req.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if user_store.user_exists(email=req.email):
        raise HTTPException(status_code=400, detail="Email already exists")

    # Create user
    user = user_store.register(req.username, req.email, req.phone, req.password)
    if not user:
        raise HTTPException(status_code=400, detail="Registration failed")

    # Create auth token
    token = auth_store.create_token(user.id)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        token=token,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest):
    """Login with username and password."""
    user_store, auth_store = get_stores()

    user = user_store.login(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create auth token
    token = auth_store.create_token(user.id)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        token=token,
    )


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Logout (delete token)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")
    _, auth_store = get_stores()
    auth_store.delete_token(token)
    return {"message": "Logged out"}


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    """Get current user from token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")
    user_store, auth_store = get_stores()

    user_id = auth_store.validate_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = user_store.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
    }
