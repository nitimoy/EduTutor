"""Tests for the Student Model evaluation engine + benchmark smoke."""

from backend.evaluation.student_eval import (
    StudentModelEvaluationEngine,
    default_cases,
    default_transition_cases,
    reference_plan,
)
from backend.evaluation.student_models import StateTransitionCase


def test_default_suite_all_passes():
    report = StudentModelEvaluationEngine().evaluate(
        default_cases(), default_transition_cases())
    assert report.all_passed
    assert report.determinism_rate == 1.0
    assert report.decision_correctness_rate == 1.0
    assert report.priority_ordering_rate == 1.0
    assert report.invariant_pass_rate == 1.0
    assert report.transition_correctness_rate == 1.0


def test_report_is_deterministic():
    engine = StudentModelEvaluationEngine()
    a = engine.evaluate(default_cases(), default_transition_cases()).model_dump_json()
    b = engine.evaluate(default_cases(), default_transition_cases()).model_dump_json()
    assert a == b


def test_bad_transition_case_is_flagged():
    bad = [StateTransitionCase(from_state="unseen", signal="introduce", to_state="mastered")]
    report = StudentModelEvaluationEngine().evaluate(default_cases(), bad)
    assert report.transition_correctness_rate == 0.0
    assert not report.all_passed


def test_reference_plan_has_expected_sections():
    kinds = {s.kind.value for s in reference_plan().sections}
    assert {"main_explanation", "prerequisites", "proof", "worked_example", "summary"} <= kinds


def test_benchmark_module_imports():
    import scripts.student_benchmark as sb

    assert hasattr(sb, "run") and hasattr(sb, "PROFILES")
