"""The Renderer: TutorPlan → per-section prompts → LLM → RenderedResponse.

Per-section segmented rendering: each populated section is rendered by its own scoped
prompt (only that section's content + citations), then the results are concatenated in the
``TutorPlan``'s fixed slot order. The renderer makes no educational decisions — it never
retrieves, reorders, adds concepts, or invents facts. Prompt construction is deterministic;
the only non-determinism is the language model itself (and the Echo default is
deterministic, so the whole offline pipeline is byte-reproducible).
"""

from __future__ import annotations

from typing import Optional

from backend.generation.language_model import LanguageModel
from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    PromptDocument,
    RenderedResponse,
)
from backend.generation.plan_builder import build_generation_plan, skipped_section_kinds
from backend.generation.prompt_builder import PromptBuilder
from backend.generation.providers import make_language_model
from backend.tutor.models import TutorPlan


class Renderer:
    """Deterministically render a TutorPlan into a natural-language teaching response."""

    def __init__(self, prompt_builder: Optional[PromptBuilder] = None) -> None:
        self._prompt_builder = prompt_builder or PromptBuilder()

    def build_prompt_documents(
        self, tutor_plan: TutorPlan, config: Optional[GenerationConfig] = None
    ) -> list[PromptDocument]:
        """Build the per-section neutral prompt documents (no LLM call). For snapshots."""
        config = config or GenerationConfig()
        plan = build_generation_plan(tutor_plan, config.style_preset)
        return [self._prompt_builder.build(unit, plan, config) for unit in plan.units]

    def render(
        self,
        tutor_plan: TutorPlan,
        config: Optional[GenerationConfig] = None,
        model: Optional[LanguageModel] = None,
    ) -> RenderedResponse:
        """Render every present section in TutorPlan order and assemble the response."""
        config = config or GenerationConfig()
        model = model or make_language_model(config)
        meta = model.metadata()
        plan = build_generation_plan(tutor_plan, config.style_preset)

        results: list[GenerationResult] = []
        for unit in plan.units:  # already in TutorPlan slot order
            doc = self._prompt_builder.build(unit, plan, config)
            results.append(model.generate(doc, config))

        text = "\n\n".join(r.text for r in results)
        return RenderedResponse(
            query=tutor_plan.query,
            primary_concept_name=tutor_plan.primary_concept_name,
            sections=tuple(results),
            text=text,
            references=tuple(tutor_plan.references),  # preserved verbatim
            provider=meta.provider,
            model_id=meta.model_id,
            deterministic=meta.deterministic,
            skipped_sections=skipped_section_kinds(tutor_plan),
        )
