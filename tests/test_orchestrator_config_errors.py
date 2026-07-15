"""Tests for OrchestratorConfig and the error types."""

import pytest

from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.errors import (
    ConfigurationError,
    OrchestratorError,
    StageExecutionError,
    VerificationFailedError,
)


def test_config_defaults_are_offline():
    c = OrchestratorConfig()
    assert c.retrieval_strategy == "bm25f" and c.generation.provider == "echo"
    assert c.strict_verification is False and c.top_k == 5


def test_stage_execution_error_carries_stage_and_cause():
    cause = ValueError("boom")
    err = StageExecutionError("retrieval", cause)
    assert err.stage == "retrieval" and err.cause is cause
    assert isinstance(err, OrchestratorError)


def test_verification_failed_error_carries_response():
    err = VerificationFailedError(response={"x": 1})
    assert err.response == {"x": 1} and isinstance(err, OrchestratorError)


def test_missing_strategy_and_compiled_dir_raises_configuration_error():
    # No injected strategy and no compiled_dir -> cannot build BM25F.
    with pytest.raises(ConfigurationError):
        EducationalTutorEngine(OrchestratorConfig())


def test_repository_without_compiled_dir_raises(monkeypatch):
    # Inject a strategy so retrieval builds, but leave use_repository=True + no compiled_dir.
    from backend.evaluation.orchestrator_eval import FakeStrategy
    with pytest.raises(ConfigurationError):
        EducationalTutorEngine(OrchestratorConfig(use_repository=True), strategy=FakeStrategy())
