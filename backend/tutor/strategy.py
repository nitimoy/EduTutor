"""Teaching Strategy selection — intent × lesson-pattern × evidence sufficiency.

This replaces the old single-pass fallback logic with a three-level decision:

1. ``question_type_strategy`` — derive the canonical TeachingStrategyKind from
   the QuestionType. This is the *requested* strategy.

2. ``select_strategy`` — check whether the lead section is backed by data.
   If not, fall back using the *intent-aware* fallback table. The fallback
   table does NOT route conceptual/comparison intents to worked_example.

3. ``apply_lesson_pattern`` — filter the strategy's section template through
   the LessonPattern's ``blocked`` list. Blocked sections are dropped even
   when backed by data; this guarantees the lesson structure is driven by
   question type, not by data availability.

KEY INVARIANT:
  WORKED_EXAMPLE_WALKTHROUGH is NEVER a fallback for EXPLANATION,
  CONCEPTUAL_REASONING, COMPARISON, or LEARNING_PATH intents.
"""

from __future__ import annotations

from backend.tutor.lesson_patterns import LessonPattern, pattern_for
from backend.tutor.models import (
    EvidenceSufficiency,
    EducationalGoal,
    EducationalIntent,
    QuestionType,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingStrategyKind,
)
from backend.tutor.organizer import OrganizedContext

# ---------------------------------------------------------------------------
# QuestionType → TeachingStrategyKind mapping (canonical strategy)
# ---------------------------------------------------------------------------

_QT_TO_STRATEGY: dict[QuestionType, TeachingStrategyKind] = {
    QuestionType.DEFINITION:           TeachingStrategyKind.CONCEPT_EXPLANATION,
    QuestionType.EXPLANATION:          TeachingStrategyKind.CONCEPT_EXPLANATION,
    QuestionType.COMPARISON:           TeachingStrategyKind.COMPARE_AND_CONTRAST,
    QuestionType.CLASSIFICATION:       TeachingStrategyKind.CONCEPT_EXPLANATION,
    QuestionType.PROCEDURE:            TeachingStrategyKind.CONCEPT_EXPLANATION,
    QuestionType.FORMULA:              TeachingStrategyKind.FORMULA_EXPLANATION,
    QuestionType.DERIVATION:           TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
    QuestionType.WORKED_EXAMPLE:       TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH,
    QuestionType.LEARNING_PATH:        TeachingStrategyKind.PREREQUISITE_PATHWAY,
    QuestionType.REVISION:             TeachingStrategyKind.REVISION_SUMMARY,
    QuestionType.EXAM_PREPARATION:     TeachingStrategyKind.REVISION_SUMMARY,
    QuestionType.APPLICATION:          TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH,
    QuestionType.CONCEPTUAL_REASONING: TeachingStrategyKind.CONCEPT_EXPLANATION,
}

# EducationalGoal → TeachingStrategyKind (used when the goal is known).
_GOAL_TO_STRATEGY: dict[EducationalGoal, TeachingStrategyKind] = {
    EducationalGoal.CONCEPTUAL_UNDERSTANDING: TeachingStrategyKind.CONCEPT_EXPLANATION,
    EducationalGoal.UNDERSTAND_PRINCIPLE:     TeachingStrategyKind.CONCEPT_EXPLANATION,
    EducationalGoal.EXAM_PREPARATION:         TeachingStrategyKind.REVISION_SUMMARY,
    EducationalGoal.PROBLEM_SOLVING:          TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH,
    EducationalGoal.PROOF_AND_DERIVATION:     TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
    EducationalGoal.QUICK_REVISION:           TeachingStrategyKind.REVISION_SUMMARY,
    EducationalGoal.LEARNING_PATH:            TeachingStrategyKind.PREREQUISITE_PATHWAY,
    EducationalGoal.STRUCTURED_COMPARISON:    TeachingStrategyKind.COMPARE_AND_CONTRAST,
}

# Legacy EducationalIntent → QuestionType bridge (for code paths that still
# use the old intent without a question_type).
_INTENT_TO_QT: dict[EducationalIntent, QuestionType] = {
    EducationalIntent.DEFINITION: QuestionType.DEFINITION,
    EducationalIntent.EXPLANATION: QuestionType.EXPLANATION,
    EducationalIntent.COMPARISON: QuestionType.COMPARISON,
    EducationalIntent.PREREQUISITE: QuestionType.LEARNING_PATH,
    EducationalIntent.WORKED_EXAMPLE: QuestionType.WORKED_EXAMPLE,
    EducationalIntent.FORMULA: QuestionType.FORMULA,
    EducationalIntent.PROOF: QuestionType.DERIVATION,
    EducationalIntent.APPLICATION: QuestionType.APPLICATION,
    EducationalIntent.REVISION: QuestionType.REVISION,
}

