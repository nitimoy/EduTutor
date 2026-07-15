"""Tests for API request/response schema serialization."""

from backend.api.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CitationOut,
    ExecutionMetadataOut,
    RetrievalMetadataOut,
    SessionProcessResponse,
    TimingOut,
    TutorAskRequest,
    TutorAskResponse,
)
from backend.evaluation.orchestrator_eval import FakeStrategy, _engine, _profile
from backend.student.models import StudentProfile


def test_tutor_ask_request_defaults():
    req = TutorAskRequest(query="Hello")
    assert req.query == "Hello"
    assert isinstance(req.student_profile, StudentProfile)
    assert req.retrieval_context is None


def test_tutor_ask_response_from_engine_response():
    resp = _engine().answer("what is alpha", _profile())
    api_resp = TutorAskResponse.from_engine_response(resp)
    assert api_resp.query == "what is alpha"
    assert api_resp.answer == resp.rendered_response.text
    assert api_resp.verification_passed == resp.passed
    assert api_resp.intent == resp.execution_metadata.intent
    assert api_resp.teaching_strategy == resp.execution_metadata.teaching_strategy
    assert api_resp.deterministic_fingerprint == resp.deterministic_fingerprint()


def test_tutor_ask_response_citations_match():
    resp = _engine().answer("what is alpha", _profile())
    api_resp = TutorAskResponse.from_engine_response(resp)
    assert len(api_resp.citations) == len(resp.citations)
    for api_cit, eng_cit in zip(api_resp.citations, resp.citations):
        assert api_cit.concept_id == eng_cit.concept_id
        assert api_cit.concept_name == eng_cit.concept_name


def test_tutor_ask_response_retrieval_metadata():
    resp = _engine().answer("what is alpha", _profile())
    api_resp = TutorAskResponse.from_engine_response(resp)
    assert api_resp.retrieval.strategy_name == resp.retrieval_metadata.strategy_name
    assert api_resp.retrieval.top_k == resp.retrieval_metadata.top_k
    assert api_resp.retrieval.n_results == resp.retrieval_metadata.n_results


def test_tutor_ask_response_timing():
    resp = _engine().answer("what is alpha", _profile())
    api_resp = TutorAskResponse.from_engine_response(resp)
    assert api_resp.timing.total_ms >= 0
    assert len(api_resp.timing.per_stage_ms) > 0


def test_tutor_ask_response_serializable():
    resp = _engine().answer("what is alpha", _profile())
    api_resp = TutorAskResponse.from_engine_response(resp)
    # Must serialize to JSON without errors.
    json_str = api_resp.model_dump_json()
    assert '"query"' in json_str
    assert '"answer"' in json_str


def test_session_process_response_from_engine_result():
    from backend.session.engine import LearningSessionEngine
    from backend.session.events import EventType, LearningEvent, SessionEventLog
    from backend.student.models import StudentState

    engine = LearningSessionEngine()
    session = SessionEventLog(
        session_id="test",
        events=[LearningEvent(type=EventType.EXERCISE_CORRECT, concept_id="c1")],
    )
    result = engine.process(StudentState(), session)
    api_resp = SessionProcessResponse.from_engine_result(result)
    assert api_resp.delta == result.delta
    assert api_resp.after == result.after


def test_chat_request_round_trip():
    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    assert len(req.messages) == 1
    assert req.messages[0].role == "user"


def test_chat_response_shape():
    resp = ChatResponse(answer="Hello!", model="echo/echo-v1")
    data = resp.model_dump()
    assert data == {"answer": "Hello!", "model": "echo/echo-v1"}
