"""Reproducibility tests: semantic outputs must be byte-stable across runs.

These guard the "deterministic compiler" contract. They build small fixtures
and assert that the relationship engine and knowledge-index builder emit the
exact same ordered output on repeated invocations, independent of dict/set
iteration order.
"""

from backend.compiler.models import Book, EducationalIR, EducationalObject
from backend.semantic.concepts.concept_models import (
    Concept,
    ConceptIndex,
    ConceptReference,
)
from backend.semantic.relationships.relationship_engine import RelationshipEngine
from backend.semantic.relationships.relationship_models import RelationshipIndex
from backend.semantic.reasoning.reasoning_models import (
    ConceptCoverage,
    ConceptReasoning,
    ReasoningIndex,
    ReasoningValidationReport,
)
from backend.retrieval.index.builder import KnowledgeIndexBuilder


def _fixture():
    book = Book(id="book.1", title="Test", subject="physics", source_pdf="t.pdf", page_count=5)
    objects = []
    for i in range(12):
        objects.append(
            EducationalObject(
                id=f"obj.{i}",
                type="paragraph",
                subject="physics",
                book="Test",
                chapter="Chapter 1",
                page=1 + i // 4,
                reading_order=i,
                text=f"Electric charge and electric field discussion number {i}.",
                confidence=0.8,
            )
        )
    book.objects = objects
    ir = EducationalIR(book=book, formulas=[], tables=[], figures=[])

    concepts = [
        Concept(id="concept.charge", name="Electric Charge", subject="physics", book="Test", chapter="Chapter 1"),
        Concept(id="concept.field", name="Electric Field", subject="physics", book="Test",
                chapter="Chapter 1", parent_id="concept.charge"),
        Concept(id="concept.flux", name="Electric Flux", subject="physics", book="Test",
                chapter="Chapter 1", parent_id="concept.field"),
    ]
    refs = [
        ConceptReference(concept_id="concept.charge", object_id=f"obj.{i}",
                         object_type="paragraph", link_reason="section_scope")
        for i in range(12)
    ]
    concept_index = ConceptIndex(book_id="book.1", concepts=concepts, references=refs, unlinked_object_ids=[])
    return ir, concept_index


def test_relationship_engine_is_order_stable():
    ir, concept_index = _fixture()
    runs = []
    for _ in range(3):
        idx = RelationshipEngine().build(ir, concept_index)
        runs.append([(r.source_id, r.target_id, r.relationship_type) for r in idx.relationships])
    assert runs[0] == runs[1] == runs[2]
    # And the ordering is the canonical sorted ordering.
    assert runs[0] == sorted(runs[0])


def test_knowledge_index_is_order_stable():
    ir, concept_index = _fixture()
    rel_index = RelationshipEngine().build(ir, concept_index)
    reasoning = ReasoningIndex(
        book_id="book.1",
        concept_reasoning={
            c.id: ConceptReasoning(
                concept_id=c.id,
                required_prerequisites=[],
                teaching_sequence=[],
                skills_developed=[],
                learning_outcomes=None,
                difficulty="Easy",
                coverage=ConceptCoverage(),
            )
            for c in concept_index.concepts
        },
        validation_report=ReasoningValidationReport(),
    )
    runs = []
    for _ in range(3):
        ki = KnowledgeIndexBuilder().build(ir, concept_index, rel_index, reasoning)
        runs.append([
            (d.concept_id, tuple(d.prerequisites), tuple(d.related_concepts), tuple(d.next_topics))
            for d in ki.documents
        ])
    assert runs[0] == runs[1] == runs[2]


def test_no_subject_specific_edge_methods():
    """The eval-gaming subject-specific inference method must not reappear."""
    ir, concept_index = _fixture()
    idx = RelationshipEngine().build(ir, concept_index)
    methods = {r.inference_method for r in idx.relationships}
    assert "math_semantics" not in methods


def test_relationship_records_are_seed_independent():
    """Full relationship records (incl. evidence text) must not depend on the
    process hash seed — the class of bug the audit found in relationships.json.

    We simulate hash-seed variation by shuffling concept/reference input order;
    a correct implementation normalizes it away.
    """
    ir, concept_index = _fixture()
    baseline = RelationshipEngine().build(ir, concept_index)
    base_records = [
        (r.source_id, r.target_id, r.relationship_type, r.evidence) for r in baseline.relationships
    ]

    shuffled = ConceptIndex(
        book_id=concept_index.book_id,
        concepts=list(reversed(concept_index.concepts)),
        references=list(reversed(concept_index.references)),
        unlinked_object_ids=[],
    )
    other = RelationshipEngine().build(ir, shuffled)
    other_records = [
        (r.source_id, r.target_id, r.relationship_type, r.evidence) for r in other.relationships
    ]
    assert base_records == other_records
