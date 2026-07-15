"""Tests for orchestrator result models."""

import json

import pytest
from pydantic import ValidationError

from backend.evaluation.orchestrator_eval import _engine, _profile
from backend.orchestrator.models import (
    ExecutionMetadata,
    RetrievalMetadata,
    TimingInfo,
    TutorResponse,
)


def test_retrieval_metadata_fields():
    rm = RetrievalMetadata(strategy_name="bm25f", top_k=5, n_results=2,
                           result_concept_ids=("c1", "c2"))
    assert rm.subject is None and rm.result_concept_ids == ("c1", "c2")


def test_execution_metadata_fields():
    em = ExecutionMetadata(provider="echo", model_id="echo-v1", style_preset="default",
                           intent="definition", teaching_strategy="concept_explanation")
    assert em.verification_passed is True and em.personalization_decisions == 0


def test_timing_info_defaults():
    assert TimingInfo().total_ms == 0.0 and TimingInfo().per_stage_ms == {}


def test_tutor_response_is_immutable():
    resp = _engine().answer("what is alpha", _profile())
    with pytest.raises((ValidationError, TypeError)):
        resp.passed = False


def test_response_serializes_to_json():
    resp = _engine().answer("what is alpha", _profile())
    payload = json.loads(resp.model_dump_json())
    assert payload["query"] == "what is alpha"
    assert "execution_trace" in payload and "timing" in payload


def test_fingerprint_is_stable_string():
    resp = _engine().answer("what is alpha", _profile())
    fp = resp.deterministic_fingerprint()
    assert isinstance(fp, str) and "trace_structure" in fp


def test_response_carries_all_stage_artifacts():
    resp = _engine().answer("what is alpha", _profile())
    assert resp.tutor_plan is not None
    assert resp.verification_report is not None
    assert resp.personalization is not None
    assert resp.rendered_response is not None