# ---------------------------------------------------------------------------
# Intent-AWARE fallback table.
#
# For each intent, the fallback cascade is restricted to strategies that
# preserve the pedagogical meaning. WORKED_EXAMPLE_WALKTHROUGH is NOT a
# fallback for conceptual, comparison, or learning-path intents.
# ---------------------------------------------------------------------------

_FALLBACK_BY_INTENT: dict[EducationalIntent, tuple[TeachingStrategyKind, ...]] = {
    EducationalIntent.DEFINITION: (
        TeachingStrategyKind.CONCEPT_EXPLANATION,
        TeachingStrategyKind.REVISION_SUMMARY,
    ),
    EducationalIntent.EXPLANATION: (
        # WORKED_EXAMPLE deliberately absent.
        TeachingStrategyKind.CONCEPT_EXPLANATION,
        TeachingStrategyKind.FORMULA_EXPLANATION,
        TeachingStrategyKind.REVISION_SUMMARY,
    ),
    EducationalIntent.COMPARISON: (
        # Only COMPARE_AND_CONTRAST is valid; no fallback to anything else.
        TeachingStrategyKind.COMPARE_AND_CONTRAST,
    ),
    EducationalIntent.PREREQUISITE: (
        TeachingStrategyKind.PREREQUISITE_PATHWAY,
        TeachingStrategyKind.REVISION_SUMMARY,
    ),
    EducationalIntent.WORKED_EXAMPLE: (
        TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH,
        TeachingStrategyKind.CONCEPT_EXPLANATION,
    ),
    EducationalIntent.FORMULA: (
        TeachingStrategyKind.FORMULA_EXPLANATION,
        TeachingStrategyKind.CONCEPT_EXPLANATION,
    ),
    EducationalIntent.PROOF: (
        TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
        TeachingStrategyKind.FORMULA_EXPLANATION,
    ),
    EducationalIntent.APPLICATION: (
        TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH,
        TeachingStrategyKind.CONCEPT_EXPLANATION,
    ),
    EducationalIntent.REVISION: (
        TeachingStrategyKind.REVISION_SUMMARY,
        TeachingStrategyKind.CONCEPT_EXPLANATION,
    ),
}

