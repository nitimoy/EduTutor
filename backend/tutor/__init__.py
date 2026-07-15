"""Tutor Brain — deterministic post-retrieval teaching planner.

Sits entirely after retrieval. Turns retrieved ``KnowledgeDocument``s into a
structured teaching plan (``TeachingPlan``) and then a final structured output
(``TutorPlan``). No LLM and no natural-language generation in this phase — every
section maps to a real compiler-produced object, and anything unsupported by the
compiler artifacts is flagged, never fabricated.

The pipeline is a clean plan → resolve → compose seam so a later Student Model can
edit the ``TeachingPlan`` without touching retrieval or composition.
"""

from backend.tutor.composer import AnswerComposer, TutorBrain
from backend.tutor.intent import detect_intent
from backend.tutor.models import (
    Citation,
    EducationalIntent,
    ItemRef,
    PlanSection,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
    TutorPlan,
)
from backend.tutor.repository import (
    CompiledArtifactRepository,
    KnowledgeRepository,
    RecoveredObject,
)

__all__ = [
    "TutorBrain",
    "AnswerComposer",
    "detect_intent",
    # models
    "EducationalIntent",
    "TeachingStrategyKind",
    "SectionKind",
    "SectionStatus",
    "Citation",
    "ItemRef",
    "SectionSpec",
    "PlanSection",
    "TeachingPlan",
    "TutorPlan",
    # repository
    "KnowledgeRepository",
    "CompiledArtifactRepository",
    "RecoveredObject",
]
