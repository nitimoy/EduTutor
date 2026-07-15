"""Tests for the orchestrator evaluation engine + benchmark smoke."""

from backend.evaluation.orchestrator_eval import OrchestratorEvaluationEngine


def test_default_suite_all_passes():
    report = OrchestratorEvaluationEngine().evaluate()
    assert report.all_passed
    assert report.deterministic
    assert report.stage_ordering
    assert report.metadata_propagation
    assert report.verify_fail_handling
    assert report.citation_preservation
    assert report.config_propagation
    assert report.no_mutation


def test_report_is_deterministic():
    engine = OrchestratorEvaluationEngine()
    a = engine.evaluate().model_dump_json()
    b = engine.evaluate().model_dump_json()
    assert a == b


def test_benchmark_module_imports():
    import scripts.orchestrator_benchmark as ob

    assert hasattr(ob, "run")
