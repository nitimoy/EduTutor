"""Apply a TeachingPlanDelta to produce a personalized TeachingPlan.

This is the only component that *executes* a delta — keeping ``TeachingPlanDelta`` pure
data. It reorders and suppresses **existing** sections only; it never edits section
content (``item_refs``), so it can never invent knowledge. The delta's ``source_plan`` is
never mutated (a deep copy is edited).
"""

from __future__ import annotations

from backend.student.models import (
    OpKind,
    SectionDirective,
    TeachingPlanDelta,
)
from backend.tutor.models import SectionKind, SectionSpec, TeachingPlan


class TeachingPlanApplier:
    """Turn a delta into a new, personalized :class:`TeachingPlan`."""

    def apply(self, delta: TeachingPlanDelta) -> TeachingPlan:
        """Return a new plan with the delta's structural ops applied, in order.

        Deterministic. ``move_to_front`` / ``move_to_back`` are stable relative to the
        other (untouched) sections; ``suppress`` removes; an op on an absent section kind
        is a no-op.
        """
        plan = delta.source_plan.model_copy(deep=True)
        sections: list[SectionSpec] = list(plan.sections)

        for decision in delta.decisions:
            for op in decision.ops:
                sections = _apply_op(sections, op.op, op.section)

        plan.sections = sections
        return plan

    def merged_directives(
        self, delta: TeachingPlanDelta
    ) -> dict[SectionKind, SectionDirective]:
        """Fold every decision's directives into one map (later decision wins per kind)."""
        merged: dict[SectionKind, SectionDirective] = {}
        for decision in delta.decisions:
            for kind, directive in decision.directives.items():
                merged[kind] = directive
        return merged


def _apply_op(
    sections: list[SectionSpec], op: OpKind, kind: SectionKind
) -> list[SectionSpec]:
    """Apply one structural op over sections, matching by kind. Pure (returns a new list)."""
    index = next((i for i, s in enumerate(sections) if s.kind == kind), None)
    if index is None:
        return sections  # op on an absent section is a no-op
    target = sections[index]
    rest = sections[:index] + sections[index + 1:]
    if op == OpKind.SUPPRESS:
        return rest
    if op == OpKind.MOVE_TO_FRONT:
        return [target] + rest
    if op == OpKind.MOVE_TO_BACK:
        return rest + [target]
    return sections
