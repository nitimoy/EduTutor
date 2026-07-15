"""The provider-agnostic LanguageModel interface + the offline deterministic default.

All LLM interaction goes through :class:`LanguageModel`. Each concrete model holds a
:class:`ProviderAdapter` (which owns the wire format) and returns a ``GenerationResult``
stamped with the prompt's stable ``unit_id``.

:class:`EchoLanguageModel` is the dependency-free, deterministic default used by tests/CI
and the benchmark — **infrastructure validation only**, not a language-quality baseline
(mirroring the role of ``HashingEmbeddingProvider`` in retrieval). It renders by
deterministically reformatting the document's grounded content, so the whole pipeline is
byte-reproducible and provably grounded without any network access.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.generation.adapters import EchoAdapter, ProviderAdapter
from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    LMMetadata,
    PromptDocument,
)


class LanguageModel(ABC):
    """Common interface for every language-model backend."""

    @abstractmethod
    def generate(
        self, doc: PromptDocument, config: GenerationConfig
    ) -> GenerationResult:
        """Render one prompt document into a ``GenerationResult`` (keyed by ``doc.unit_id``)."""

    @abstractmethod
    def metadata(self) -> LMMetadata:
        """Describe this backend (provider, model id, determinism)."""


class EchoLanguageModel(LanguageModel):
    """Deterministic, offline model. Reformats grounded content; invents nothing."""

    def __init__(self, model_id: str = "echo-v1") -> None:
        self._model_id = model_id
        self._adapter: ProviderAdapter = EchoAdapter()

    def generate(
        self, doc: PromptDocument, config: GenerationConfig
    ) -> GenerationResult:
        request = self._adapter.to_request(doc, config)
        text = self._render(doc)
        # Route the rendered text back through the adapter's parser for symmetry.
        parsed_text, finish_reason = self._adapter.parse_response(
            {"text": text, "finish_reason": "stop"})
        return GenerationResult(
            unit_id=doc.unit_id,
            unit_kind=doc.unit_kind,
            prompt=doc,
            text=parsed_text,
            citations=doc.citations,
            model_id=self._model_id,
            provider="echo",
            finish_reason=finish_reason,
        )

    def _render(self, doc: PromptDocument) -> str:
        """Deterministically compose the section text from grounded content only.

        Every output line is a content line from the document — no new information. This
        makes the Echo model's output provably grounded (a subset of the unit's content).
        """
        content = next((b for b in doc.blocks if b.label == "Content"), None)
        lines = list(content.lines) if content else []
        heading = doc.unit_kind.value.replace("_", " ").title()
        body = " ".join(line.strip() for line in lines if line.strip())
        if not body:
            return heading
        return f"{heading}: {body}"

    def metadata(self) -> LMMetadata:
        return LMMetadata(provider="echo", model_id=self._model_id, deterministic=True)
