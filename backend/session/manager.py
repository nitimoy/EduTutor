"""The Learning Session Manager coordinating multi-turn interactions."""

from __future__ import annotations

import uuid

from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.models import TutorResponse
from backend.session.models import LearningSession, SessionTurn
from backend.session.resolver import FollowUpResolver
from backend.session.store import SessionStore
from backend.student.models import StudentProfile


class SessionNotFoundError(Exception):
    """Raised when a session cannot be found."""
    pass


class SessionManager:
    """Coordinates stateful tutoring sessions over the EducationalTutorEngine."""

    def __init__(
        self,
        engine: EducationalTutorEngine,
        store: SessionStore,
        resolver: FollowUpResolver | None = None,
    ) -> None:
        self._engine = engine
        self._store = store
        self._resolver = resolver or FollowUpResolver()

    def start(self, student_id: str, profile: StudentProfile | None = None) -> LearningSession:
        """Initialize and persist a new tutoring session."""
        session_id = str(uuid.uuid4())
        session = LearningSession(
            session_id=session_id,
            student_profile=profile or StudentProfile(),
        )
        self._store.save(session)
        return session

    def list_sessions(self) -> list[dict[str, str]]:
        """List all sessions with lightweight metadata."""
        return self._store.list_sessions()

    def ask(self, session_id: str, query: str) -> TutorResponse:
        """Process a query within a stateful session."""
        session = self._store.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found.")

        # Resolve context-dependent queries
        resolved_query = self._resolver.resolve(query, session)

        # Call the frozen EducationalTutorEngine
        response = self._engine.answer(resolved_query, session.student_profile)

        # Update session state
        concept_id = None
        if response.retrieval_metadata.result_concept_ids:
            concept_id = response.retrieval_metadata.result_concept_ids[0]
            
        primary_concept = response.execution_metadata.primary_concept_name
        if primary_concept:
            session.active_concept = primary_concept
            
        session.active_subject = response.retrieval_metadata.subject
        session.active_chapter = response.retrieval_metadata.chapter
        session.last_response = response

        # Add turn to history
        tutor_plan = getattr(response, "tutor_plan", None)
        qt = getattr(tutor_plan, "question_type", None)
        eg = getattr(tutor_plan, "educational_goal", None)
        turn = SessionTurn(
            user_query=query,
            resolved_query=resolved_query,
            retrieval_metadata=response.retrieval_metadata.model_dump(),
            intent=response.execution_metadata.intent,
            strategy=response.execution_metadata.teaching_strategy,
            question_type=qt.value if qt is not None else None,
            educational_goal=eg.value if eg is not None else None,
            primary_concept=primary_concept,
            tutor_response=response.rendered_response.text,
            verification_passed=response.execution_metadata.verification_passed,
            notes=getattr(tutor_plan, "notes", []) or [],
        )
        session.history.append(turn)

        # Update student profile based on the interaction
        self.update_student_profile(session, concept_id)

        self._store.save(session)
        return response

    def update_student_profile(self, session: LearningSession, concept_id: str | None) -> None:
        """Sync session interactions back into the student profile."""
        if not concept_id:
            return
            
        if concept_id not in session.completed_concepts:
            session.completed_concepts.append(concept_id)
            
        # Simplified sync into the underlying StudentProfile for this engine level
        if concept_id not in session.student_profile.state.completed_concepts:
            session.student_profile.state.completed_concepts.append(concept_id)

    def get(self, session_id: str) -> LearningSession:
        """Retrieve a session by ID."""
        session = self._store.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found.")
        return session

    def delete(self, session_id: str) -> None:
        """Delete a session."""
        self._store.delete(session_id)
