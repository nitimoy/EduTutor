import pytest
import os
import json
from backend.evaluation.regression_models import DatasetItem, ExpectedOutput, RegressionResult
from backend.evaluation.regression_reporter import RegressionReporter
from backend.evaluation.regression_eval import RegressionEvaluationEngine

class DummyTutorResponse:
    def __init__(self, passed):
        self.passed = passed
        self.evidence_report = None
        self.teaching_plan = None
    def model_dump_json(self):
        return json.dumps({"passed": self.passed})

def test_regression_reporter_empty():
    reporter = RegressionReporter(output_dir="/tmp/test_reports")
    metrics = reporter.calculate_metrics([])
    assert metrics.total_queries == 0
    assert metrics.overall_accuracy == 0.0

def test_regression_reporter_metrics():
    reporter = RegressionReporter(output_dir="/tmp/test_reports")
    result1 = RegressionResult(
        query="test",
        expected_concept="C1",
        actual_concept="C1",
        retrieval_correct=True,
        retrieval_rank=1,
        retrieval_score=0.9,
        expected_intent="definition",
        actual_intent="definition",
        intent_correct=True,
        expected_strategy="explain",
        actual_strategy="explain",
        strategy_correct=True,
        expected_sections=["summary"],
        actual_sections=["summary"],
        sections_correct=True,
        verification_passed=True,
        supported_expected=True,
        supported_actual=True,
        supported_correct=True,
        time_retrieval_ms=10.0,
        time_planning_ms=10.0,
        time_generation_ms=10.0,
        time_verification_ms=10.0,
        time_total_ms=40.0,
        deterministic=True
    )
    metrics = reporter.calculate_metrics([result1])
    assert metrics.total_queries == 1
    assert metrics.overall_accuracy == 100.0
    assert metrics.retrieval_recall_1 == 100.0
    assert metrics.avg_latency_ms == 40.0
    assert metrics.determinism_rate == 100.0

def test_regression_engine_deterministic():
    engine = RegressionEvaluationEngine(use_repository=False)
    
    item = DatasetItem(
        query="what is alpha",
        expected=ExpectedOutput(
            concept="alpha",
            intent="definition",
            strategy="concept_explanation",
            supported=False,
            sections=[]
        )
    )
    
    # Run item evaluation (uses default EchoLanguageModel and DummyStrategy or empty strategy)
    result = engine.evaluate_item(item)
    
    assert result.deterministic is True
    # As the empty strategy will return zero results, it will be unsupported
    assert result.supported_actual is False
