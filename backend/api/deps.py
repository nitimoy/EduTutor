"""FastAPI dependency injection functions.

The ``EngineFactory`` is stored in ``app.state.factory`` during application lifespan.
These ``Depends``-compatible functions retrieve it and its engines for route handlers.
"""

from __future__ import annotations

from fastapi import Depends, Request

from backend.api.config import ServiceConfig
from backend.api.factory import EngineFactory
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine


from backend.session.manager import SessionManager


def get_factory(request: Request) -> EngineFactory:
    """Retrieve the application-wide ``EngineFactory`` from ``app.state``."""
    return request.app.state.factory


def get_tutor_engine(
    factory: EngineFactory = Depends(get_factory),
) -> EducationalTutorEngine:
    """Provide the ``EducationalTutorEngine`` via dependency injection."""
    return factory.tutor_engine


def get_session_engine(
    factory: EngineFactory = Depends(get_factory),
) -> LearningSessionEngine:
    """Provide the ``LearningSessionEngine`` via dependency injection."""
    return factory.session_engine


def get_session_manager(
    factory: EngineFactory = Depends(get_factory),
) -> SessionManager:
    """Provide the ``SessionManager`` via dependency injection."""
    return factory.session_manager


def get_config(
    factory: EngineFactory = Depends(get_factory),
) -> ServiceConfig:
    """Provide the ``ServiceConfig`` via dependency injection."""
    return factory.config
