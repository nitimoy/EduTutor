"""Models for the stateful Learning Session Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.orchestrator.models import TutorResponse
from backend.student.models import StudentProfile


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionTurn(BaseModel):
    """A structured record of a single interaction turn."""

    user_query: str
    resolved_query: str
    retrieval_metadata: dict[str, Any]
    intent: str
    strategy: str
    question_type: Optional[str] = None     # e.g. "conceptual_reasoning"
    educational_goal: Optional[str] = None  # e.g. "understand_principle"
    primary_concept: str
    tutor_response: str
    verification_passed: bool
    notes: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)


class LearningSession(BaseModel):
    """A stateful tutoring session representing an active learning conversation."""

    session_id: str
    student_profile: StudentProfile = Field(default_factory=StudentProfile)
    active_subject: Optional[str] = None
    active_chapter: Optional[str] = None
    active_concept: Optional[str] = None
    history: list[SessionTurn] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    completed_concepts: list[str] = Field(default_factory=list)
    last_response: Optional[TutorResponse] = None
