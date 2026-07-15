"""Prompt IR, config, and result models for the Language Generation Layer.

This layer is a **renderer**, not a planner: it turns a frozen ``TutorPlan`` into a
natural-language response without making educational decisions. These models capture the
deterministic request pipeline:

    TutorPlan → LanguageGenerationPlan (RenderUnits) → PromptDocument (provider-neutral)
              → ProviderAdapter → LanguageModel → GenerationResult → RenderedResponse

The ``PromptDocument`` is deliberately **provider-neutral** — no chat/message shape leaks
into it; provider adapters own that translation. A stable ``unit_id`` threads through
``RenderUnit`` → ``PromptDocument`` → ``GenerationResult`` for future streaming, retries,
caching, and telemetry. Everything except the LLM call is deterministic.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Reused read-only from the frozen Tutor Brain — a single source of truth for the
# section vocabulary and citation shape. This layer never edits them.
from backend.tutor.models import Citation, EducationalIntent, SectionKind, TeachingStrategyKind

__all__ = [
    "StyleDirective",
    "RenderUnit",
    "LanguageGenerationPlan",
    "PromptBlock",
    "PromptDocument",
    "GenerationConfig",
    "GenerationResult",
    "RenderedResponse",
    "LMMetadata",
]


class StyleDirective(BaseModel):
    """Formatting/tone guidance for one section — **formatting only, never facts**."""

    model_config = ConfigDict(frozen=True)

    tone: str = "clear and encouraging"
    format: str = "short paragraphs"
    max_sentences: Optional[int] = None


class RenderUnit(BaseModel):
    """One section's grounded content to be rendered, with a stable id.

    ``content_lines`` and ``citations`` come verbatim from the ``TutorPlan`` section — the
    only knowledge the renderer is allowed to express.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    kind: SectionKind
    content_lines: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()
    style: StyleDirective = StyleDirective()
    note: str = ""


class LanguageGenerationPlan(BaseModel):
    """The deterministic Prompt IR: ordered render units in ``TutorPlan`` slot order."""

    model_config = ConfigDict(frozen=True)

    query: str
    primary_concept_name: str = ""
    intent: EducationalIntent
    strategy: TeachingStrategyKind
    preset: str = "default"
    units: tuple[RenderUnit, ...] = ()


class PromptBlock(BaseModel):
    """A labeled block of lines inside a provider-neutral prompt document."""

    model_config = ConfigDict(frozen=True)

    label: str
    lines: tuple[str, ...] = ()


class PromptDocument(BaseModel):
    """A **provider-neutral** rendering request for one unit.

    ``system`` carries the fact-free style + renderer contract; ``blocks`` carry the
    unit's grounded content and a citations block. Provider adapters translate this into
    concrete chat/message shapes — this document commits to none.
    """

    model_config = ConfigDict(frozen=True)

    unit_id: str
    unit_kind: SectionKind
    system: str
    blocks: tuple[PromptBlock, ...] = ()
    citations: tuple[Citation, ...] = ()
    metadata: dict[str, str] = Field(default_factory=dict)


class GenerationConfig(BaseModel):
    """Provider-agnostic generation knobs.

    ``temperature=0`` + ``seed`` are requested for reproducibility on real backends
    (best-effort — true determinism is only guaranteed for the offline Echo model).
    """

    provider: str = "echo"
    model_id: str = "echo-v1"
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    seed: int = 0
    style_preset: str = "default"
    extra: dict[str, Any] = Field(default_factory=dict)


class LMMetadata(BaseModel):
    """Self-description of a language model backend."""

    provider: str
    model_id: str
    deterministic: bool


class GenerationResult(BaseModel):
    """One LLM call's output plus its exact neutral prompt and preserved citations."""

    model_config = ConfigDict(frozen=True)

    unit_id: str
    unit_kind: SectionKind
    prompt: PromptDocument
    text: str
    citations: tuple[Citation, ...] = ()
    model_id: str = ""
    provider: str = ""
    finish_reason: str = "stop"


class RenderedResponse(BaseModel):
    """The assembled teaching response: per-section results + concatenated text."""

    model_config = ConfigDict(frozen=True)

    query: str
    primary_concept_name: str = ""
    sections: tuple[GenerationResult, ...] = ()
    text: str = ""
    references: tuple[Citation, ...] = ()  # == TutorPlan.references, preserved verbatim
    provider: str = "echo"
    model_id: str = "echo-v1"
    deterministic: bool = True
    skipped_sections: tuple[str, ...] = ()  # provenance: sections with no renderable content
