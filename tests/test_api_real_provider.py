"""Tests for API layer real provider configuration."""

from backend.api.config import ServiceConfig
from backend.api.factory import EngineFactory
from backend.integrations.openrouter import OpenRouterLanguageModel
from backend.orchestrator.engine import EducationalTutorEngine


def test_service_config_api_keys_aliasing(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://custom.router/api")
    
    config = ServiceConfig()
    
    assert config.api_key == "sk-or-test"
    assert config.base_url == "https://custom.router/api"


def test_engine_factory_injects_openrouter(monkeypatch):
    # Set up config for OpenRouter via env vars
    monkeypatch.setenv("PROVIDER", "openrouter")
    monkeypatch.setenv("MODEL_ID", "test-model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "http://test")
    
    config = ServiceConfig()
    
    factory = EngineFactory(config)
    
    from backend.evaluation.orchestrator_eval import FakeStrategy
    
    # We patch the orchestrator config so it bypasses strategy building or we mock _build_strategy
    monkeypatch.setattr("backend.orchestrator.engine.EducationalTutorEngine._build_strategy", lambda self: FakeStrategy())
    monkeypatch.setattr("backend.orchestrator.engine.EducationalTutorEngine._build_repository", lambda self: None)
    
    
    # Check the created engine
    engine = factory.tutor_engine
    assert isinstance(engine, EducationalTutorEngine)
    
    # The language model inside the engine should be OpenRouterLanguageModel
    lm = engine._language_model
    assert isinstance(lm, OpenRouterLanguageModel)
    assert lm._api_key == "sk-test"
    assert lm._base_url == "http://test"
    assert lm._model_id == "test-model"
