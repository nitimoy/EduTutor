import pytest
from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.models import UnsupportedQueryResponse
from backend.student.models import StudentProfile
from backend.retrieval.strategies.base import SearchResult, StrategyMetadata
from backend.retrieval.index.models import KnowledgeDocument
from backend.generation.language_model import EchoLanguageModel

class DummyStrategy:
    def __init__(self, should_support: bool):
        self.should_support = should_support
        self.doc = KnowledgeDocument(
            concept_id="test", name="Test Concept", subject="math", chapter="ch1",
            definition_texts=["This is a test definition."]
        )

    def search(self, query, top_k=5, context=None):
        if not self.should_support:
            return []
        return [SearchResult(score=0.9, document=self.doc)]

    def metadata(self):
        return StrategyMetadata(name="dummy", kind="lexical", deterministic=True)

def test_orchestrator_evidence_rejection():
    config = OrchestratorConfig(use_repository=False, top_k=5, style_preset="default", strict_verification=False)
    engine = EducationalTutorEngine(config, strategy=DummyStrategy(should_support=False), language_model=EchoLanguageModel())
    
    response = engine.answer("unsupported query that returns zero results", StudentProfile())
    
    # Should reject the query and return UnsupportedQueryResponse
    assert isinstance(response, UnsupportedQueryResponse)
    assert response.passed is False
    assert response.evidence_report is not None
    assert response.evidence_report.supported is False
    assert "Zero retrieval results returned." in response.evidence_report.reason

def test_orchestrator_evidence_acceptance():
    config = OrchestratorConfig(use_repository=False, top_k=5, style_preset="default", strict_verification=False)
    engine = EducationalTutorEngine(config, strategy=DummyStrategy(should_support=True), language_model=EchoLanguageModel())
    
    # Needs to match intent "DEFINITION" and lexical "test concept"
    response = engine.answer("test concept definition", StudentProfile())
    
    # Should not be an UnsupportedQueryResponse if it succeeds (returns TutorResponse which is what UnsupportedQueryResponse subclasses, 
    # but UnsupportedQueryResponse has passed=False, whereas a successful response has passed=True)
    assert not isinstance(response, UnsupportedQueryResponse) or response.passed is True
