"""Tests for teaching-strategy selection and the data-aware fallback."""

import pytest

from backend.tutor.models import (
    EducationalIntent,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingStrategyKind,
)
from backend.tutor.organizer import OrganizedContext
from backend.tutor.strategy import base_strategy, select_strategy, template_for


def _ctx(*present_kinds: SectionKind) -> OrganizedContext:
    sections = {
        k: SectionSpec(kind=k, status=SectionStatus.PRESENT) for k in present_kinds
    }
    return OrganizedContext(primary_concept_id="c1", sections=sections)


@pytest.mark.parametrize("intent,strategy", [
    (EducationalIntent.DEFINITION, TeachingStrategyKind.CONCEPT_EXPLANATION),
    (EducationalIntent.EXPLANATION, TeachingStrategyKind.CONCEPT_EXPLANATION),
    (EducationalIntent.COMPARISON, TeachingStrategyKind.COMPARE_AND_CONTRAST),
    (EducationalIntent.PREREQUISITE, TeachingStrategyKind.PREREQUISITE_PATHWAY),
    (EducationalIntent.WORKED_EXAMPLE, TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH),
    (EducationalIntent.FORMULA, TeachingStrategyKind.FORMULA_EXPLANATION),
    (EducationalIntent.PROOF, TeachingStrategyKind.STEP_BY_STEP_DERIVATION),
    (EducationalIntent.APPLICATION, TeachingStrategyKind.WORKED_EXAMPLE_WALKTHROUGH),
    (EducationalIntent.REVISION, TeachingStrategyKind.REVISION_SUMMARY),
])
def test_intent_to_strategy_map(intent, strategy):
    assert base_strategy(intent) == strategy


def test_every_strategy_has_a_template_with_a_lead():
    for strategy in TeachingStrategyKind:
        template = template_for(strategy)
        assert len(template) >= 1


def test_no_fallback_when_lead_present():
    ctx = _ctx(SectionKind.MAIN_EXPLANATION)
    strategy, note = select_strategy(EducationalIntent.DEFINITION, ctx)
    assert strategy == TeachingStrategyKind.CONCEPT_EXPLANATION and note == ""


def test_proof_present_keeps_derivation():
    ctx = _ctx(SectionKind.PROOF, SectionKind.MAIN_EXPLANATION, SectionKind.SUMMARY)
    strategy, note = select_strategy(EducationalIntent.PROOF, ctx)
    assert strategy == TeachingStrategyKind.STEP_BY_STEP_DERIVATION and note == ""


def test_proof_absent_falls_back_to_concept_explanation():
    ctx = _ctx(SectionKind.MAIN_EXPLANATION, SectionKind.SUMMARY)  # no proof
    strategy, note = select_strategy(EducationalIntent.PROOF, ctx)
    assert strategy == TeachingStrategyKind.CONCEPT_EXPLANATION and note


def test_fallback_ends_at_revision_summary_when_only_summary_present():
    ctx = _ctx(SectionKind.SUMMARY)  # nothing else supported
    strategy, note = select_strategy(EducationalIntent.DEFINITION, ctx)
    assert strategy == TeachingStrategyKind.REVISION_SUMMARY and note


def test_compare_and_contrast_is_never_a_fallback_target():
    # comparison supported but the intent is a definition with no main explanation:
    # the fallback must NOT hijack into compare_and_contrast.
    ctx = _ctx(SectionKind.COMPARISON, SectionKind.SUMMARY)
    strategy, _ = select_strategy(EducationalIntent.DEFINITION, ctx)
    assert strategy != TeachingStrategyKind.COMPARE_AND_CONTRAST
    assert strategy == TeachingStrategyKind.REVISION_SUMMARY


def test_no_supported_section_retains_base_strategy():
    ctx = _ctx()  # empty context (e.g. empty retrieval)
    strategy, note = select_strategy(EducationalIntent.PROOF, ctx)
    assert strategy == TeachingStrategyKind.STEP_BY_STEP_DERIVATION and note
