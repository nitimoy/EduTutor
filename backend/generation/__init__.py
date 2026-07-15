"""Language Generation Layer — deterministic renderer over the frozen TutorPlan (Phase 6.0).

Turns a ``TutorPlan`` into a natural-language teaching response via an LLM, **making no
educational decisions**: no retrieval, no reordering, no added concepts, no invented facts;
citations preserved verbatim. Prompt construction is deterministic and provider-neutral
(``PromptDocument``); provider adapters own the wire formats; the offline ``EchoLanguageModel``
keeps the whole pipeline byte-reproducible in tests/CI.
"""

from backend.generation.adapters import (
    ClaudeAdapter,
    EchoAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    ProviderAdapter,
    adapter_for,
)
from backend.generation.language_model import EchoLanguageModel, LanguageModel
from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    LanguageGenerationPlan,
    LMMetadata,
    PromptBlock,
    PromptDocument,
    RenderedResponse,
    RenderUnit,
    StyleDirective,
)
from backend.generation.plan_builder import build_generation_plan, make_unit_id
from backend.generation.prompt_builder import PromptBuilder
from backend.generation.providers import make_language_model
from backend.generation.renderer import Renderer
from backend.generation.style import STYLE_PRESETS, directive_for

__all__ = [
    "Renderer",
    "PromptBuilder",
    "build_generation_plan",
    "make_unit_id",
    # language models
    "LanguageModel",
    "EchoLanguageModel",
    "make_language_model",
    "LMMetadata",
    # provider adapters
    "ProviderAdapter",
    "EchoAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "GeminiAdapter",
    "adapter_for",
    # IR + config + results
    "StyleDirective",
    "RenderUnit",
    "LanguageGenerationPlan",
    "PromptBlock",
    "PromptDocument",
    "GenerationConfig",
    "GenerationResult",
    "RenderedResponse",
    # style
    "STYLE_PRESETS",
    "directive_for",
]
