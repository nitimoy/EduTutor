"""Tests for verification report models."""

import pytest
from pydantic import ValidationError

from backend.verification.models import (
    CoverageReport,
    Severity,
    VerificationIssue,
    VerificationResult,
    severity_rank,
)


def test_issue_is_immutable():
    issue = VerificationIssue(code="X", severity=Severity.ERROR, message="m")
    with pytest.raises((ValidationError, TypeError)):
        issue.code = "Y"


def test_severity_rank_orders_error_first():
    assert severity_rank(Severity.ERROR) < severity_rank(Severity.WARNING) < severity_rank(Severity.INFO)


def test_result_defaults():
    r = VerificationResult(name="v", passed=True)
    assert r.issues == ()


def test_coverage_report_roundtrip():
    rep = CoverageReport(expected_kinds=("a",), rendered_kinds=("a",), coverage_pct=1.0)
    assert CoverageReport.model_validate_json(rep.model_dump_json()) == rep
