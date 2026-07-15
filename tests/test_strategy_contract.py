"""Contract + interchangeability tests exercised against every strategy.

Verifies the guarantees in docs/retrieval_strategy_contract.md hold for both
BM25F and Dense, and that either strategy is a drop-in for the frozen
RetrievalEvaluationEngine.
"""

import pytest

from backend.evaluation.retrieval_engine import RetrievalEvaluationEngine
from backend.evaluation.retrieval_models import RetrievalQuery, RetrievalQueryDataset
from backend.retrieval.embedding.builder import EmbeddingBuilder
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import HashingEmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex
from backend.retrieval.strategies.base import RetrievalStrategy
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.retrieval.strategies.dense import DenseRetrievalStrategy
from backend.retrieval.vectorstore.local import LocalVectorStore


def _ki():
    return KnowledgeIndex(book_id="book.1", documents=[
        KnowledgeDocument(concept_id="c.charge", name="Electric Charge", subject="physics",
                          chapter="Chapter 1", definition_texts=["electric charge property of matter"]),
        KnowledgeDocument(concept_id="c.field", name="Electric Field", subject="physics",
                          chapter="Chapter 1", definition_texts=["electric field region of force"]),
        KnowledgeDocument(concept_id="c.dipole", name="Electric Dipole", subject="physics",
                          chapter="Chapter 1", definition_texts=["electric dipole two poles"]),
    ])


@pytest.fixture
def strategies(tmp_path):
    ki = _ki()
    index_path = tmp_path / "knowledge_index.json"
    index_path.write_text(ki.model_dump_json())
    root = tmp_path / "embeddings"
    provider = HashingEmbeddingProvider(dimension=128)
    EmbeddingIndex(root).build(ki, provider, EmbeddingBuilder())
    return {
        "bm25f": BM25FRetrievalStrategy(index_path),
        "dense": DenseRetrievalStrategy.build(index_path, root, provider, LocalVectorStore()),
    }


@pytest.mark.parametrize("name", ["bm25f", "dense"])
def test_is_retrieval_strategy(strategies, name):
    assert isinstance(strategies[name], RetrievalStrategy)


@pytest.mark.parametrize("name,kind", [("bm25f", "lexical"), ("dense", "dense")])
def test_metadata(strategies, name, kind):
    md = strategies[name].metadata()
    assert md.name == name and md.kind == kind and md.deterministic is True


@pytest.mark.parametrize("name", ["bm25f", "dense"])
def test_determinism(strategies, name):
    s = strategies[name]
    a = [(r.document.concept_id, r.score) for r in s.search("electric charge", top_k=3)]
    b = [(r.document.concept_id, r.score) for r in s.search("electric charge", top_k=3)]
    assert a == b


@pytest.mark.parametrize("name", ["bm25f", "dense"])
def test_top_k_bounds_and_empty_query(strategies, name):
    s = strategies[name]
    assert len(s.search("electric", top_k=2)) <= 2
    assert s.search("electric", top_k=0) == []
    assert s.search("the a of", top_k=5) == []  # stop-words only -> nothing


@pytest.mark.parametrize("name", ["bm25f", "dense"])
def test_batch_search_parity(strategies, name):
    s = strategies[name]
    queries = ["electric charge", "electric field"]
    batched = s.batch_search(queries, top_k=3)
    for query, br in zip(queries, batched):
        single = s.search(query, top_k=3)
        assert [r.document.concept_id for r in br] == [r.document.concept_id for r in single]


@pytest.mark.parametrize("name", ["bm25f", "dense"])
def test_interchangeable_through_eval_engine(strategies, name):
    dataset = RetrievalQueryDataset(
        version="1.0", subject="physics", book="book.1",
        queries=[RetrievalQuery(query="electric charge", expected_concept_names=["Electric Charge"])],
    )
    report = RetrievalEvaluationEngine(strategies[name]).evaluate(dataset)
    assert 0.0 <= report.overall_mrr <= 1.0
