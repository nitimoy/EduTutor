"""Deterministic personalization rules (mirrors ``retrieval/routing/rules.py``).

A rule is ``(name, priority, axis, predicate, build)``: when ``predicate(ctx)`` is true and
the rule's ``axis`` hasn't already been claimed, its ``build(ctx)`` decision is applied.
Rules are evaluated by **priority ascending, then declaration order** (deterministic
tie-break). Predicates are pure functions of a :class:`PersonalizationContext` — no ML, no
LLM, no time. Every ``SectionOp`` targets only sections that exist in the source plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from backend.student.learning_state import LearningState
from backend.student.models import (
    Depth,
    DifficultyPreference,
    DifficultyTarget,
    Emphasis,
    ExamplePreference,
    ExplanationPreference,
    OpKind,
    PacePreference,
    PersonalizationAction,
    PersonalizationDecision,
    SectionDirective,
    SectionOp,
    StudentProfile,
)
from backend.tutor.models import SectionKind, TeachingPlan

# Mastery thresholds for rule predicates.
LOW_MASTERY = 0.3
HIGH_MASTERY = 0.8


class PersonalizationContext:
    """Precomputed, read-only view a rule predicate/builder needs."""

    def __init__(self, profile: StudentProfile, source_plan: TeachingPlan) -> None:
        self.profile = profile
        self.state = profile.state
        self.prefs = profile.preferences
        self.source_plan = source_plan
        self.primary_id = source_plan.primary_concept_id
        self.primary_state: LearningState = self.state.state_of(self.primary_id)
        self.primary_mastery: float = self.state.mastery_of(self.primary_id)
        self.present_kinds: frozenset[SectionKind] = frozenset(
            s.kind for s in source_plan.sections
        )

    def has(self, kind: SectionKind) -> bool:
        return kind in self.present_kinds

    def ops_for_present(self, *ops: SectionOp) -> list[SectionOp]:
        """Keep only ops targeting a section that exists in the plan (no-invention)."""
        return [op for op in ops if self.has(op.section)]


@dataclass(frozen=True)
class PersonalizationRule:
    name: str
    priority: int
    axis: str
    predicate: Callable[[PersonalizationContext], bool]
    build: Callable[[PersonalizationContext], PersonalizationDecision]


@dataclass(frozen=True)
class RulePolicy:
    name: str
    rules: tuple[PersonalizationRule, ...] = field(default_factory=tuple)


# --- rule builders ------------------------------------------------------------
def _prereq_gap_review(ctx: PersonalizationContext) -> PersonalizationDecision:
    gaps = ", ".join(ctx.state.prerequisite_gaps[:5]) or "unspecified"
    return PersonalizationDecision(
        action=PersonalizationAction.INSERT_PREREQUISITE_REVIEW,
        reason=f"student has prerequisite gaps ({gaps}); surface prerequisites first",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.PREREQUISITES)),
        directives={SectionKind.PREREQUISITES: SectionDirective(review=True, emphasis=Emphasis.EMPHASIZE)},
    )


def _forgotten_revision(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.RECOMMEND_REVISION,
        reason=f"primary concept state is '{ctx.primary_state.value}'; lead with a recap",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.SUMMARY)),
        directives={SectionKind.SUMMARY: SectionDirective(review=True, emphasis=Emphasis.EMPHASIZE)},
    )


def _misconception_review(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.RECOMMEND_REVISION,
        reason="student has a recorded misconception on this concept; re-emphasize the core explanation",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.MAIN_EXPLANATION)),
        directives={SectionKind.MAIN_EXPLANATION: SectionDirective(review=True, emphasis=Emphasis.EMPHASIZE)},
    )


def _lower_difficulty(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.LOWER_DIFFICULTY,
        reason=f"low mastery ({ctx.primary_mastery:.2f}) or easy preference; suppress advanced material",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.SUPPRESS, section=SectionKind.PROOF)),
        directives={SectionKind.MAIN_EXPLANATION: SectionDirective(difficulty_target=DifficultyTarget.EASY)},
    )


def _raise_difficulty(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.RAISE_DIFFICULTY,
        reason=f"high mastery ({ctx.primary_mastery:.2f}) or challenging preference; lead with advanced material",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.PROOF)),
        directives={
            SectionKind.PROOF: SectionDirective(emphasis=Emphasis.EMPHASIZE),
            SectionKind.MAIN_EXPLANATION: SectionDirective(difficulty_target=DifficultyTarget.CHALLENGING),
        },
    )


def _more_examples(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.INCREASE_WORKED_EXAMPLES,
        reason="low mastery or 'many examples' preference; surface and expand worked examples",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.WORKED_EXAMPLE)),
        directives={SectionKind.WORKED_EXAMPLE: SectionDirective(emphasis=Emphasis.EMPHASIZE, depth=Depth.EXPAND)},
    )


def _fewer_examples(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.ADJUST_EMPHASIS,
        reason="'few examples' preference; de-emphasize worked examples",
        directives={SectionKind.WORKED_EXAMPLE: SectionDirective(emphasis=Emphasis.DEEMPHASIZE)},
    )


def _condense_main(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.ADJUST_DEPTH,
        reason="high mastery or fast pace; condense the main explanation and postpone prerequisites",
        ops=ctx.ops_for_present(SectionOp(op=OpKind.MOVE_TO_BACK, section=SectionKind.PREREQUISITES)),
        directives={SectionKind.MAIN_EXPLANATION: SectionDirective(depth=Depth.CONDENSE)},
    )


def _expand_main(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.ADJUST_DEPTH,
        reason="'detailed' explanation preference; expand the main explanation",
        directives={SectionKind.MAIN_EXPLANATION: SectionDirective(depth=Depth.EXPAND)},
    )


def _concise_main(ctx: PersonalizationContext) -> PersonalizationDecision:
    return PersonalizationDecision(
        action=PersonalizationAction.ADJUST_DEPTH,
        reason="'concise' explanation preference; condense the main explanation",
        directives={SectionKind.MAIN_EXPLANATION: SectionDirective(depth=Depth.CONDENSE)},
    )


# --- the default policy (declaration order = tie-break within equal priority) --
DEFAULT_POLICY = RulePolicy(
    name="default",
    rules=(
        PersonalizationRule(
            "prereq_gap_review", 10, "prereq",
            lambda c: bool(c.state.prerequisite_gaps) and c.has(SectionKind.PREREQUISITES),
            _prereq_gap_review),
        PersonalizationRule(
            "forgotten_recommend_revision", 20, "review",
            lambda c: c.primary_state in (LearningState.FORGOTTEN, LearningState.NEEDS_REVIEW),
            _forgotten_revision),
        PersonalizationRule(
            "misconception_review", 25, "review",
            lambda c: c.state.has_misconception(c.primary_id),
            _misconception_review),
        PersonalizationRule(
            "low_mastery_lower_difficulty", 30, "difficulty",
            lambda c: c.primary_mastery < LOW_MASTERY or c.prefs.difficulty == DifficultyPreference.EASY,
            _lower_difficulty),
        PersonalizationRule(
            "challenging_raise_difficulty", 30, "difficulty",
            lambda c: c.prefs.difficulty == DifficultyPreference.CHALLENGING or c.primary_mastery >= HIGH_MASTERY,
            _raise_difficulty),
        PersonalizationRule(
            "low_mastery_more_examples", 40, "examples",
            lambda c: c.primary_mastery < LOW_MASTERY or c.prefs.example == ExamplePreference.MANY,
            _more_examples),
        PersonalizationRule(
            "few_examples_deemphasize", 45, "examples",
            lambda c: c.prefs.example == ExamplePreference.FEW,
            _fewer_examples),
        PersonalizationRule(
            "high_mastery_condense", 50, "depth:main",
            lambda c: c.primary_mastery >= HIGH_MASTERY or c.prefs.pace == PacePreference.FAST,
            _condense_main),
        PersonalizationRule(
            "detailed_pref_expand", 55, "depth:main",
            lambda c: c.prefs.explanation == ExplanationPreference.DETAILED,
            _expand_main),
        PersonalizationRule(
            "concise_pref_condense", 55, "depth:main",
            lambda c: c.prefs.explanation == ExplanationPreference.CONCISE,
            _concise_main),
    ),
)
