"""Tests for the Response Verification evaluation engine + benchmark smoke."""

from backend.evaluation.verification_eval import (
    VerificationEvaluationEngine,
    default_cases,
)


def test_default_suite_all_passes():
    report = VerificationEvaluationEngine().evaluate(default_cases())
    assert report.all_passed
    assert report.verdict_accuracy == 1.0
    assert report.code_detection_rate == 1.0
    assert report.determinism_rate == 1.0


def test_report_is_deterministic():
    engine = VerificationEvaluationEngine()
    a = engine.evaluate(default_cases()).model_dump_json()
    b = engine.evaluate(default_cases()).model_dump_json()
    assert a == b


def test_case_set_has_faithful_and_tampered():
    names = {c.name for c in default_cases()}
    assert "faithful" in names
    assert {"dropped_section", "extra_citation", "ungrounded_term",
            "missing_content_line"}.issubset(names)


def test_benchmark_module_imports():
    import scripts.verification_benchmark as vb

    assert hasattr(vb, "run")
