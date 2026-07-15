"""Tests for the orchestrator ExecutionTrace + Tracer."""

import pytest

from backend.orchestrator.tracing import ExecutionTrace, StageStatus, StageTrace, Tracer


def test_tracer_records_success():
    tracer = Tracer()
    with tracer.stage("a"):
        pass
    trace = tracer.build()
    assert trace.stage_names() == ("a",)
    assert trace.stage("a").status == StageStatus.SUCCESS


def test_tracer_records_failure_and_reraises():
    tracer = Tracer()
    with pytest.raises(ValueError):
        with tracer.stage("boom"):
            raise ValueError("x")
    trace = tracer.build()
    assert trace.stage("boom").status == StageStatus.FAILED


def test_stage_order_is_call_order():
    tracer = Tracer()
    for name in ("one", "two", "three"):
        with tracer.stage(name):
            pass
    assert tracer.build().stage_names() == ("one", "two", "three")


def test_structure_is_timing_free():
    tracer = Tracer()
    with tracer.stage("a"):
        pass
    structure = tracer.build().structure()
    assert structure == (("a", "success"),)


def test_per_stage_ms_keys():
    tracer = Tracer()
    with tracer.stage("a"):
        pass
    assert "a" in tracer.per_stage_ms()


def test_stage_trace_defaults():
    st = StageTrace(name="x", status=StageStatus.SKIPPED)
    assert st.duration_ms == 0.0


def test_execution_trace_stage_lookup_missing():
    assert ExecutionTrace().stage("nope") is None