# Section templates: used only for the legacy path + strategy name mapping.
_TEMPLATES: dict[TeachingStrategyKind, tuple[SectionKind, ...]] = {
    TeachingStrategyKind.CONCEPT_EXPLANATION: (
        SectionKind.MAIN_EXPLANATION, SectionKind.PREREQUISITES, SectionKind.FORMULA,
        SectionKind.WORKED_EXAMPLE, SectionKind.RELATED_CONCEPTS,
        SectionKind.NEXT_TOPICS, SectionKind.SUMMARY),
    TeachingStrategyKind.FORMULA_EXPLANATION: (
        SectionKind.MAIN_EXPLANATION, SectionKind.FORMULA, SectionKind.WORKED_EXAMPLE,
        SectionKind.RELATED_CONCEPTS, SectionKind.SUMMARY),
    TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH: (
        SectionKind.MAIN_EXPLANATION, SectionKind.WORKED_EXAMPLE, SectionKind.FORMULA,
        SectionKind.EXERCISE, SectionKind.SUMMARY),
    TeachingStrategyKind.COMPARE_AND_CONTRAST: (
        SectionKind.COMPARISON, SectionKind.RELATED_CONCEPTS, SectionKind.SUMMARY),
    TeachingStrategyKind.STEP_BY_STEP_DERIVATION: (
        SectionKind.MAIN_EXPLANATION, SectionKind.PROOF, SectionKind.FORMULA,
        SectionKind.WORKED_EXAMPLE, SectionKind.SUMMARY),
    TeachingStrategyKind.REVISION_SUMMARY: (
        SectionKind.MAIN_EXPLANATION, SectionKind.SUMMARY, SectionKind.FORMULA,
        SectionKind.PREREQUISITES, SectionKind.NEXT_TOPICS),
    TeachingStrategyKind.PREREQUISITE_PATHWAY: (
        SectionKind.PREREQUISITES, SectionKind.NEXT_TOPICS,
        SectionKind.RELATED_CONCEPTS, SectionKind.SUMMARY),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def strategy_for_question_type(qt: QuestionType) -> TeachingStrategyKind:
    """The TeachingStrategyKind that a QuestionType naturally maps to."""
    return _QT_TO_STRATEGY[qt]


def strategy_for_goal(goal: EducationalGoal) -> TeachingStrategyKind:
    """The TeachingStrategyKind that an EducationalGoal maps to."""
    return _GOAL_TO_STRATEGY[goal]


def question_type_for_intent(intent: EducationalIntent) -> QuestionType:
    """Bridge: EducationalIntent → QuestionType (for legacy call sites)."""
    return _INTENT_TO_QT.get(intent, QuestionType.DEFINITION)


def template_for(strategy: TeachingStrategyKind) -> tuple[SectionKind, ...]:
    """The ordered section template for a strategy (legacy / composition use)."""
    return _TEMPLATES[strategy]


def base_strategy(intent: EducationalIntent) -> TeachingStrategyKind:
    """Legacy: the strategy an intent maps to before any data-aware fallback."""
    qt = _INTENT_TO_QT.get(intent, QuestionType.DEFINITION)
    return _QT_TO_STRATEGY[qt]


def select_strategy(
    intent: EducationalIntent, context: OrganizedContext
) -> tuple[TeachingStrategyKind, str]:
    """Pick a strategy for ``intent``, using intent-aware fallback when needed.

    Returns ``(strategy, note)`` where ``note`` is empty when no fallback
    occurred, or a human-readable reason when the natural strategy lacked
    backing content.

    KEY DIFFERENCE FROM OLD CODE:
      - Fallback cascades are intent-specific; WORKED_EXAMPLE is not reachable
        from EXPLANATION, COMPARISON, or LEARNING_PATH intents.
      - When *no* fallback is viable, the natural strategy is returned with an
        honest note — empty sections are better than wrong sections.
    """
    qt = _INTENT_TO_QT.get(intent, QuestionType.DEFINITION)
    return select_strategy_for_qt(qt, intent, context)


def select_strategy_for_qt(
    question_type: QuestionType,
    intent: EducationalIntent,
    context: OrganizedContext,
    educational_goal: EducationalGoal | None = None,
) -> tuple[TeachingStrategyKind, str]:
    """Full strategy selection using QuestionType, EducationalGoal, and EducationalIntent."""
    # Prefer the goal-driven strategy when an EducationalGoal is available.
    if educational_goal is not None:
        base = _GOAL_TO_STRATEGY.get(educational_goal, _QT_TO_STRATEGY[question_type])
        pattern = pattern_for(educational_goal)
    else:
        base = _QT_TO_STRATEGY[question_type]
        from backend.tutor.lesson_patterns import default_goal_for
        default_goal = default_goal_for(question_type)
        pattern = pattern_for(default_goal)

    lead = _lead_section_for(base, pattern)

    # If the lead section (or any required section) is supported, proceed.
    if lead is None or context.is_supported(lead):
        return base, ""

    # Intent-aware fallback: iterate only over cascades permitted for this intent.
    cascade = _FALLBACK_BY_INTENT.get(intent, (base,))
    for candidate in cascade:
        if candidate == base:
            continue
        candidate_lead = _TEMPLATES[candidate][0] if _TEMPLATES.get(candidate) else None
        if candidate_lead is None or context.is_supported(candidate_lead):
            note = (
                f"intent '{intent.value}' → '{base.value}' unavailable "
                f"(lead section '{lead.value if lead else 'unknown'}' has no "
                f"backing content); fell back to '{candidate.value}'"
            )
            return candidate, note

    # No fallback viable — retain the natural strategy with an honest note.
    # The composer will emit the disclaimer via EvidenceSufficiency.
    return base, (
        f"no section has backing content for '{intent.value}'; "
        f"retaining '{base.value}' — grounded-facts pattern will be used"
    )


def apply_lesson_pattern(
    sections: list[SectionSpec],
    pattern: LessonPattern,
) -> list[SectionSpec]:
    """Filter ``sections`` through the lesson pattern's blocked list.

    Any section whose kind is in ``pattern.blocked`` is set to EMPTY status
    (not removed, to preserve the TutorPlan's fixed slot structure). This
    ensures the lesson shape is driven by question type, not by what exists.
    """
    out: list[SectionSpec] = []
    for spec in sections:
        if pattern.is_blocked(spec.kind):
            # Replace with an explicit EMPTY — never drop the slot silently.
            out.append(SectionSpec(
                kind=spec.kind,
                status=SectionStatus.EMPTY,
                note=f"Section blocked by lesson pattern for this question type.",
            ))
        else:
            out.append(spec)
    return out


def _lead_section_for(
    strategy: TeachingStrategyKind, pattern: LessonPattern
) -> SectionKind | None:
    """Return the lead (first required) section for ``strategy``, respecting blocked."""
    template = _TEMPLATES.get(strategy, ())
    for kind in template:
        if not pattern.is_blocked(kind):
            return kind
    return None
