"""Tests for the Citation Builder."""

from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult
from backend.tutor.citations import CitationBuilder
from backend.tutor.models import (
    SOURCE_DEFINITION,
    SOURCE_OBJECT,
    SOURCE_PREREQUISITE,
    EducationalIntent,
    ItemRef,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
)


def _doc(cid, name):
    return KnowledgeDocument(concept_id=cid, name=name, subject="physics", chapter="Ch1")


def _plan(*item_refs):
    return TeachingPlan(
        query="q", intent=EducationalIntent.DEFINITION,
        strategy=TeachingStrategyKind.CONCEPT_EXPLANATION, primary_concept_id="c1",
        sections=[SectionSpec(kind=SectionKind.MAIN_EXPLANATION,
                              status=SectionStatus.PRESENT, item_refs=list(item_refs))],
    )


def _builder():
    results = [SearchResult(score=2.0, document=_doc("c1", "Alpha")),
               SearchResult(score=1.0, document=_doc("c2", "Beta"))]
    return CitationBuilder.from_results(results)


def test_content_ref_keeps_its_concept_id():
    plan = _plan(ItemRef(concept_id="c1", concept_name="Alpha",
                         source_field=SOURCE_DEFINITION, locator="0", text="def"))
    cite = _builder().resolve(plan)[0][0]
    assert cite.concept_id == "c1" and cite.source_field == SOURCE_DEFINITION


def test_prerequisite_name_resolves_when_retrieved():
    plan = _plan(ItemRef(concept_id=None, concept_name="Beta",
                         source_field=SOURCE_PREREQUISITE, locator="0", text="Beta"))
    cite = _builder().resolve(plan)[0][0]
    assert cite.concept_id == "c2"  # Beta was retrieved as c2


def test_unresolved_name_yields_none_not_a_fabricated_id():
    plan = _plan(ItemRef(concept_id=None, concept_name="Gamma (not retrieved)",
                         source_field=SOURCE_PREREQUISITE, locator="0", text="Gamma"))
    cite = _builder().resolve(plan)[0][0]
    assert cite.concept_id is None


def test_object_ref_preserves_type_and_locator():
    plan = _plan(ItemRef(concept_id="c1", concept_name="Alpha", source_field=SOURCE_OBJECT,
                         locator="obj-77", object_type="proof", text="Proof text"))
    cite = _builder().resolve(plan)[0][0]
    assert cite.object_type == "proof" and cite.locator == "obj-77" and cite.concept_id == "c1"


def test_resolve_is_aligned_to_sections():
    plan = _plan(
        ItemRef(concept_id="c1", concept_name="Alpha", source_field=SOURCE_DEFINITION, locator="0"),
        ItemRef(concept_id="c1", concept_name="Alpha", source_field=SOURCE_DEFINITION, locator="1"),
    )
    resolved = _builder().resolve(plan)
    assert len(resolved) == 1 and len(resolved[0]) == 2
