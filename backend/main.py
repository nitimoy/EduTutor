"""Entry point for uvicorn: ``uvicorn backend.main:app``.

Re-exports the Phase 8.0 FastAPI application. The legacy starter agent files
(agent.py, inputs.py, types.py, constants.py) are preserved but no longer
imported here.
"""

from backend.api.app import app  # noqa: F401
