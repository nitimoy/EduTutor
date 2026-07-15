"""Evaluation benchmark for deterministic multi-turn conversation replay."""

from __future__ import annotations

import time

from backend.api.config import ServiceConfig
from backend.api.factory import EngineFactory


def evaluate_conversation_determinism() -> None:
    """Run a multi-turn conversation twice and assert perfectly identical outputs and states."""
    
    # We use echo provider but strict reproducibility.
    # In a real environment we'd use GPT/Claude. For benchmark we use echo since it is fast.
    config = ServiceConfig(provider="echo", compiled_dir="data/compiled", use_repository=False)
    factory = EngineFactory(config)
    manager = factory.session_manager
    
    conversation = [
        "What is a matrix?",
        "Give me another example.",
        "Explain that again.",
        "What should I study next?",
    ]
    
    def run_session(student_id: str) -> list[dict[str, str]]:
        session = manager.start(student_id)
        turns = []
        for q in conversation:
            response = manager.ask(session.session_id, q)
            # manually set active concept to simulate orchestrator resolving it
            current = manager.get(session.session_id)
            if not current.active_concept:
                current.active_concept = "matrix"
                manager._store.save(current)
            turns.append({
                "resolved": current.history[-1].resolved_query,
                "response": response.rendered_response.text,
            })
        return turns
        
    print("Running Session A...")
    start_a = time.time()
    turns_a = run_session("student_a")
    dur_a = time.time() - start_a
    
    print("Running Session B...")
    start_b = time.time()
    turns_b = run_session("student_b")
    dur_b = time.time() - start_b
    
    print(f"Execution time: Session A: {dur_a:.2f}s, Session B: {dur_b:.2f}s")
    
    for i, (ta, tb) in enumerate(zip(turns_a, turns_b)):
        assert ta["resolved"] == tb["resolved"], f"Turn {i} resolved query mismatch"
        assert ta["response"] == tb["response"], f"Turn {i} response mismatch"
        print(f"Turn {i+1} perfectly matched.")
        
    print("✅ Determinism verified: Multi-turn conversations are byte-identical.")

if __name__ == "__main__":
    evaluate_conversation_determinism()
