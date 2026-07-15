"""Tests for the KnowledgeRepository abstraction and CompiledArtifactRepository."""

import pytest

from backend.compiler.models.educational_ir import Book, EducationalIR, EducationalObject
from backend.semantic.concepts.concept_models import Concept, ConceptIndex
from backend.tutor.repository import (
    CompiledArtifactRepository,
    KnowledgeRepository,
    RecoveredObject,
)


def _obj(oid: str, otype: str, text: str) -> EducationalObject:
    return EducationalObject(id=oid, type=otype, subject="mathematics", book="b", text=text)


def _repo() -> CompiledArtifactRepository:
    concept = Concept(
        id="c.skew", name="Skew Symmetric Matrix", subject="mathematics", book="b",
        chapter="Ch3", proof_ids=["p1", "p2"], exercise_ids=["e1"], theorem_ids=["t1"],
        definition_ids=["d1"],
    )
    index = ConceptIndex(book_id="b", concepts=[concept])
    ir = EducationalIR(book=Book(
        id="b", title="B", subject="mathematics", source_pdf="x.pdf",
        objects=[
            _obj("p1", "proof", "Proof one."),
            _obj("p2", "proof", "Proof two."),
            _obj("e1", "exercise", "Exercise one."),
            _obj("t1", "theorem", "Theorem one."),
            _obj("d1", "definition", "A square matrix A is skew symmetric if A' = -A."),
        ],
    ))
    return CompiledArtifactRepository(index, ir)


def test_recovers_proofs_in_declared_order():
    got = _repo().recover_objects("c.skew", ("proof",))
    assert [o.text for o in got] == ["Proof one.", "Proof two."]
    assert all(isinstance(o, RecoveredObject) and o.type == "proof" for o in got)


def test_recovers_multiple_kinds():
    got = _repo().recover_objects("c.skew", ("proof", "exercise", "theorem"))
    assert [o.type for o in got] == ["proof", "proof", "exercise", "theorem"]


def test_unknown_concept_returns_empty():
    assert _repo().recover_objects("c.nope", ("proof",)) == []


def test_unknown_kind_is_skipped():
    assert _repo().recover_objects("c.skew", ("misconception",)) == []


def test_get_concept():
    repo = _repo()
    assert repo.get_concept("c.skew").name == "Skew Symmetric Matrix"
    assert repo.get_concept("c.nope") is None


def test_read_only_repeated_calls_stable():
    repo = _repo()
    a = repo.recover_objects("c.skew", ("proof",))
    b = repo.recover_objects("c.skew", ("proof",))
    assert [o.object_id for o in a] == [o.object_id for o in b]


def test_custom_repository_is_a_drop_in():
    class FakeRepo(KnowledgeRepository):
        def get_concept(self, concept_id):
            return None

        def recover_objects(self, concept_id, kinds):
            return [RecoveredObject(object_id="x", type="proof", text="fake")]

    repo = FakeRepo()
    assert isinstance(repo, KnowledgeRepository)
    assert repo.recover_objects("anything", ("proof",))[0].text == "fake"
