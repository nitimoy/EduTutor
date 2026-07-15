"""Provider adapters — the ONLY place chat/message wire formats are constructed.

``PromptBuilder`` produces a provider-neutral :class:`PromptDocument`; each adapter
translates that document into a specific provider's request payload and parses that
provider's raw response back into ``(text, finish_reason)``. Adapters are pure translators:
they hold no educational knowledge, never see a ``TutorPlan``, and are deterministic.

Adding a new provider is one adapter here plus a lazy backend in ``providers.py`` — the
builder and the neutral document never change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from backend.generation.models import GenerationConfig, PromptDocument


def _neutral_user_text(doc: PromptDocument) -> str:
    """Flatten the document's grounded blocks into one deterministic user string."""
    parts: list[str] = []
    for block in doc.blocks:
        if not block.lines:
            continue
        parts.append(f"{block.label}:")
        parts.extend(block.lines)
        parts.append("")  # blank line between blocks
    return "\n".join(parts).rstrip("\n")


class ProviderAdapter(ABC):
    """Translate a neutral PromptDocument to/from a provider's wire format."""

    provider: str = ""

    @abstractmethod
    def to_request(self, doc: PromptDocument, config: GenerationConfig) -> dict[str, Any]:
        """Return the provider-specific request payload for ``doc``."""

    @abstractmethod
    def parse_response(self, raw: Any) -> tuple[str, str]:
        """Return ``(text, finish_reason)`` from a provider's raw response object."""


class EchoAdapter(ProviderAdapter):
    """Trivial adapter for the offline model: exposes the neutral document as-is."""

    provider = "echo"

    def to_request(self, doc: PromptDocument, config: GenerationConfig) -> dict[str, Any]:
        return {
            "unit_id": doc.unit_id,
            "system": doc.system,
            "user": _neutral_user_text(doc),
        }

    def parse_response(self, raw: Any) -> tuple[str, str]:
        if isinstance(raw, dict):
            return raw.get("text", ""), raw.get("finish_reason", "stop")
        return str(raw), "stop"


class OpenAIAdapter(ProviderAdapter):
    """OpenAI chat-completions shape: a system + user message list."""

    provider = "openai"

    def to_request(self, doc: PromptDocument, config: GenerationConfig) -> dict[str, Any]:
        return {
            "model": config.model_id,
            "temperature": config.temperature,
            "seed": config.seed,
            "max_tokens": config.max_tokens or 2048,  # Default to 2048 if not set
            "messages": [
                {"role": "system", "content": doc.system},
                {"role": "user", "content": _neutral_user_text(doc)},
            ],
        }

    def parse_response(self, raw: Any) -> tuple[str, str]:
        choice = raw["choices"][0]
        return choice["message"]["content"], choice.get("finish_reason", "stop")


class ClaudeAdapter(ProviderAdapter):
    """Anthropic Messages shape: top-level system + user messages."""

    provider = "claude"

    def to_request(self, doc: PromptDocument, config: GenerationConfig) -> dict[str, Any]:
        return {
            "model": config.model_id,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens or 1024,
            "system": doc.system,
            "messages": [
                {"role": "user", "content": _neutral_user_text(doc)},
            ],
        }

    def parse_response(self, raw: Any) -> tuple[str, str]:
        # Anthropic returns content blocks; concatenate text blocks.
        blocks = raw["content"]
        text = "".join(b.get("text", "") for b in blocks)
        return text, raw.get("stop_reason", "stop")


class GeminiAdapter(ProviderAdapter):
    """Google Gemini shape: contents + systemInstruction."""

    provider = "gemini"

    def to_request(self, doc: PromptDocument, config: GenerationConfig) -> dict[str, Any]:
        # Strip "gemini/" prefix if present (LiteLLM format -> Google AI format)
        model_name = config.model_id.replace("gemini/", "") if config.model_id.startswith("gemini/") else config.model_id
        return {
            "model": model_name,
            "systemInstruction": {"parts": [{"text": doc.system}]},
            "contents": [
                {"role": "user", "parts": [{"text": _neutral_user_text(doc)}]},
            ],
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens,
            },
        }

    def parse_response(self, raw: Any) -> tuple[str, str]:
        candidate = raw["candidates"][0]
        text = "".join(p.get("text", "") for p in candidate["content"]["parts"])
        return text, candidate.get("finishReason", "stop")


ADAPTERS: dict[str, type[ProviderAdapter]] = {
    a.provider: a for a in (EchoAdapter, OpenAIAdapter, ClaudeAdapter, GeminiAdapter)
}


def adapter_for(provider: str) -> ProviderAdapter:
    """Instantiate the adapter for a provider id."""
    if provider not in ADAPTERS:
        raise ValueError(f"Unknown provider '{provider}'. Known: {sorted(ADAPTERS)}")
    return ADAPTERS[provider]()
