"""Tests for the LocalVectorStore cache backend."""

from backend.retrieval.vectorstore.local import LocalVectorStore
from backend.retrieval.vectorstore.base import VectorRecord


def _store():
    s = LocalVectorStore()
    s.add([
        VectorRecord(id="a", vector=[1.0, 0.0], payload={"subject": "physics"}),
        VectorRecord(id="b", vector=[0.0, 1.0], payload={"subject": "physics"}),
        VectorRecord(id="c", vector=[1.0, 1.0], payload={"subject": "chemistry"}),
    ])
    return s


def test_search_ranks_by_cosine():
    hits = _store().search([1.0, 0.0], top_k=3)
    assert hits[0].id == "a"  # exact direction match ranks first


def test_top_k_bounds():
    assert _store().search([1.0, 0.0], top_k=0) == []
    assert len(_store().search([1.0, 1.0], top_k=2)) == 2


def test_deterministic_tiebreak_by_id():
    s = LocalVectorStore()
    s.add([
        VectorRecord(id="z", vector=[1.0, 0.0]),
        VectorRecord(id="a", vector=[1.0, 0.0]),
        VectorRecord(id="m", vector=[1.0, 0.0]),
    ])
    ids = [h.id for h in s.search([1.0, 0.0], top_k=3)]
    assert ids == ["a", "m", "z"]  # equal scores -> id ascending


def test_payload_filter():
    hits = _store().search([1.0, 1.0], top_k=5, payload_filter={"subject": "chemistry"})
    assert [h.id for h in hits] == ["c"]


def test_delete_and_update():
    s = _store()
    s.delete(["a"])
    assert all(h.id != "a" for h in s.search([1.0, 0.0], top_k=5))
    s.update([VectorRecord(id="b", vector=[1.0, 0.0])])
    assert s.search([1.0, 0.0], top_k=1)[0].id == "b"


def test_save_load_roundtrip(tmp_path):
    s = _store()
    path = tmp_path / "store.json"
    s.save(path)
    loaded = LocalVectorStore.load(path)
    assert loaded.search([1.0, 0.0], top_k=1)[0].id == "a"
