"""Tests for the Language Generation evaluation engine + benchmark smoke."""

from backend.evaluation.generation_eval import (
    GenerationEvaluationEngine,
    check_adapter_equivalence,
    check_template_purity,
    default_cases,
)


def test_default_suite_all_passes():
    report = GenerationEvaluationEngine().evaluate(default_cases())
    assert report.all_passed
    assert report.prompt_determinism_rate == 1.0
    assert report.order_preserved_rate == 1.0
    assert report.unit_id_stability_rate == 1.0
    assert report.no_added_concepts_rate == 1.0
    assert report.citation_preservation_rate == 1.0
    assert report.grounding_rate == 1.0
    assert report.response_determinism_rate == 1.0
    assert report.template_purity_ok and report.adapter_equivalence_ok


def test_report_is_deterministic():
    engine = GenerationEvaluationEngine()
    a = engine.evaluate(default_cases()).model_dump_json()
    b = engine.evaluate(default_cases()).model_dump_json()
    assert a == b


def test_template_purity_guard():
    assert check_template_purity() is True


def test_adapter_equivalence_guard():
    assert check_adapter_equivalence() is True


def test_benchmark_module_imports():
    import scripts.generation_benchmark as gb

    assert hasattr(gb, "run")
