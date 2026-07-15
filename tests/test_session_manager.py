"""Tests for the multi-turn Session Engine."""

import pytest

from backend.api.config import ServiceConfig
from backend.api.factory import EngineFactory
from backend.session.manager import SessionNotFoundError


@pytest.fixture
def manager():
    # Use the echo provider and an empty memory store
    config = ServiceConfig(provider="echo", compiled_dir="data/compiled", use_repository=False)
    factory = EngineFactory(config)
    return factory.session_manager


def test_start_session(manager):
    session = manager.start("student_123")
    assert session.session_id


def test_ask_question_first_turn(manager):
    session = manager.start("student_1")
    
    # First turn
    response = manager.ask(session.session_id, "What is a matrix?")
    
    # Check updated state
    updated = manager.get(session.session_id)
    assert len(updated.history) == 1
    turn = updated.history[0]
    assert turn.user_query == "What is a matrix?"
    assert turn.resolved_query == "What is a matrix?"
    assert turn.tutor_response == response.rendered_response.text


def test_follow_up_resolution(manager):
    session = manager.start("student_1")
    
    # Turn 1: establish active concept
    manager.ask(session.session_id, "What is a matrix?")
    # In Echo provider with no repo, active_concept might be None or dummy
    # We will manually set the active concept to simulate an orchestrator result
    session = manager.get(session.session_id)
    session.active_concept = "matrix addition"
    manager._store.save(session)
    
    # Turn 2: Follow up
    manager.ask(session.session_id, "another example")
    
    updated = manager.get(session.session_id)
    assert len(updated.history) == 2
    turn2 = updated.history[1]
    assert turn2.user_query == "another example"
    # Should resolve using the AnotherExampleRule
    assert "matrix addition" in turn2.resolved_query
    assert turn2.resolved_query == "Show me another worked example of matrix addition."


def test_update_student_profile(manager):
    session = manager.start("student_2")
    
    manager.ask(session.session_id, "What is scalar multiplication?")
    
    updated = manager.get(session.session_id)
    # The echo provider with use_repository=False won't return a concept_id,
    # so we manually test the update function.
    manager.update_student_profile(updated, "concept_scalar_mult")
    
    assert "concept_scalar_mult" in updated.completed_concepts
    assert "concept_scalar_mult" in updated.student_profile.state.completed_concepts


def test_invalid_session_id(manager):
    with pytest.raises(SessionNotFoundError):
        manager.ask("invalid_id", "hello")
        
    with pytest.raises(SessionNotFoundError):
        manager.get("invalid_id")


def test_delete_session(manager):
    session = manager.start("student_3")
    manager.delete(session.session_id)
    
    with pytest.raises(SessionNotFoundError):
        manager.get(session.session_id)
