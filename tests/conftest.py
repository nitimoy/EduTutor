"""Shared fixtures for generation-layer tests."""

import pytest

from backend.tutor.models import (
    Citation,
    EducationalIntent,
    PlanSection,
    SectionKind,
    SectionStatus,
    TeachingStrategyKind,
    TutorPlan,
)


def _cit(cid: str) -> Citation:
    return Citation(concept_id=cid, concept_name=cid.upper(),
                    source_field="definition_texts", locator="0")


def _present(kind: SectionKind, items, cids) -> PlanSection:
    return PlanSection(kind=kind, status=SectionStatus.PRESENT, items=list(items),
                       citations=[_cit(c) for c in cids])


def _empty(kind: SectionKind) -> PlanSection:
    return PlanSection(kind=kind, status=SectionStatus.EMPTY)


@pytest.fixture
def tutor_plan() -> TutorPlan:
    """A fixed synthetic TutorPlan: 4 present sections (in slot order) + empties."""
    return TutorPlan(
        query="What is c1?",
        intent=EducationalIntent.DEFINITION,
        strategy=TeachingStrategyKind.CONCEPT_EXPLANATION,
        primary_concept_id="c1", primary_concept_name="C1",
        prerequisites=_present(SectionKind.PREREQUISITES, ["C2"], ["c2"]),
        main_explanation=_present(SectionKind.MAIN_EXPLANATION, ["C1 is the first thing."], ["c1"]),
        formula=_empty(SectionKind.FORMULA),
        worked_example=_present(SectionKind.WORKED_EXAMPLE, ["Step one.", "Step two."], ["c1"]),
        proof=_empty(SectionKind.PROOF),
        exercise=_empty(SectionKind.EXERCISE),
        comparison=_empty(SectionKind.COMPARISON),
        related_concepts=_empty(SectionKind.RELATED_CONCEPTS),
        suggested_next_topics=_empty(SectionKind.NEXT_TOPICS),
        summary=_present(SectionKind.SUMMARY, ["C1 recap."], ["c1"]),
        references=[_cit("c1"), _cit("c2")],
    )
