"""Tests for the Context Organizer."""

from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult
from backend.tutor.models import SectionKind, SectionStatus
from backend.tutor.organizer import organize
from backend.tutor.repository import KnowledgeRepository, RecoveredObject


def _doc(cid, name, **kw):
    return KnowledgeDocument(concept_id=cid, name=name, subject="physics", chapter="Ch1", **kw)


def _results(*docs):
    return [SearchResult(score=float(len(docs) - i), document=d) for i, d in enumerate(docs)]


class _Repo(KnowledgeRepository):
    """Fake repo that returns one object per requested kind."""

    def get_concept(self, concept_id):
        return None

    def recover_objects(self, concept_id, kinds):
        return [RecoveredObject(object_id=f"{k}1", type=k, text=f"{k} text") for k in kinds]


def test_empty_results_yield_empty_context():
    ctx = organize([])
    assert ctx.primary_concept_id is None
    assert ctx.sections == {}


def test_primary_and_supporting_selection():
    ctx = organize(_results(_doc("c1", "A"), _doc("c2", "B"), _doc("c3", "C")))
    assert ctx.primary_concept_id == "c1"
    assert ctx.supporting_concept_ids == ["c2", "c3"]


def test_definitions_and_formulas_and_examples_present():
    doc = _doc("c1", "A", definition_texts=["def"], formula_latex=["x=1"], example_texts=["ex"])
    ctx = organize(_results(doc))
    assert ctx.is_supported(SectionKind.MAIN_EXPLANATION)
    assert ctx.is_supported(SectionKind.FORMULA)
    assert ctx.is_supported(SectionKind.WORKED_EXAMPLE)


def test_empty_field_is_empty_status():
    ctx = organize(_results(_doc("c1", "A")))  # no definitions/formulas/examples
    assert ctx.section(SectionKind.MAIN_EXPLANATION).status == SectionStatus.EMPTY
    assert ctx.section(SectionKind.FORMULA).status == SectionStatus.EMPTY


def test_prerequisites_and_related_and_next_from_names():
    doc = _doc("c1", "A", prerequisites=["P"], related_concepts=["R"], next_topics=["N"])
    ctx = organize(_results(doc))
    assert ctx.section(SectionKind.PREREQUISITES).item_refs[0].text == "P"
    assert ctx.is_supported(SectionKind.RELATED_CONCEPTS)
    assert ctx.is_supported(SectionKind.NEXT_TOPICS)


def test_proof_and_exercise_unsupported_without_repository():
    ctx = organize(_results(_doc("c1", "A")))
    assert ctx.section(SectionKind.PROOF).status == SectionStatus.UNSUPPORTED_BY_INDEX
    assert ctx.section(SectionKind.EXERCISE).status == SectionStatus.UNSUPPORTED_BY_INDEX


def test_proof_and_exercise_present_with_repository():
    ctx = organize(_results(_doc("c1", "A")), _Repo())
    assert ctx.is_supported(SectionKind.PROOF)
    assert ctx.is_supported(SectionKind.EXERCISE)
    # recovered proof object is cited to its object id
    ref = ctx.section(SectionKind.PROOF).item_refs[0]
    assert ref.object_type == "proof" and ref.locator == "proof1"


def test_recovered_theorem_property_fold_into_main_explanation():
    ctx = organize(_results(_doc("c1", "A", definition_texts=["def"])), _Repo())
    kinds = [r.object_type for r in ctx.section(SectionKind.MAIN_EXPLANATION).item_refs if r.object_type]
    assert "theorem" in kinds and "property" in kinds


def test_comparison_present_with_two_concepts_empty_with_one():
    assert organize(_results(_doc("c1", "A"), _doc("c2", "B"))).is_supported(SectionKind.COMPARISON)
    assert organize(_results(_doc("c1", "A"))).section(SectionKind.COMPARISON).status == SectionStatus.EMPTY


def test_summary_always_present_with_primary():
    ctx = organize(_results(_doc("c1", "A", difficulty="Easy")))
    assert ctx.is_supported(SectionKind.SUMMARY)
    assert "Easy" in ctx.section(SectionKind.SUMMARY).item_refs[0].text


def test_no_synthesized_application_section_kind():
    # Section vocabulary is compiler-backed only; there is no 'application' kind.
    assert not any(k.value == "application" for k in SectionKind)
