"""Tests for DenseRetrievalStrategy (hashing provider + local store)."""

from backend.retrieval.embedding.builder import EmbeddingBuilder
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import HashingEmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex
from backend.retrieval.strategies.base import RetrievalContext
from backend.retrieval.strategies.dense import DenseRetrievalStrategy
from backend.retrieval.vectorstore.local import LocalVectorStore


def _doc(cid, name, subject="physics", **kw):
    return KnowledgeDocument(concept_id=cid, name=name, subject=subject, chapter="Chapter 1", **kw)


def _ki():
    return KnowledgeIndex(book_id="book.1", documents=[
        _doc("c.charge", "Electric Charge", definition_texts=["electric charge is a property of matter"]),
        _doc("c.field", "Electric Field", definition_texts=["electric field is a region of force"]),
        _doc("c.dipole", "Electric Dipole", definition_texts=["an electric dipole has two poles"]),
        _doc("c.solution", "Solutions", subject="chemistry", definition_texts=["a homogeneous mixture"]),
    ])


def _dense(tmp_path, dimension=128):
    ki = _ki()
    index_path = tmp_path / "knowledge_index.json"
    index_path.write_text(ki.model_dump_json())
    root = tmp_path / "embeddings"
    provider = HashingEmbeddingProvider(dimension=dimension)
    EmbeddingIndex(root).build(ki, provider, EmbeddingBuilder())
    return DenseRetrievalStrategy.build(index_path, root, provider, LocalVectorStore())


def test_returns_searchresult_with_document(tmp_path):
    dense = _dense(tmp_path)
    results = dense.search("electric charge", top_k=3)
    assert results
    assert hasattr(results[0], "score") and hasattr(results[0], "document")
    assert isinstance(results[0].document, KnowledgeDocument)


def test_ranks_relevant_concept_first(tmp_path):
    dense = _dense(tmp_path)
    assert dense.search("electric charge", top_k=4)[0].document.concept_id == "c.charge"
    assert dense.search("electric dipole", top_k=4)[0].document.concept_id == "c.dipole"


def test_determinism(tmp_path):
    dense = _dense(tmp_path)
    a = [(r.document.concept_id, r.score) for r in dense.search("electric field", top_k=4)]
    b = [(r.document.concept_id, r.score) for r in dense.search("electric field", top_k=4)]
    assert a == b


def test_top_k_and_empty_query(tmp_path):
    dense = _dense(tmp_path)
    assert len(dense.search("electric", top_k=2)) <= 2
    assert dense.search("electric", top_k=0) == []
    assert dense.search("   ", top_k=5) == []


def test_batch_search_parity(tmp_path):
    dense = _dense(tmp_path)
    queries = ["electric charge", "electric dipole", "solutions"]
    batched = dense.batch_search(queries, top_k=3)
    for query, batch_result in zip(queries, batched):
        single = dense.search(query, top_k=3)
        assert [(r.document.concept_id, r.score) for r in batch_result] == \
               [(r.document.concept_id, r.score) for r in single]


def test_context_filter_by_subject(tmp_path):
    dense = _dense(tmp_path)
    results = dense.search("electric", top_k=5, context=RetrievalContext(subject="chemistry"))
    assert all(r.document.subject == "chemistry" for r in results)
