"""Tests for POST /api/v1/session/process."""

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
    def __init__(self) -> None:
        super().__init__(ServiceConfig())
        config = OrchestratorConfig(use_repository=False)
        self._tutor_engine = EducationalTutorEngine(
            config, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
        )
        self._session_engine = LearningSessionEngine()


app.dependency_overrides[get_factory] = lambda: _TestFactory()
client = TestClient(app)


def test_session_process_basic():
    resp = client.post("/api/v1/session/process", json={
        "session": {
            "session_id": "s1",
            "events": [
                {"type": "lesson_started", "concept_id": "c1"},
                {"type": "exercise_correct", "concept_id": "c1"},
                {"type": "lesson_completed", "concept_id": "c1"},
            ],
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "delta" in data
    assert "after" in data
    assert "summary" in data


def test_session_process_empty_events():
    resp = client.post("/api/v1/session/process", json={
        "session": {"session_id": "s2", "events": []},
    })
    assert resp.status_code == 200
    data = resp.json()
    # Empty session → no concept changes.
    assert data["delta"]["concept_changes"] == []


def test_session_process_with_before_state():
    resp = client.post("/api/v1/session/process", json={
        "before": {"concept_mastery": {"c1": 0.5}},
        "session": {
            "session_id": "s3",
            "events": [
                {"type": "exercise_correct", "concept_id": "c1"},
            ],
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    # After-state should reflect the mastery bump from the correct exercise.
    assert data["after"]["concept_mastery"]["c1"] > 0.5


def test_session_process_missing_session_rejected():
    resp = client.post("/api/v1/session/process", json={})
    assert resp.status_code == 422
