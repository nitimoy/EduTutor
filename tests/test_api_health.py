"""Tests for GET /, /api/v1/health, /api/v1/ready, /api/v1/version, /api/v1/config."""

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.config import ServiceConfig
from backend.api.deps import get_factory
from backend.api.factory import EngineFactory
from backend.evaluation.orchestrator_eval import FakeStrategy
from backend.generation.language_model import EchoLanguageModel
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine


class _TestFactory(EngineFactory):
    """Factory with injected offline components — no compiled data needed."""

    def __init__(self) -> None:
        super().__init__(ServiceConfig())
        config = OrchestratorConfig(use_repository=False)
        self._tutor_engine = EducationalTutorEngine(
            config, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
        )
        self._session_engine = LearningSessionEngine()


def _test_factory() -> EngineFactory:
    return _TestFactory()


app.dependency_overrides[get_factory] = _test_factory
client = TestClient(app)


def test_root_returns_service_info():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "NCERT Educational Tutor API"
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/v1/health"


def test_health_returns_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_returns_ready():
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True


def test_version_returns_version_and_phase():
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert data["phase"] == "8.0"


def test_config_returns_non_secret_summary():
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["retrieval_strategy"] == "bm25f"
    assert "api_version" in data
    # Must not contain secrets.
    assert "api_key" not in str(data).lower()
