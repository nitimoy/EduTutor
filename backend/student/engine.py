"""The Student Model: deterministic, rule-based personalization.

Given a frozen ``TeachingPlan`` and a ``StudentProfile``, it produces an immutable
``TeachingPlanDelta`` — an ordered, explainable patch. It never mutates the input plan and
never invents content (rules only reorder/suppress existing sections + attach directive
metadata). Rules fire by **priority ascending, then declaration order**, with **one
decision per axis** (later same-axis rules are skipped and noted).
"""

from __future__ import annotations

from typing import Optional

from backend.student.applier import TeachingPlanApplier
from backend.student.models import StudentProfile, TeachingPlanDelta
from backend.student.rules import DEFAULT_POLICY, PersonalizationContext, RulePolicy
from backend.tutor.models import TeachingPlan, TutorPlan


class StudentModel:
    """Personalize a TeachingPlan for a particular student, deterministically."""

    def __init__(self, policy: RulePolicy = DEFAULT_POLICY) -> None:
        self._policy = policy

    def personalize(
        self, source_plan: TeachingPlan, profile: StudentProfile
    ) -> TeachingPlanDelta:
        ctx = PersonalizationContext(profile, source_plan)

        # Priority ascending, then declaration order (Python's sort is stable).
        ordered = sorted(self._policy.rules, key=lambda r: r.priority)

        claimed_axes: set[str] = set()
        decisions = []
        notes: list[str] = []
        for rule in ordered:
            if not rule.predicate(ctx):
                continue
            if rule.axis in claimed_axes:
                notes.append(
                    f"rule '{rule.name}' (priority {rule.priority}) skipped: "
                    f"axis '{rule.axis}' already decided"
                )
                continue
            decision = rule.build(ctx).model_copy(
                update={"rule_name": rule.name, "priority": rule.priority}
            )
            decisions.append(decision)
            claimed_axes.add(rule.axis)

        return TeachingPlanDelta(
            source_plan=source_plan,
            decisions=tuple(decisions),
            profile=profile,
            notes=tuple(notes),
        )

    def personalize_and_compose(
        self,
        source_plan: TeachingPlan,
        profile: StudentProfile,
        results,
        brain,
        applier: Optional[TeachingPlanApplier] = None,
    ) -> TutorPlan:
        """Full path: personalize → apply the delta → frozen composer → TutorPlan."""
        applier = applier or TeachingPlanApplier()
        delta = self.personalize(source_plan, profile)
        personalized = applier.apply(delta)
        return brain.compose_from(personalized, results)
