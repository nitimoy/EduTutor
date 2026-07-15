"""Tests for ServiceConfig."""

import os

from backend.api.config import ServiceConfig
from backend.generation.models import GenerationConfig
from backend.orchestrator.config import OrchestratorConfig


def test_default_config():
    config = ServiceConfig()
    assert config.provider == "openai"
    assert config.model_id == "gpt-4o-mini"
    assert config.retrieval_strategy == "bm25f"
    assert config.top_k == 5
    assert config.use_repository is True
    assert config.strict_verification is False
    assert config.temperature == 0.0
    assert str(config.compiled_dir) == "data/compiled"


def test_to_orchestrator_config_default():
    config = ServiceConfig()
    oc = config.to_orchestrator_config()
    assert isinstance(oc, OrchestratorConfig)
    assert str(oc.compiled_dir) == "data/compiled"
    assert oc.top_k == 5
    assert oc.generation.provider == "openai"
    assert oc.generation.model_id == "gpt-4o-mini"
    assert oc.generation.temperature == 0.0
    assert oc.strict_verification is False


def test_to_orchestrator_config_custom():
    config = ServiceConfig(
        provider="openai",
        model_id="gpt-4o-mini",
        top_k=10,
        style_preset="concise",
        strict_verification=True,
    )
    oc = config.to_orchestrator_config()
    assert oc.generation.provider == "openai"
    assert oc.generation.model_id == "gpt-4o-mini"
    assert oc.top_k == 10
    assert oc.style_preset == "concise"
    assert oc.strict_verification is True


def test_public_summary_no_secrets():
    config = ServiceConfig()
    summary = config.public_summary()
    assert summary["provider"] == "openai"
    assert summary["retrieval_strategy"] == "bm25f"
    assert "api_version" in summary
    # Must not expose any secret fields.
    summary_str = str(summary).lower()
    assert "api_key" not in summary_str
    assert "password" not in summary_str


def test_env_override(monkeypatch):
    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.setenv("MODEL_ID", "gpt-4o")
    monkeypatch.setenv("TOP_K", "3")
    config = ServiceConfig()
    assert config.provider == "openai"
    assert config.model_id == "gpt-4o"
    assert config.top_k == 3
