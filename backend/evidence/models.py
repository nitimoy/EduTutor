"""Models for the Evidence Assessment Engine."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CorpusPresence(str, Enum):
    """Presence of the requested concept in the compiled repository."""
    FOUND = "FOUND"
    PARTIAL = "PARTIAL"
    NOT_FOUND = "NOT_FOUND"


class EvidenceRelevance(str, Enum):
    """Relevance of retrieved evidence to the explicitly requested topic."""
    RELEVANT = "RELEVANT"
    PARTIALLY_RELEVANT = "PARTIALLY_RELEVANT"
    NOT_RELEVANT = "NOT_RELEVANT"


class EvidenceReport(BaseModel):
    """Deterministic evaluation of retrieval results before planning."""

    model_config = ConfigDict(frozen=True)

    supported: bool
    reason: str
    retrieval_score: float = 0.0
    coverage: float = 0.0
    planner_supported: bool = False
    presence: CorpusPresence = CorpusPresence.NOT_FOUND
    relevance: EvidenceRelevance = EvidenceRelevance.NOT_RELEVANT
    issues: list[str] = Field(default_factory=list)
    # Sufficiency and question type are filled by EvidenceAssessmentEngine
    # and forwarded to the planner via the orchestrator.
    sufficiency: Optional[str] = None   # EvidenceSufficiency value
    question_type: Optional[str] = None  # QuestionType value
