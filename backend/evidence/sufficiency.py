"""Evidence Sufficiency Check — can the retrieved material answer WHY?

This runs *after* the Evidence Assessment Engine confirms that the corpus
contains a relevant concept. It answers a separate, finer question:

    "Does the retrieved evidence support the *reasoning style* the question
     demands — or only the bare facts?"

Returns ``EvidenceSufficiency``:
    SUPPORTED           — material can answer the question from first principles.
    PARTIALLY_SUPPORTED — material has facts but lacks a causal chain.
    INSUFFICIENT        — material is too thin to support any real answer.

When the result is not SUPPORTED, the EducationalGoal's lesson pattern
decides whether to emit a structured disclaimer (disclaimer_if_partial=True).
"""

from __future__ import annotations

from backend.retrieval.strategies.base import SearchResult
from backend.tutor.models import (
    EvidenceSufficiency,
    EducationalGoal,
    SectionKind,
)
from backend.tutor.organizer import OrganizedContext


class EvidenceSufficiencyCheck:
    """Determine whether retrieved evidence can support the required reasoning."""

    def check(
        self,
        educational_goal: EducationalGoal,
        context: OrganizedContext,
        results: list[SearchResult],
    ) -> tuple[EvidenceSufficiency, str]:
        """Return ``(sufficiency, reason)`` for the given educational goal.

        ``reason`` is empty when SUPPORTED; otherwise a student-friendly
        description that becomes the disclaimer text.
        """
        method = _DISPATCH.get(educational_goal, _check_default)
        return method(context, results)


# ---------------------------------------------------------------------------
# Per-EducationalGoal checks
# ---------------------------------------------------------------------------

def _has_definition(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.MAIN_EXPLANATION)


def _has_formula(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.FORMULA)


def _has_example(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.WORKED_EXAMPLE)


def _has_related(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.RELATED_CONCEPTS)


def _has_next_topics(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.NEXT_TOPICS)


def _has_prereqs(context: OrganizedContext) -> bool:
    return context.is_supported(SectionKind.PREREQUISITES)


def _count_comparison_concepts(context: OrganizedContext) -> int:
    comp_section = context.section(SectionKind.COMPARISON)
    if not comp_section.item_refs:
        return 0
    from backend.tutor.models import SOURCE_DEFINITION
    return sum(1 for item in comp_section.item_refs if item.source_field == SOURCE_DEFINITION)


def _check_understand_principle(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    """UNDERSTAND_PRINCIPLE (Why/How/Can): needs a causal or conceptual chain.

    SUPPORTED           — definition + (related concepts OR formula) — enough
                          to explain first-principles reasoning.
    PARTIALLY_SUPPORTED — definition only — can state what, not explain why.
    INSUFFICIENT        — no definition at all.
    """
    if not _has_definition(context):
        return (
            EvidenceSufficiency.INSUFFICIENT,
            "no definition found in the retrieved material",
        )
    if _has_related(context) or _has_formula(context) or _has_example(context):
        return EvidenceSufficiency.SUPPORTED, ""
    return (
        EvidenceSufficiency.PARTIALLY_SUPPORTED,
        "contains a definition but does not explicitly explain the underlying reason",
    )


def _check_structured_comparison(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    """STRUCTURED_COMPARISON: needs ≥ 2 concepts with definitions."""
    n = _count_comparison_concepts(context)
    if n >= 2:
        return EvidenceSufficiency.SUPPORTED, ""
    if n == 1 or _has_definition(context):
        return (
            EvidenceSufficiency.PARTIALLY_SUPPORTED,
            "provides only one concept; a full side-by-side comparison is not possible",
        )
    return (
        EvidenceSufficiency.INSUFFICIENT,
        "does not provide sufficient definitions to make a comparison",
    )


def _check_learning_path(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    """LEARNING_PATH: needs next_topics from the chapter hierarchy."""
    if _has_next_topics(context):
        return EvidenceSufficiency.SUPPORTED, ""
    if _has_prereqs(context) or _has_related(context):
        return (
            EvidenceSufficiency.PARTIALLY_SUPPORTED,
            "chapter study-order information is not available in the source material; "
            "related concepts and prerequisites are shown instead",
        )
    return (
        EvidenceSufficiency.INSUFFICIENT,
        "no chapter hierarchy information (next topics, prerequisites) is available",
    )


def _check_problem_solving(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    if _has_example(context):
        return EvidenceSufficiency.SUPPORTED, ""
    if _has_definition(context) or _has_formula(context):
        return (
            EvidenceSufficiency.PARTIALLY_SUPPORTED,
            "no worked example found in the source material; "
            "definition and formula are available",
        )
    return (
        EvidenceSufficiency.INSUFFICIENT,
        "no worked example, definition, or formula found",
    )


def _check_proof_and_derivation(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    if context.is_supported(SectionKind.PROOF):
        return EvidenceSufficiency.SUPPORTED, ""
    if _has_formula(context):
        return (
            EvidenceSufficiency.PARTIALLY_SUPPORTED,
            "no derivation or proof found in the source material; "
            "the formula is available but not its derivation",
        )
    return (
        EvidenceSufficiency.INSUFFICIENT,
        "neither a proof nor a formula was found in the retrieved material",
    )


def _check_quick_revision(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    # Revision always has at least a SUMMARY (always PRESENT by design).
    return EvidenceSufficiency.SUPPORTED, ""


def _check_default(
    context: OrganizedContext, results: list[SearchResult]
) -> tuple[EvidenceSufficiency, str]:
    """CONCEPTUAL_UNDERSTANDING, EXAM_PREPARATION, and others."""
    if _has_definition(context):
        return EvidenceSufficiency.SUPPORTED, ""
    return (
        EvidenceSufficiency.PARTIALLY_SUPPORTED,
        "no explicit definition found; related facts are available",
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict = {
    EducationalGoal.UNDERSTAND_PRINCIPLE: _check_understand_principle,
    EducationalGoal.STRUCTURED_COMPARISON: _check_structured_comparison,
    EducationalGoal.LEARNING_PATH: _check_learning_path,
    EducationalGoal.PROBLEM_SOLVING: _check_problem_solving,
    EducationalGoal.PROOF_AND_DERIVATION: _check_proof_and_derivation,
    EducationalGoal.QUICK_REVISION: _check_quick_revision,
}
