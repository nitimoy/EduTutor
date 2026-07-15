"""Language-model factory + lazily-imported real provider backends.

``make_language_model`` returns the offline :class:`EchoLanguageModel` by default. Real
providers (OpenAI / Gemini / Claude) are imported lazily inside their ``__init__`` so the
package has no hard SDK dependency and stays offline unless explicitly configured. Each
backend pairs its :class:`ProviderAdapter` (wire format) with an SDK client; retrieval and
educational knowledge are never touched here.
"""

from __future__ import annotations

from backend.generation.adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    ProviderAdapter,
)
from backend.generation.language_model import EchoLanguageModel, LanguageModel
from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    LMMetadata,
    PromptDocument,
)


class _RemoteLanguageModel(LanguageModel):
    """Shared skeleton for real backends: adapter builds the request, a client sends it."""

    provider = ""

    def __init__(self, adapter: ProviderAdapter, model_id: str) -> None:
        self._adapter = adapter
        self._model_id = model_id
        self._client = self._build_client()  # lazy SDK import happens here

    def _build_client(self):  # pragma: no cover - requires SDK + credentials
        raise NotImplementedError

    def _invoke(self, request: dict):  # pragma: no cover - network
        raise NotImplementedError

    def generate(self, doc: PromptDocument, config: GenerationConfig) -> GenerationResult:  # pragma: no cover
        request = self._adapter.to_request(doc, config)
        raw = self._invoke(request)
        text, finish_reason = self._adapter.parse_response(raw)
        return GenerationResult(
            unit_id=doc.unit_id, unit_kind=doc.unit_kind, prompt=doc, text=text,
            citations=doc.citations, model_id=self._model_id, provider=self.provider,
            finish_reason=finish_reason)

    def metadata(self) -> LMMetadata:
        return LMMetadata(provider=self.provider, model_id=self._model_id, deterministic=False)


class OpenAILanguageModel(_RemoteLanguageModel):
    provider = "openai"

    def __init__(self, model_id: str = "gpt-4o-mini") -> None:
        super().__init__(OpenAIAdapter(), model_id)

    def _build_client(self):  # pragma: no cover - requires SDK + credentials
        from openai import OpenAI  # lazy
        return OpenAI()

    def _invoke(self, request: dict):  # pragma: no cover - network
        return self._client.chat.completions.create(**request).model_dump()


class ClaudeLanguageModel(_RemoteLanguageModel):
    provider = "claude"

    def __init__(self, model_id: str = "claude-sonnet-5") -> None:
        super().__init__(ClaudeAdapter(), model_id)

    def _build_client(self):  # pragma: no cover - requires SDK + credentials
        from anthropic import Anthropic  # lazy
        return Anthropic()

    def _invoke(self, request: dict):  # pragma: no cover - network
        return self._client.messages.create(**request).model_dump()


class GeminiLanguageModel(_RemoteLanguageModel):
    provider = "gemini"

    def __init__(self, model_id: str = "gemini-2.0-flash") -> None:
        # Strip "gemini/" prefix if present (LiteLLM format -> Google AI format)
        clean_id = model_id.replace("gemini/", "") if model_id.startswith("gemini/") else model_id
        super().__init__(GeminiAdapter(), clean_id)

    def _build_client(self):  # pragma: no cover - requires SDK + credentials
        import google.generativeai as genai  # lazy
        return genai

    def _invoke(self, request: dict):  # pragma: no cover - network
        model = self._client.GenerativeModel(request["model"])
        return model.generate_content(request["contents"]).to_dict()


class OpenRouterLanguageModel(_RemoteLanguageModel):
    provider = "openrouter"

    def __init__(self, model_id: str = "openrouter/auto") -> None:
        super().__init__(OpenAIAdapter(), model_id)

    def _build_client(self):  # pragma: no cover - requires SDK + credentials
        from openai import OpenAI  # lazy
        import os
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )

    def _invoke(self, request: dict):  # pragma: no cover - network
        return self._client.chat.completions.create(**request).model_dump()


_REMOTE: dict[str, type[_RemoteLanguageModel]] = {
    "openai": OpenAILanguageModel,
    "claude": ClaudeLanguageModel,
    "gemini": GeminiLanguageModel,
    "openrouter": OpenRouterLanguageModel,
}


def make_language_model(config: GenerationConfig) -> LanguageModel:
    """Return the language model for ``config.provider`` (Echo by default)."""
    provider = config.provider
    if provider == "echo":
        return EchoLanguageModel(model_id=config.model_id)
        
    if provider == "auto":
        import os
        if os.environ.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "claude"
        elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            provider = "gemini"
        else:
            raise ValueError("PROVIDER=auto, but no API keys found in environment.")
            
    if provider in _REMOTE:
        return _REMOTE[provider](model_id=config.model_id)  # pragma: no cover - lazy SDK
    raise ValueError(
        f"Unknown provider '{provider}'. Known: auto, echo, {', '.join(sorted(_REMOTE))}"
    )
