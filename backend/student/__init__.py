"""Student Model — deterministic personalization between TeachingPlan and TutorPlan.

Sits in the Phase-4 seam: takes a frozen ``TeachingPlan`` + a ``StudentProfile`` and emits
an immutable ``TeachingPlanDelta`` (an explainable patch). ``TeachingPlanApplier`` turns the
delta into a personalized ``TeachingPlan`` that the frozen Tutor Brain composer consumes.
No LLM, no scheduling, no ML — every decision is rule-based and explainable.
"""

from backend.student.applier import TeachingPlanApplier
from backend.student.engine import StudentModel
from backend.student.learning_state import (
    LearningSignal,
    LearningState,
    derive_state,
    transition,
)
from backend.student.models import (
    Depth,
    DifficultyPreference,
    DifficultyTarget,
    Emphasis,
    ExamplePreference,
    ExplanationPreference,
    OpKind,
    PacePreference,
    PersonalizationAction,
    PersonalizationDecision,
    SectionDirective,
    SectionOp,
    StudentPreferences,
    StudentProfile,
    StudentState,
    TeachingPlanDelta,
)
from backend.student.rules import DEFAULT_POLICY, PersonalizationRule, RulePolicy

__all__ = [
    "StudentModel",
    "TeachingPlanApplier",
    # profile
    "StudentProfile",
    "StudentState",
    "StudentPreferences",
    "DifficultyPreference",
    "ExplanationPreference",
    "ExamplePreference",
    "PacePreference",
    # learning state
    "LearningState",
    "LearningSignal",
    "transition",
    "derive_state",
    # personalization IR
    "TeachingPlanDelta",
    "PersonalizationDecision",
    "PersonalizationAction",
    "SectionOp",
    "OpKind",
    "SectionDirective",
    "Emphasis",
    "Depth",
    "DifficultyTarget",
    # rules
    "PersonalizationRule",
    "RulePolicy",
    "DEFAULT_POLICY",
]
