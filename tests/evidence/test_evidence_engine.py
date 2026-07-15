import pytest
from backend.evidence.engine import EvidenceAssessmentEngine
from backend.evidence.models import CorpusPresence
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult

@pytest.fixture
def supported_doc():
    return KnowledgeDocument(
        concept_id="c1",
        name="Alpha Protocol",
        subject="physics",
        chapter="Ch1",
        definition_texts=["Alpha Protocol denotes the leading idea."],
        example_texts=["Compute alpha carefully."],
        formula_latex=["\\alpha = 1"]
    )

@pytest.fixture
def hollow_doc():
    return KnowledgeDocument(
        concept_id="c2",
        name="Hollow Concept",
        subject="physics",
        chapter="Ch1"
    )

def test_engine_empty_results():
    engine = EvidenceAssessmentEngine()
    report = engine.assess("what is alpha", [])
    assert report.supported is False
    assert report.presence == CorpusPresence.NOT_FOUND
    assert "Zero retrieval results returned." in report.reason

def test_engine_hollow_concept(hollow_doc):
    engine = EvidenceAssessmentEngine()
    results = [SearchResult(score=0.9, document=hollow_doc)]
    report = engine.assess("hollow concept definition", results)
    assert report.supported is False
    assert "hollow" in report.reason

def test_engine_lexical_failure(supported_doc):
    engine = EvidenceAssessmentEngine()
    results = [SearchResult(score=0.9, document=supported_doc)]
    report = engine.assess("completely missing terms", results)
    assert report.supported is False
    assert report.presence == CorpusPresence.NOT_FOUND

def test_engine_planner_failure(supported_doc):
    engine = EvidenceAssessmentEngine()
    doc_without_formula = supported_doc.model_copy(update={"formula_latex": []})
    results = [SearchResult(score=0.9, document=doc_without_formula)]
    report = engine.assess("formula for alpha protocol", results)
    assert report.supported is False
    assert "requires formulas" in report.reason

def test_engine_success(supported_doc):
    engine = EvidenceAssessmentEngine()
    results = [SearchResult(score=0.9, document=supported_doc)]
    report = engine.assess("what is alpha protocol", results)
    assert report.supported is True
    assert report.presence == CorpusPresence.FOUND
    assert report.reason == ""
    assert len(report.issues) == 0
