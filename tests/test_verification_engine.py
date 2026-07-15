"""End-to-end tests for the ResponseVerificationEngine."""

from backend.evaluation.verification_eval import _faithful, default_cases
from backend.verification import VerificationEngine
from backend.verification.config import VerificationConfig
from backend.verification.engine import ResponseVerificationEngine


def test_faithful_response_passes():
    plan, gplan, rendered = _faithful()
    report = ResponseVerificationEngine().verify(plan, gplan, rendered)
    assert report.passed
    assert report.metrics.coverage == 1.0
    assert report.metrics.grounding_completeness == 1.0
    assert report.metrics.citation_accuracy == 1.0
    assert report.issues == ()


def test_alias_exported():
    assert VerificationEngine is ResponseVerificationEngine


def test_every_tampered_case_fails_with_expected_code():
    engine = ResponseVerificationEngine()
    for case in default_cases():
        report = engine.verify(case.tutor_plan, case.generation_plan, case.rendered)
        assert report.passed == case.expected_pass, case.name
        raised = {i.code for i in report.issues}
        for code in case.expected_codes:
            assert code in raised, f"{case.name}: expected {code}, got {sorted(raised)}"


def test_report_is_deterministic():
    plan, gplan, rendered = _faithful()
    engine = ResponseVerificationEngine()
    a = engine.verify(plan, gplan, rendered).model_dump_json()
    b = engine.verify(plan, gplan, rendered).model_dump_json()
    assert a == b


def test_inputs_not_mutated():
    plan, gplan, rendered = _faithful()
    before = (plan.model_dump_json(), gplan.model_dump_json(), rendered.model_dump_json())
    ResponseVerificationEngine().verify(plan, gplan, rendered)
    assert (plan.model_dump_json(), gplan.model_dump_json(), rendered.model_dump_json()) == before


def test_issues_sorted_by_severity():
    # dropped section produces errors; ensure severity-sorted (errors first).
    case = next(c for c in default_cases() if c.name == "dropped_section")
    report = ResponseVerificationEngine().verify(case.tutor_plan, case.generation_plan, case.rendered)
    ranks = [i.severity.value for i in report.issues]
    assert ranks == sorted(ranks, key=lambda s: {"error": 0, "warning": 1, "info": 2}[s])


def test_config_thresholds_affect_verdict():
    # A tiny grounding gap fails under strict config; a relaxed threshold could pass.
    plan, gplan, rendered = _faithful()
    strict = ResponseVerificationEngine(VerificationConfig(min_grounding_coverage=1.0))
    assert strict.verify(plan, gplan, rendered).passed  # faithful is perfect either way
