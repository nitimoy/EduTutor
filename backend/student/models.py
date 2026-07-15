"""Intermediate representations for the Student Model.

All data, deterministic, no LLM. The profile is split into persistent learning
``StudentState`` and user ``StudentPreferences``, aggregated by ``StudentProfile``. The
personalization output is an **immutable** ``TeachingPlanDelta`` — a source plan plus an
ordered, explainable decision patch. Applying the delta lives in ``applier.py`` (the delta
itself carries no execution logic).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from backend.student.learning_state import LearningState, derive_state
from backend.tutor.models import SectionKind, TeachingPlan

__all__ = [
    "LearningState",
    "DifficultyPreference", "ExplanationPreference", "ExamplePreference", "PacePreference",
    "StudentState", "StudentPreferences", "StudentProfile",
    "PersonalizationAction", "OpKind", "SectionOp",
    "Emphasis", "Depth", "DifficultyTarget", "SectionDirective",
    "PersonalizationDecision", "TeachingPlanDelta",
]


# --- preference enums (all default to STANDARD) ------------------------------
class DifficultyPreference(str, Enum):
    EASY = "easy"
    STANDARD = "standard"
    CHALLENGING = "challenging"


class ExplanationPreference(str, Enum):
    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


class ExamplePreference(str, Enum):
    FEW = "few"
    STANDARD = "standard"
    MANY = "many"


class PacePreference(str, Enum):
    SLOW = "slow"
    STANDARD = "standard"
    FAST = "fast"


# --- profile: persistent state + preferences ---------------------------------
class StudentState(BaseModel):
    """Persistent, per-concept learning state. Defaults describe a brand-new student."""

    concept_mastery: dict[str, float] = Field(default_factory=dict)      # 0.0 .. 1.0
    concept_confidence: dict[str, float] = Field(default_factory=dict)   # 0.0 .. 1.0
    concept_states: dict[str, LearningState] = Field(default_factory=dict)  # explicit
    misconception_flags: dict[str, list[str]] = Field(default_factory=dict)  # opaque labels
    completed_concepts: list[str] = Field(default_factory=list)
    prerequisite_gaps: list[str] = Field(default_factory=list)
    revision_counts: dict[str, int] = Field(default_factory=dict)  # history w/o scheduling
    learning_streak: int = 0

    def mastery_of(self, concept_id: str | None) -> float:
        return self.concept_mastery.get(concept_id, 0.0) if concept_id else 0.0

    def confidence_of(self, concept_id: str | None) -> float:
        return self.concept_confidence.get(concept_id, 0.0) if concept_id else 0.0

    def is_completed(self, concept_id: str | None) -> bool:
        return bool(concept_id) and concept_id in self.completed_concepts

    def has_gap(self, concept_id: str | None) -> bool:
        return bool(concept_id) and concept_id in self.prerequisite_gaps

    def has_misconception(self, concept_id: str | None) -> bool:
        return bool(concept_id) and bool(self.misconception_flags.get(concept_id))

    def _seen(self, concept_id: str) -> bool:
        return (
            concept_id in self.concept_mastery
            or concept_id in self.concept_states
            or concept_id in self.completed_concepts
            or concept_id in self.revision_counts
        )

    def state_of(self, concept_id: str | None) -> LearningState:
        """Explicit stored state if present, else deterministically derived."""
        if not concept_id:
            return LearningState.UNSEEN
        if concept_id in self.concept_states:
            return self.concept_states[concept_id]
        return derive_state(
            mastery=self.mastery_of(concept_id),
            seen=self._seen(concept_id),
            completed=self.is_completed(concept_id),
            needs_review=False,
        )


class StudentPreferences(BaseModel):
    """User-facing teaching preferences (all default to STANDARD)."""

    difficulty: DifficultyPreference = DifficultyPreference.STANDARD
    explanation: ExplanationPreference = ExplanationPreference.STANDARD
    example: ExamplePreference = ExamplePreference.STANDARD
    pace: PacePreference = PacePreference.STANDARD


class StudentProfile(BaseModel):
    """Aggregate of persistent state + preferences (no fields of its own)."""

    state: StudentState = Field(default_factory=StudentState)
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)


# --- personalization vocabulary ----------------------------------------------
class PersonalizationAction(str, Enum):
    INSERT_PREREQUISITE_REVIEW = "insert_prerequisite_review"
    REORDER_SECTIONS = "reorder_sections"
    SUPPRESS_ADVANCED = "suppress_advanced"
    INCREASE_WORKED_EXAMPLES = "increase_worked_examples"
    RECOMMEND_REVISION = "recommend_revision"
    LOWER_DIFFICULTY = "lower_difficulty"
    RAISE_DIFFICULTY = "raise_difficulty"
    POSTPONE_DIFFICULT = "postpone_difficult"
    ADJUST_DEPTH = "adjust_depth"
    ADJUST_EMPHASIS = "adjust_emphasis"


class OpKind(str, Enum):
    MOVE_TO_FRONT = "move_to_front"
    MOVE_TO_BACK = "move_to_back"
    SUPPRESS = "suppress"


class SectionOp(BaseModel):
    """A structural patch primitive over a section, by kind."""

    op: OpKind
    section: SectionKind


class Emphasis(str, Enum):
    DEEMPHASIZE = "deemphasize"
    NORMAL = "normal"
    EMPHASIZE = "emphasize"


class Depth(str, Enum):
    CONDENSE = "condense"
    NORMAL = "normal"
    EXPAND = "expand"


class DifficultyTarget(str, Enum):
    EASY = "easy"
    STANDARD = "standard"
    CHALLENGING = "challenging"


class SectionDirective(BaseModel):
    """Advisory metadata for the future language generator — never content."""

    emphasis: Emphasis = Emphasis.NORMAL
    depth: Depth = Depth.NORMAL
    review: bool = False
    difficulty_target: DifficultyTarget | None = None


class PersonalizationDecision(BaseModel):
    """One explainable patch element produced by a firing rule.

    ``rule_name`` and ``priority`` are stamped by the engine from the firing rule, so a
    rule's ``build`` function can omit them.
    """

    action: PersonalizationAction
    reason: str
    rule_name: str = ""
    priority: int = 0
    ops: list[SectionOp] = Field(default_factory=list)
    directives: dict[SectionKind, SectionDirective] = Field(default_factory=dict)


class TeachingPlanDelta(BaseModel):
    """Immutable personalization patch: a source plan + an ordered decision list.

    Carries **no execution logic** — ``TeachingPlanApplier`` turns it into a personalized
    ``TeachingPlan``. The ``source_plan`` is kept unchanged.
    """

    model_config = ConfigDict(frozen=True)

    source_plan: TeachingPlan
    decisions: tuple[PersonalizationDecision, ...] = ()
    profile: StudentProfile = Field(default_factory=StudentProfile)
    notes: tuple[str, ...] = ()
    deterministic: bool = True
