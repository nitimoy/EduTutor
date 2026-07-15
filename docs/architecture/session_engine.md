# Phase 10.0: Learning Session Engine Architecture

## Overview
The Learning Session Engine sits on top of the frozen `EducationalTutorEngine` to provide stateful, multi-turn tutoring. It maintains conversational history, resolves context-dependent follow-up queries deterministically, and synthesizes interaction state into a structured `StudentProfile`.

The session engine adheres to the core architectural principles:
- **No LLM in orchestration:** All state management and query resolution is purely deterministic.
- **Dependency Injection:** The `EducationalTutorEngine` is injected into the `SessionManager`.
- **Freezing core logic:** The `backend/api/` layer wraps the Session Engine, leaving the core educational components strictly untouched.

## Components

### Models
- `SessionTurn`: Represents a single request-response turn, storing the raw query, the resolved query, intent/strategy metadata, and verification results.
- `LearningSession`: The stateful object representing the active conversation, tracking the `StudentProfile`, history, and active concept.

### FollowUpResolver
A rule-based module for converting vague, context-dependent queries into explicit, fully formed queries.
Rules (e.g., `AnotherExampleRule`, `ExplainAgainRule`) implement `matches()` and `rewrite()` using simple heuristics against user input. This eliminates the need for LLM-based query rewriting and guarantees determinism.

### SessionManager
Coordinates everything. Exposes lifecycle methods (`start`, `ask`, `get`, `delete`) and updates the `StudentProfile` based on the interaction history. It intercepts the user query, rewrites it, asks the `EducationalTutorEngine`, and saves the results.

### API Layer
Session endpoints (`POST /api/v1/session/start`, `POST /api/v1/session/{id}/ask`, etc.) in `backend/api/routes/session_lifecycle.py` provide external access to the stateful multi-turn tutor.

## Extensibility
The `backend/api/` and `backend/session/` packages are extensible to support the product layer, while `backend/orchestrator/`, `backend/generation/`, and other educational core packages remain frozen.
