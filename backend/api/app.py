"""FastAPI application — the service layer entry point.

Creates the app, registers routers and exception handlers, and manages the
application lifespan (engine factory construction). Start with::

    uvicorn backend.main:app
    uvicorn backend.main:app --reload  # development
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.config import ServiceConfig
from backend.api.errors import register_exception_handlers
from backend.api.factory import EngineFactory
from backend.api.routes.chat import router as chat_router
from backend.api.routes.health import router as health_router
from backend.api.routes.session import router as session_router
from backend.api.routes.session_lifecycle import router as session_lifecycle_router
from backend.api.routes.tutor import router as tutor_router
from backend.api.routes.version_selector import router as version_router
from backend.api.routes.auth import router as auth_router
from backend.api.routes.chat_sessions import router as chat_sessions_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the engine factory at startup; tear down on shutdown."""
    config = ServiceConfig()
    factory = EngineFactory(config)
    app.state.factory = factory
    app.state.engine_version = "v1"  # Default to v1
    yield
    # No teardown needed for current components.


app = FastAPI(
    title="NCERT Educational Tutor API",
    description=(
        "A deterministic educational tutor for Class 12 CBSE Mathematics, Physics, "
        "and Chemistry. Supports v1 (traditional) and v2 (RAG-based) engines."
    ),
    version="9.0.0",
    lifespan=lifespan,
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers (order: health/info first, then domain endpoints, then legacy).
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_sessions_router)
app.include_router(version_router)
app.include_router(tutor_router)
app.include_router(session_router)
app.include_router(session_lifecycle_router)
app.include_router(chat_router)

# Register orchestrator exception → HTTP status handlers.
register_exception_handlers(app)
