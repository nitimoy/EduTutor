"""End-to-end tests for EducationalTutorEngine (offline: FakeStrategy + Echo)."""

import pytest

from backend.evaluation.orchestrator_eval import (
    FakeStrategy,
    _FailVerifier,
    _engine,
    _profile,
)
from backend.generation.language_model import EchoLanguageModel
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import STAGES, EducationalTutorEngine
from backend.orchestrator.errors import StageExecutionError, VerificationFailedError
from backend.orchestrator.models import TutorResponse
from backend.orchestrator.tracing import StageStatus
from backend.retrieval.strategies.base import RetrievalContext


def test_answer_returns_tutor_response():
    resp = _engine().answer("what is alpha", _profile())
    assert isinstance(resp, TutorResponse)
    assert resp.query == "what is alpha"
    assert resp.rendered_response.text  # something was rendered


def test_stage_order_and_all_success():
    resp = _engine().answer("what is alpha", _profile())
    assert resp.execution_trace.stage_names() == STAGES
    assert all(s.status == StageStatus.SUCCESS for s in resp.execution_trace.stages)


def test_deterministic_fingerprint():
    a = _engine().answer("what is alpha", _profile())
    b = _engine().answer("what is alpha", _profile())
    assert a.deterministic_fingerprint() == b.deterministic_fingerprint()


def test_citations_preserved_through_pipeline():
    resp = _engine().answer("what is alpha", _profile())
    assert list(resp.citations) == list(resp.tutor_plan.references)
    assert list(resp.citations) == list(resp.rendered_response.references)


def test_retrieval_metadata_propagated():
    resp = _engine().answer("what is alpha", _profile())
    rm = resp.retrieval_metadata
    assert rm.n_results == 2 and rm.top_k == 5 and rm.strategy_name == "fake"
    assert rm.result_concept_ids == ("c1", "c2")


def test_execution_metadata_propagated():
    resp = _engine().answer("what is alpha", _profile())
    em = resp.execution_metadata
    assert em.provider == "echo"
    assert em.intent == resp.tutor_plan.intent.value
    assert em.teaching_strategy == resp.tutor_plan.strategy.value
    assert em.personalization_decisions == len(resp.personalization.decisions)


def test_profile_not_mutated():
    profile = _profile()
    before = profile.model_dump_json()
    _engine().answer("what is alpha", profile)
    assert profile.model_dump_json() == before


def test_stage_exception_wrapped_and_halts():
    class _Boom:
        def search(self, query, top_k=5, context=None):
            raise RuntimeError("retrieval down")

        def metadata(self):
            raise RuntimeError("nope")

    engine = EducationalTutorEngine(
        OrchestratorConfig(use_repository=False), strategy=_Boom(),
        language_model=EchoLanguageModel())
    with pytest.raises(StageExecutionError) as exc:
        engine.answer("q", _profile())
    assert exc.value.stage == "retrieval"


def test_strict_verification_raises_on_fail():
    with pytest.raises(VerificationFailedError):
        _engine(strict=True, verifier=_FailVerifier()).answer("what is alpha", _profile())


def test_default_returns_failing_report_without_raising():
    resp = _engine(verifier=_FailVerifier()).answer("what is alpha", _profile())
    assert resp.passed is False and resp.verification_report.passed is False


def test_fingerprint_excludes_timing():
    resp = _engine().answer("what is alpha", _profile())
    from backend.orchestrator.models import TimingInfo
    other = resp.model_copy(update={"timing": TimingInfo(total_ms=999.0)})
    assert resp.deterministic_fingerprint() == other.deterministic_fingerprint()


def test_retrieval_context_filter_propagates():
    resp = _engine().answer("what is alpha", _profile(),
                            RetrievalContext(subject="chemistry"))
    # FakeStrategy docs are physics -> chemistry filter yields no results.
    assert resp.retrieval_metadata.n_results == 0
    assert resp.retrieval_metadata.subject == "chemistry"
