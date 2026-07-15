"""Tests for TeachingPlanDelta immutability and TeachingPlanApplier."""

import pytest
from pydantic import ValidationError

from backend.student.applier import TeachingPlanApplier
from backend.student.models import (
    Emphasis,
    OpKind,
    PersonalizationAction,
    PersonalizationDecision,
    SectionDirective,
    SectionOp,
    StudentProfile,
    TeachingPlanDelta,
)
from backend.tutor.models import (
    EducationalIntent,
    SectionKind,
    SectionSpec,
    SectionStatus,
    ItemRef,
    TeachingPlan,
    TeachingStrategyKind,
)


def _plan():
    kinds = (SectionKind.MAIN_EXPLANATION, SectionKind.PREREQUISITES, SectionKind.PROOF,
             SectionKind.WORKED_EXAMPLE, SectionKind.SUMMARY)
    return TeachingPlan(
        query="q", intent=EducationalIntent.PROOF,
        strategy=TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
        primary_concept_id="c1", primary_concept_name="Alpha",
        sections=[SectionSpec(kind=k, status=SectionStatus.PRESENT,
                              item_refs=[ItemRef(concept_id="c1", concept_name="Alpha",
                                                 source_field="definition_texts", locator="0",
                                                 text=f"{k.value} text")])
                  for k in kinds])


def _delta(plan, *decisions):
    return TeachingPlanDelta(source_plan=plan, decisions=tuple(decisions),
                             profile=StudentProfile())


def _decision(action, *ops, directives=None):
    return PersonalizationDecision(action=action, reason="test", ops=list(ops),
                                   directives=directives or {})


def test_delta_is_immutable():
    delta = _delta(_plan())
    with pytest.raises((ValidationError, TypeError)):
        delta.decisions = ()


def test_apply_moves_section_to_front():
    plan = _plan()
    delta = _delta(plan, _decision(PersonalizationAction.INCREASE_WORKED_EXAMPLES,
                                   SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.WORKED_EXAMPLE)))
    applied = TeachingPlanApplier().apply(delta)
    assert applied.sections[0].kind == SectionKind.WORKED_EXAMPLE


def test_apply_suppresses_section():
    plan = _plan()
    delta = _delta(plan, _decision(PersonalizationAction.SUPPRESS_ADVANCED,
                                   SectionOp(op=OpKind.SUPPRESS, section=SectionKind.PROOF)))
    applied = TeachingPlanApplier().apply(delta)
    assert all(s.kind != SectionKind.PROOF for s in applied.sections)


def test_apply_moves_section_to_back():
    plan = _plan()
    delta = _delta(plan, _decision(PersonalizationAction.ADJUST_DEPTH,
                                   SectionOp(op=OpKind.MOVE_TO_BACK, section=SectionKind.PREREQUISITES)))
    applied = TeachingPlanApplier().apply(delta)
    assert applied.sections[-1].kind == SectionKind.PREREQUISITES


def test_op_on_absent_section_is_noop():
    plan = _plan()
    delta = _delta(plan, _decision(PersonalizationAction.RECOMMEND_REVISION,
                                   SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.COMPARISON)))
    applied = TeachingPlanApplier().apply(delta)
    assert [s.kind for s in applied.sections] == [s.kind for s in plan.sections]


def test_apply_never_mutates_source():
    plan = _plan()
    before = plan.model_dump_json()
    delta = _delta(plan, _decision(PersonalizationAction.SUPPRESS_ADVANCED,
                                   SectionOp(op=OpKind.SUPPRESS, section=SectionKind.PROOF)))
    TeachingPlanApplier().apply(delta)
    assert plan.model_dump_json() == before


def test_no_invention_content_identical_after_apply():
    plan = _plan()
    delta = _delta(plan, _decision(PersonalizationAction.INCREASE_WORKED_EXAMPLES,
                                   SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.WORKED_EXAMPLE)))
    applied = TeachingPlanApplier().apply(delta)
    source_by_kind = {s.kind: s.item_refs for s in plan.sections}
    for s in applied.sections:
        assert s.item_refs == source_by_kind[s.kind]  # text untouched
    assert set(s.kind for s in applied.sections).issubset(set(source_by_kind))


def test_merged_directives_later_decision_wins():
    plan = _plan()
    d1 = _decision(PersonalizationAction.ADJUST_EMPHASIS,
                   directives={SectionKind.WORKED_EXAMPLE: SectionDirective(emphasis=Emphasis.DEEMPHASIZE)})
    d2 = _decision(PersonalizationAction.INCREASE_WORKED_EXAMPLES,
                   directives={SectionKind.WORKED_EXAMPLE: SectionDirective(emphasis=Emphasis.EMPHASIZE)})
    merged = TeachingPlanApplier().merged_directives(_delta(plan, d1, d2))
    assert merged[SectionKind.WORKED_EXAMPLE].emphasis == Emphasis.EMPHASIZE


def test_apply_is_deterministic():
    plan = _plan()
    delta = _delta(plan,
                   _decision(PersonalizationAction.INCREASE_WORKED_EXAMPLES,
                             SectionOp(op=OpKind.MOVE_TO_FRONT, section=SectionKind.WORKED_EXAMPLE)),
                   _decision(PersonalizationAction.SUPPRESS_ADVANCED,
                             SectionOp(op=OpKind.SUPPRESS, section=SectionKind.PROOF)))
    a = TeachingPlanApplier().apply(delta).model_dump_json()
    b = TeachingPlanApplier().apply(delta).model_dump_json()
    assert a == b
