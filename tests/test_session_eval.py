"""Tests for the Learning Session Engine evaluation framework + benchmark smoke."""

from backend.evaluation.session_eval import (
    SessionEvaluationEngine,
    default_cases,
    default_transition_cases,
)
from backend.evaluation.session_models import TransitionCase


def test_default_suite_all_passes():
    report = SessionEvaluationEngine().evaluate(default_cases(), default_transition_cases())
    assert report.all_passed
    assert report.determinism_rate == 1.0
    assert report.replay_rate == 1.0
    assert report.canonical_delta_rate == 1.0
    assert report.outcome_rate == 1.0
    assert report.invariant_rate == 1.0
    assert report.transition_correctness_rate == 1.0


def test_report_is_deterministic():
    engine = SessionEvaluationEngine()
    a = engine.evaluate(default_cases(), default_transition_cases()).model_dump_json()
    b = engine.evaluate(default_cases(), default_transition_cases()).model_dump_json()
    assert a == b


def test_bad_transition_case_flagged():
    bad = [TransitionCase(from_state="unseen", event_type="lesson_started", to_state="mastered")]
    report = SessionEvaluationEngine().evaluate(default_cases(), bad)
    assert report.transition_correctness_rate == 0.0 and not report.all_passed


def test_benchmark_module_imports():
    import scripts.session_benchmark as sb

    assert hasattr(sb, "run")
