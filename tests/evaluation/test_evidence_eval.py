import pytest
from backend.evaluation.evidence_eval import EvidenceEvaluationEngine, FakeStrategy, _engine

def test_evidence_eval_report():
    engine = EvidenceEvaluationEngine()
    report = engine.evaluate()
    
    assert report.coverage is True
    assert report.educational_evidence is True
    assert report.lexical_support is True
    assert report.planner_support is True
    assert report.presence_detection is True
    assert report.determinism is True
    assert report.all_passed is True

def test_fake_strategy():
    strategy = FakeStrategy()
    docs = strategy.search("alpha protocol")
    assert len(docs) == 1
    assert docs[0].document.concept_id == "c1"
    
    hollow = strategy.search("hollow")
    assert len(hollow) == 1
    assert hollow[0].document.concept_id == "c2"

    missing = strategy.search("unknown")
    assert len(missing) == 0
