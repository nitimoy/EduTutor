"""Build a deterministic LanguageGenerationPlan from a frozen TutorPlan.

Walks the ``TutorPlan``'s **fixed slot order** and emits one :class:`RenderUnit` per
section that is ``PRESENT`` with non-empty items. No reordering (slot order is
authoritative), no added content — the unit carries the section's ``items``/``citations``
verbatim plus a formatting-only style directive. Each unit gets a stable, deterministic
``unit_id`` so prompts/results are byte-reproducible.
"""

from __future__ import annotations

from backend.generation.models import LanguageGenerationPlan, RenderUnit
from backend.generation.style import directive_for
from backend.tutor.models import PlanSection, SectionStatus, TutorPlan

# The canonical slot order, matching the TutorPlan field order (Phase 4.0). Rendering
# never deviates from this — the Student Model already decided ordering upstream.
_SLOT_ORDER: tuple[str, ...] = (
    "grounded_facts",   # disclaimer — rendered first when present
    "prerequisites",
    "main_explanation",
    "formula",
    "worked_example",
    "proof",
    "exercise",
    "comparison",
    "related_concepts",
    "suggested_next_topics",
    "summary",
)


def make_unit_id(primary_concept_id: str | None, section_kind_value: str) -> str:
    """Deterministic unit id. Each kind is a unique fixed slot, so this is collision-free."""
    return f"{primary_concept_id or 'plan'}::{section_kind_value}"


def build_generation_plan(
    tutor_plan: TutorPlan, preset: str = "default"
) -> LanguageGenerationPlan:
    """Flatten a TutorPlan into ordered render units (present, non-empty sections only)."""
    units: list[RenderUnit] = []
    for field in _SLOT_ORDER:
        section: PlanSection = getattr(tutor_plan, field)
        # GROUNDED_FACTS: present when note is set, even if items is empty.
        from backend.tutor.models import SectionKind
        if section.kind == SectionKind.GROUNDED_FACTS:
            if section.status != SectionStatus.PRESENT:
                continue
            # Use the note as the content line (the disclaimer text).
            content = (section.note,) if section.note else ("[disclaimer]",)
            units.append(RenderUnit(
                unit_id=make_unit_id(tutor_plan.primary_concept_id, section.kind.value),
                kind=section.kind,
                content_lines=content,
                citations=(),
                style=directive_for(preset, section.kind),
                note=section.note,
            ))
            continue
        if section.status != SectionStatus.PRESENT or not section.items:
            continue
        units.append(RenderUnit(
            unit_id=make_unit_id(tutor_plan.primary_concept_id, section.kind.value),
            kind=section.kind,
            content_lines=tuple(section.items),
            citations=tuple(section.citations),
            style=directive_for(preset, section.kind),
            note=section.note,
        ))

    return LanguageGenerationPlan(
        query=tutor_plan.query,
        primary_concept_name=tutor_plan.primary_concept_name,
        intent=tutor_plan.intent,
        strategy=tutor_plan.strategy,
        preset=preset,
        units=tuple(units),
    )


def skipped_section_kinds(tutor_plan: TutorPlan) -> tuple[str, ...]:
    """Section kinds present in the plan but not renderable (empty/unsupported)."""
    skipped: list[str] = []
    for field in _SLOT_ORDER:
        section: PlanSection = getattr(tutor_plan, field)
        if section.status != SectionStatus.PRESENT or not section.items:
            skipped.append(section.kind.value)
    return tuple(skipped)
