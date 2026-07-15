import pytest
from backend.evidence.checks import EvidenceContext, RetrievalCoverageCheck, EducationalEvidenceCheck, LexicalSupportCheck, PlannerSupportCheck, CorpusPresenceCheck
from backend.evidence.models import CorpusPresence
from backend.retrieval.strategies.base import SearchResult
from backend.retrieval.index.models import KnowledgeDocument
from backend.tutor.models import EducationalIntent

@pytest.fixture
def empty_ctx():
    return EvidenceContext(query="test", results=[], intent=EducationalIntent.DEFINITION, issues=[])

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

@pytest.fixture
def supported_ctx(supported_doc):
    results = [SearchResult(score=0.9, document=supported_doc)]
    return EvidenceContext(query="alpha protocol definition", results=results, intent=EducationalIntent.DEFINITION, issues=[])

def test_coverage_check_empty(empty_ctx):
    check = RetrievalCoverageCheck()
    assert check.evaluate(empty_ctx) is False
    assert len(empty_ctx.issues) == 1

def test_coverage_check_supported(supported_ctx):
    check = RetrievalCoverageCheck()
    assert check.evaluate(supported_ctx) is True
    assert len(supported_ctx.issues) == 0

def test_educational_check_empty(empty_ctx):
    check = EducationalEvidenceCheck()
    assert check.evaluate(empty_ctx) is False

def test_educational_check_hollow(hollow_doc):
    ctx = EvidenceContext(query="hollow", results=[SearchResult(score=0.8, document=hollow_doc)], intent=EducationalIntent.EXPLANATION, issues=[])
    check = EducationalEvidenceCheck()
    assert check.evaluate(ctx) is False
    assert len(ctx.issues) == 1
    assert "hollow" in ctx.issues[0]

def test_educational_check_supported(supported_ctx):
    check = EducationalEvidenceCheck()
    assert check.evaluate(supported_ctx) is True

def test_lexical_check_empty(empty_ctx):
    check = LexicalSupportCheck()
    assert check.evaluate(empty_ctx) is False

def test_lexical_check_no_overlap(supported_doc):
    ctx = EvidenceContext(query="completely missing terms", results=[SearchResult(score=0.9, document=supported_doc)], intent=EducationalIntent.DEFINITION, issues=[])
    check = LexicalSupportCheck()
    assert check.evaluate(ctx) is False
    assert len(ctx.issues) == 1

def test_lexical_check_overlap(supported_ctx):
    check = LexicalSupportCheck()
    assert check.evaluate(supported_ctx) is True

def test_planner_check_empty(empty_ctx):
    check = PlannerSupportCheck()
    assert check.evaluate(empty_ctx) is False

def test_planner_check_formula_pass(supported_doc):
    ctx = EvidenceContext(query="alpha formula", results=[SearchResult(score=0.9, document=supported_doc)], intent=EducationalIntent.FORMULA, issues=[])
    check = PlannerSupportCheck()
    assert check.evaluate(ctx) is True

def test_planner_check_formula_fail(hollow_doc):
    ctx = EvidenceContext(query="hollow formula", results=[SearchResult(score=0.9, document=hollow_doc)], intent=EducationalIntent.FORMULA, issues=[])
    check = PlannerSupportCheck()
    assert check.evaluate(ctx) is False
    assert len(ctx.issues) == 1

def test_planner_check_example_pass(supported_doc):
    ctx = EvidenceContext(query="alpha example", results=[SearchResult(score=0.9, document=supported_doc)], intent=EducationalIntent.WORKED_EXAMPLE, issues=[])
    check = PlannerSupportCheck()
    assert check.evaluate(ctx) is True

def test_planner_check_example_fail(hollow_doc):
    ctx = EvidenceContext(query="hollow example", results=[SearchResult(score=0.9, document=hollow_doc)], intent=EducationalIntent.WORKED_EXAMPLE, issues=[])
    check = PlannerSupportCheck()
    assert check.evaluate(ctx) is False

def test_corpus_presence_empty(empty_ctx):
    check = CorpusPresenceCheck()
    assert check.evaluate(empty_ctx) == CorpusPresence.NOT_FOUND

def test_corpus_presence_found(supported_ctx):
    # Query: "alpha protocol definition"
    # Doc name: "Alpha Protocol"
    # Overlap is partial (definition not in name)
    check = CorpusPresenceCheck()
    assert check.evaluate(supported_ctx) == CorpusPresence.PARTIAL

def test_corpus_presence_exact(supported_doc):
    ctx = EvidenceContext(query="alpha protocol", results=[SearchResult(score=0.9, document=supported_doc)], intent=EducationalIntent.DEFINITION, issues=[])
    check = CorpusPresenceCheck()
    assert check.evaluate(ctx) == CorpusPresence.FOUND

def test_corpus_presence_not_found(supported_doc):
    ctx = EvidenceContext(query="omega test", results=[SearchResult(score=0.9, document=supported_doc)], intent=EducationalIntent.DEFINITION, issues=[])
    check = CorpusPresenceCheck()
    assert check.evaluate(ctx) == CorpusPresence.NOT_FOUND
