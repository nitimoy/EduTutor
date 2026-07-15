"""Tests for POST /api/v1/tutor/ask and POST /chat (legacy)."""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.config import ServiceConfig
from backend.api.deps import get_factory
from backend.api.factory import EngineFactory
from backend.evaluation.orchestrator_eval import FakeStrategy, _FailVerifier
from backend.generation.language_model import EchoLanguageModel
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine


class _TestFactory(EngineFactory):
    """Offline factory for tutor tests."""

    def __init__(self, strict: bool = False, verifier=None) -> None:
        super().__init__(ServiceConfig())
        config = OrchestratorConfig(
            use_repository=False, strict_verification=strict,
        )
        self._tutor_engine = EducationalTutorEngine(
            config, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
            verification_engine=verifier,
        )
        self._session_engine = LearningSessionEngine()


def _test_factory() -> EngineFactory:
    return _TestFactory()


app.dependency_overrides[get_factory] = _test_factory
client = TestClient(app)


# --- POST /api/v1/tutor/ask ---


def test_tutor_ask_default_echo():
    resp = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "What is alpha?"
    assert data["answer"]  # non-empty rendered text
    assert data["verification_passed"] is True
    assert data["execution"]["provider"] == "echo"
    assert "deterministic_fingerprint" in data


def test_tutor_ask_with_student_profile():
    resp = client.post("/api/v1/tutor/ask", json={
        "query": "What is alpha?",
        "student_profile": {
            "preferences": {"difficulty": "easy"},
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]


def test_tutor_ask_with_retrieval_context():
    resp = client.post("/api/v1/tutor/ask", json={
        "query": "What is alpha?",
        "retrieval_context": {"subject": "chemistry"},
    })
    assert resp.status_code == 200
    data = resp.json()
    # FakeStrategy has physics docs, so chemistry filter → 0 results.
    assert data["retrieval"]["n_results"] == 0
    assert data["retrieval"]["subject"] == "chemistry"


def test_tutor_ask_empty_query_rejected():
    resp = client.post("/api/v1/tutor/ask", json={"query": ""})
    assert resp.status_code == 422


def test_tutor_ask_citations_present():
    resp = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"})
    data = resp.json()
    assert isinstance(data["citations"], list)
    if data["citations"]:
        cit = data["citations"][0]
        assert "concept_id" in cit
        assert "concept_name" in cit


def test_tutor_ask_determinism():
    a = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"}).json()
    b = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"}).json()
    assert a["deterministic_fingerprint"] == b["deterministic_fingerprint"]


def test_tutor_ask_timing_present():
    data = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"}).json()
    assert "timing" in data
    assert "total_ms" in data["timing"]
    assert "per_stage_ms" in data["timing"]


# --- Verification failure ---


def test_strict_verification_returns_422():
    """Under strict mode, a failing verifier should return 422."""
    strict_factory = _TestFactory(strict=True, verifier=_FailVerifier())
    app.dependency_overrides[get_factory] = lambda: strict_factory
    try:
        resp = client.post("/api/v1/tutor/ask", json={"query": "What is alpha?"})
        assert resp.status_code == 422
        data = resp.json()
        assert data["code"] == "VERIFICATION_FAILED"
    finally:
        app.dependency_overrides[get_factory] = _test_factory


# --- POST /chat (legacy) ---


def test_chat_legacy_endpoint():
    resp = client.post("/chat", json={
        "messages": [{"role": "user", "content": "What is alpha?"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "model" in data
    assert data["answer"]  # non-empty


def test_chat_legacy_empty_messages_rejected():
    resp = client.post("/chat", json={"messages": []})
    assert resp.status_code == 422


def test_chat_legacy_multi_turn():
    resp = client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "What is alpha?"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
