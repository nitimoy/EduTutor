"""Tests for OpenRouter integration."""

import pytest
from unittest.mock import MagicMock

from backend.generation.models import GenerationConfig, PromptDocument
from backend.tutor.models import SectionKind
from backend.integrations.openrouter import OpenRouterLanguageModel


def test_openrouter_metadata():
    model = OpenRouterLanguageModel(model_id="test-model")
    meta = model.metadata()
    assert meta.provider == "openrouter"
    assert meta.model_id == "test-model"
    assert not meta.deterministic


def test_openrouter_lazy_client_init():
    model = OpenRouterLanguageModel(api_key="secret", base_url="http://mock")
    # Client is None initially
    assert model._client is None
    
    client = model._ensure_client()
    assert client is not None
    assert client.api_key == "secret"
    assert str(client.base_url) == "http://mock"


def test_openrouter_generate(monkeypatch):
    model = OpenRouterLanguageModel(model_id="test-model")
    
    # Mock the client
    mock_client = MagicMock()
    mock_completions = MagicMock()
    mock_create = MagicMock()
    
    mock_create.return_value.model_dump.return_value = {
        "choices": [
            {
                "message": {"content": "mocked response"},
                "finish_reason": "stop"
            }
        ]
    }
    
    mock_completions.create = mock_create
    mock_client.chat.completions = mock_completions
    model._client = mock_client
    
    doc = PromptDocument(unit_id="test_unit", unit_kind=SectionKind.MAIN_EXPLANATION, system="sys", blocks=[], citations=[])
    config = GenerationConfig(provider="openrouter", model_id="test-model")
    
    result = model.generate(doc, config)
    
    assert result.text == "mocked response"
    assert result.finish_reason == "stop"
    assert result.provider == "openrouter"
    assert result.model_id == "test-model"
    
    # Verify the request payload shape (OpenAIAdapter format)
    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "sys"
