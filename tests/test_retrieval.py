"""Tests for the deterministic BM25F retriever.

Covers the audit's retrieval findings: natural-language query handling (BUG-3),
ranking anomalies / additive double-counting (BUG-18), exact-match handling
(BUG-19), plus determinism and tokenization behavior.
"""

from backend.retrieval.api.search import RetrievalAPI, _content_tokens, _stem
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex


def _api(tmp_path, docs):
    index = KnowledgeIndex(book_id="book.1", documents=docs)
    p = tmp_path / "knowledge_index.json"
    p.write_text(index.model_dump_json())
    return RetrievalAPI(p)


def _doc(cid, name, aliases=None, definitions=None):
    return KnowledgeDocument(
        concept_id=cid,
        name=name,
        aliases=aliases or [],
        subject="physics",
        chapter="Chapter 1",
        definition_texts=definitions or [],
    )


# --- tokenization / lexical normalization -------------------------------------

def test_stop_words_and_question_words_are_removed():
    assert _content_tokens("What is an electric dipole?") == ["electric", "dipole"]


def test_standalone_article_is_not_merged_into_next_word():
    # Regression: the concept-heading normalizer merged "a solution" -> "asolution".
    assert _content_tokens("What is a solution?") == ["solution"]


def test_plural_stemming():
    assert _stem("solutions") == "solution"
    assert _stem("properties") == "property"
    assert _stem("charges") == "charge"


# --- BUG-3: natural-language queries return the right concept -----------------

def test_natural_language_query_matches_concept(tmp_path):
    api = _api(tmp_path, [
        _doc("c.dipole", "Electric Dipole"),
        _doc("c.field", "Electric Field"),
        _doc("c.flux", "Electric Flux"),
    ])
    results = api.search("What is an electric dipole?", top_k=3)
    assert results
    assert results[0].document.concept_id == "c.dipole"


def test_singular_query_matches_plural_concept(tmp_path):
    api = _api(tmp_path, [
        _doc("c.sol", "Solutions"),
        _doc("c.conc", "Expressing Concentration of Solutions"),
    ])
    results = api.search("What is a solution?", top_k=3)
    assert results[0].document.concept_id == "c.sol"


# --- BUG-19: exact-match handling ---------------------------------------------

def test_exact_name_match_ranks_first(tmp_path):
    api = _api(tmp_path, [
        _doc("c.a", "Electric Field Lines"),
        _doc("c.b", "Electric Field"),
        _doc("c.c", "Field due to a charged shell", definitions=["electric field lines everywhere"]),
    ])
    results = api.search("Electric Field Lines", top_k=3)
    assert results[0].document.concept_id == "c.a"
    # Exact hit dominates partial/definition hits by a wide margin.
    assert results[0].score > results[1].score + 100


def test_alias_exact_match(tmp_path):
    api = _api(tmp_path, [
        _doc("c.a", "One-one function", aliases=["injective function"]),
        _doc("c.b", "Onto function", aliases=["surjective function"]),
    ])
    results = api.search("injective function", top_k=2)
    assert results[0].document.concept_id == "c.a"


# --- BUG-18: no additive double-count anomaly ---------------------------------

def test_concise_name_outranks_noisy_long_name(tmp_path):
    # A short exact concept name must beat a long OCR-noisy name that merely
    # contains the query term, rather than the long name winning via stacked
    # additive tiers.
    api = _api(tmp_path, [
        _doc("c.short", "Electric Charge"),
        _doc("c.long", "Potential Due To As Ystem Of Charges And Fields And Charge"),
    ])
    results = api.search("electric charge", top_k=2)
    assert results[0].document.concept_id == "c.short"


def test_scores_are_bounded_no_runaway(tmp_path):
    api = _api(tmp_path, [_doc("c.a", "Electric Charge")])
    # Even with name + subset applicability, a single exact tier fires.
    results = api.search("Electric Charge", top_k=1)
    assert results[0].score < 1100  # one exact-name boost + small BM25, not stacked


# --- determinism --------------------------------------------------------------

def test_ranking_is_deterministic_with_ties(tmp_path):
    # Three docs that all match "charge" identically -> stable, name-sorted order.
    api = _api(tmp_path, [
        _doc("c.z", "Charge Z"),
        _doc("c.a", "Charge A"),
        _doc("c.m", "Charge M"),
    ])
    r1 = [x.document.concept_id for x in api.search("charge", top_k=3)]
    r2 = [x.document.concept_id for x in api.search("charge", top_k=3)]
    assert r1 == r2


def test_empty_query_returns_nothing(tmp_path):
    api = _api(tmp_path, [_doc("c.a", "Electric Charge")])
    assert api.search("what is the?", top_k=5) == []
