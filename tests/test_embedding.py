"""Tests for the embedding core: document text, hashing provider, builder,
provenance/versioning, and incremental rebuilds."""

import math

from backend.retrieval.embedding.builder import (
    EmbeddingBuilder,
    document_checksum,
    document_text,
)
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import HashingEmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex


def _doc(cid="c.1", name="Electric Charge", **kw):
    return KnowledgeDocument(concept_id=cid, name=name, subject="physics", chapter="Chapter 1", **kw)


# --- document_text: only allowed fields ---------------------------------------

def test_document_text_uses_only_name_alias_definition():
    # Frozen Phase 3.35 representation: only name + aliases + definitions are
    # embedded (label-free). Everything else is deliberately excluded.
    doc = _doc(
        aliases=["charge"],
        definition_texts=["a fundamental property of matter"],
        formula_latex=["q = ne"],
        example_texts=["a proton carries plus e"],
        related_concepts=["Field Lines"],
        prerequisites=["Atomic Structure"],
        next_topics=["nope"],
        difficulty="nope",
    )
    text = document_text(doc)
    for included in ("Electric Charge", "charge", "fundamental property"):
        assert included in text
    for excluded in ("q = ne", "proton", "Field Lines", "Atomic Structure", "nope"):
        assert excluded not in text
    # Label-free: no "definition_texts:" style field labels in the output.
    assert "definition_texts:" not in text and "aliases:" not in text


def test_document_text_is_deterministic():
    doc = _doc(definition_texts=["x"], aliases=["a", "b"])
    assert document_text(doc) == document_text(doc)


# --- hashing provider ---------------------------------------------------------

def test_hashing_provider_shape_and_determinism():
    p = HashingEmbeddingProvider(dimension=64)
    assert p.provider_id == "hashing"
    assert p.dimension == 64
    v1 = p.embed_query("electric charge")
    v2 = p.embed_query("electric charge")
    assert v1 == v2 and len(v1) == 64
    # L2-normalized for non-empty text
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9


def test_hashing_batch_matches_single():
    p = HashingEmbeddingProvider(dimension=32)
    texts = ["electric field", "magnetic flux"]
    batch = p.embed_documents(texts)
    assert batch[0] == p.embed_query("electric field")
    assert batch[1] == p.embed_query("magnetic flux")


def test_builder_returns_vector_per_concept():
    p = HashingEmbeddingProvider(dimension=32)
    docs = [_doc("c.1", "Electric Charge"), _doc("c.2", "Electric Field")]
    vecs = EmbeddingBuilder().vectors(docs, p)
    assert set(vecs) == {"c.1", "c.2"}
    assert len(vecs["c.1"]) == 32


def test_document_checksum_changes_on_content_change():
    p = HashingEmbeddingProvider(dimension=16)
    a = _doc(definition_texts=["one"])
    b = _doc(definition_texts=["two"])
    assert document_checksum(a, p) != document_checksum(b, p)
    assert document_checksum(a, p) == document_checksum(_doc(definition_texts=["one"]), p)


# --- EmbeddingIndex: versioning, provenance, incremental ----------------------

def _ki():
    return KnowledgeIndex(
        book_id="book.1",
        documents=[_doc("c.1", "Electric Charge", definition_texts=["property of matter"]),
                   _doc("c.2", "Electric Field", definition_texts=["region of force"])],
    )


def test_embedding_index_build_and_provenance(tmp_path):
    p = HashingEmbeddingProvider(dimension=32)
    idx = EmbeddingIndex(tmp_path)
    result = idx.build(_ki(), p, EmbeddingBuilder())
    prov = result.manifest.provenance
    assert result.created and result.embedded == 2 and result.reused == 0
    assert prov.provider == "hashing" and prov.dimension == 32
    assert prov.document_count == 2 and prov.book_id == "book.1"
    assert prov.compiler_version and prov.knowledge_index_checksum and prov.created_at
    # load round-trip
    manifest, vectors = idx.load("hashing", p.model_id)
    assert set(vectors) == {"c.1", "c.2"} and manifest.version == result.manifest.version


def test_embedding_index_incremental_noop_on_rebuild(tmp_path):
    p = HashingEmbeddingProvider(dimension=32)
    idx = EmbeddingIndex(tmp_path)
    idx.build(_ki(), p, EmbeddingBuilder())
    again = idx.build(_ki(), p, EmbeddingBuilder())
    assert again.created is False and again.embedded == 0 and again.reused == 2


def test_embedding_index_incremental_only_changed(tmp_path):
    p = HashingEmbeddingProvider(dimension=32)
    idx = EmbeddingIndex(tmp_path)
    idx.build(_ki(), p, EmbeddingBuilder())
    changed = KnowledgeIndex(
        book_id="book.1",
        documents=[_doc("c.1", "Electric Charge", definition_texts=["property of matter"]),
                   _doc("c.2", "Electric Field", definition_texts=["CHANGED DEFINITION"])],
    )
    result = idx.build(changed, p, EmbeddingBuilder())
    assert result.created is True
    assert result.embedded == 1 and result.reused == 1  # only c.2 re-embedded
