"""OpenRouter language model integration.

Implements the frozen :class:`LanguageModel` interface for OpenRouter. Reuses the
frozen :class:`OpenAIAdapter` since OpenRouter is API-compatible.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from backend.generation.adapters import OpenAIAdapter, ProviderAdapter
from backend.generation.language_model import LanguageModel
from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    LMMetadata,
    PromptDocument,
)


class OpenRouterLanguageModel(LanguageModel):
    """OpenRouter integration via the OpenAI Python SDK."""

    provider = "openrouter"
    default_base_url = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        model_id: str = "openai/gpt-oss-120b",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._model_id = model_id
        self._api_key = api_key
        self._base_url = base_url or self.default_base_url
        self._adapter: ProviderAdapter = OpenAIAdapter()
        # Lazy import of SDK to keep tests fast/offline if not used.
        self._client = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                # Optional: specify headers typical for OpenRouter, though often works without
                # default_headers={
                #     "HTTP-Referer": "https://github.com/sujho-assignment",
                #     "X-Title": "NCERT Tutor",
                # }
            )
        return self._client

    def generate(
        self, doc: PromptDocument, config: GenerationConfig
    ) -> GenerationResult:
        """Call OpenRouter, parse response, and extract token usage."""
        client = self._ensure_client()
        request = self._adapter.to_request(doc, config)
        
        # Call the API
        t0 = time.time()
        raw = client.chat.completions.create(**request).model_dump()
        latency_ms = (time.time() - t0) * 1000

        text, finish_reason = self._adapter.parse_response(raw)
        
        # Log usage to side-channel for benchmarks (preserves frozen GenerationResult)
        usage = raw.get("usage")
        if usage:
            try:
                import json
                from pathlib import Path
                log_file = Path("data/openrouter_usage.jsonl")
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with log_file.open("a") as f:
                    f.write(json.dumps({
                        "unit_id": doc.unit_id,
                        "model": self._model_id,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0)
                    }) + "\n")
            except Exception:
                pass

        # Build basic result
        result = GenerationResult(
            unit_id=doc.unit_id,
            unit_kind=doc.unit_kind,
            prompt=doc,
            text=text,
            citations=doc.citations,
            model_id=self._model_id,
            provider=self.provider,
            finish_reason=finish_reason,
        )

        # OpenRouter returns usage metrics we can piggyback onto the result if needed later,
        # but the frozen GenerationResult currently only tracks text/citations/metadata.
        # We respect the frozen interface.
        return result

    def metadata(self) -> LMMetadata:
        """Describe this backend."""
        return LMMetadata(
            provider=self.provider, model_id=self._model_id, deterministic=False
        )
