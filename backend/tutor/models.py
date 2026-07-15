"""Intermediate representations for the Tutor Brain.

Two pydantic IRs, produced in sequence:

* :class:`TeachingPlan` — the *intermediate* plan of what to teach and in what order.
  It references the selected content but carries **no resolved citations**. This is the
  object a later Student Model edits (reorder / drop / restrategize) without touching
  retrieval or composition.
* :class:`TutorPlan` — the *final* structured output: the same material assembled into
  named sections, each with resolved :class:`Citation`s back to compiler-produced
  objects.

Everything here is data only — deterministic, no LLM, no natural-language generation.
Every emitted section maps to a real compiler object; sections with no backing object
use :data:`SectionStatus.UNSUPPORTED_BY_INDEX` and are never fabricated.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EducationalIntent(str, Enum):
    """The educational intent of a student's question (detected, deterministic)."""

    DEFINITION = "definition"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    PREREQUISITE = "prerequisite"
    WORKED_EXAMPLE = "worked_example"
    FORMULA = "formula"
    PROOF = "proof"
    APPLICATION = "application"
    REVISION = "revision"


class QuestionType(str, Enum):
    """Fine-grained pedagogical question type — 13 deterministic classes.

    Drives *what lesson pattern* is used, independently of which educational
    objects happen to exist in the index. Maps 1-to-1 to a LessonPattern.
    """

    DEFINITION = "definition"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    CLASSIFICATION = "classification"
    PROCEDURE = "procedure"
    FORMULA = "formula"
    DERIVATION = "derivation"
    WORKED_EXAMPLE = "worked_example"
    LEARNING_PATH = "learning_path"
    REVISION = "revision"
    EXAM_PREPARATION = "exam_preparation"
    APPLICATION = "application"
    CONCEPTUAL_REASONING = "conceptual_reasoning"


class EvidenceSufficiency(str, Enum):
    """Whether the retrieved material can support the required style of reasoning.

    SUPPORTED           — retrieved material can answer the question from first principles.
    PARTIALLY_SUPPORTED — has grounded facts but lacks a causal chain or explicit reason.
    INSUFFICIENT        — only isolated definitions/formulae; no meaningful reasoning support.
    """

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    INSUFFICIENT = "insufficient"


class EducationalGoal(str, Enum):
    """The student's underlying learning goal — finer than QuestionType.

    Detected from QuestionType + contextual cues in the query (e.g. "for board
    exams", "intuitively", "step by step"). Two students can ask the same
    QuestionType (EXPLANATION) with different goals (CONCEPTUAL_UNDERSTANDING
    vs EXAM_PREPARATION), producing different lesson patterns.

    CONCEPTUAL_UNDERSTANDING  — comprehend what a concept *is* and how it works.
    UNDERSTAND_PRINCIPLE      — understand *why* or *how* from first principles
                                (physical/mathematical intuition).
    EXAM_PREPARATION          — board / JEE / NEET exam focus: key points + problems.
    PROBLEM_SOLVING           — solve a specific numerical or procedural problem.
    PROOF_AND_DERIVATION      — derive or prove something rigorously.
    QUICK_REVISION            — fast recap of key concepts, formulae, definitions.
    LEARNING_PATH             — understand what to study next / prerequisite order.
    STRUCTURED_COMPARISON     — compare two or more concepts side-by-side.
    """

    CONCEPTUAL_UNDERSTANDING = "conceptual_understanding"
    UNDERSTAND_PRINCIPLE = "understand_principle"
    EXAM_PREPARATION = "exam_preparation"
    PROBLEM_SOLVING = "problem_solving"
    PROOF_AND_DERIVATION = "proof_and_derivation"
    QUICK_REVISION = "quick_revision"
    LEARNING_PATH = "learning_path"
    STRUCTURED_COMPARISON = "structured_comparison"


class TeachingStrategyKind(str, Enum):
    """The explanation template selected for an intent."""

    CONCEPT_EXPLANATION = "concept_explanation"
    STEP_BY_STEP_DERIVATION = "step_by_step_derivation"
    FORMULA_EXPLANATION = "formula_explanation"
    COMPARE_AND_CONTRAST = "compare_and_contrast"
    WORKED_EXAMPLE_WALKTHROUGH = "worked_example_walkthrough"
    REVISION_SUMMARY = "revision_summary"
    PREREQUISITE_PATHWAY = "prerequisite_pathway"


class ResponseDepth(str, Enum):
    """The depth of the educational response."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_DETAILED = "very_detailed"


class TeachingGoal(str, Enum):
    """The specific pedagogical goal for the response."""

    INTRODUCE_CONCEPT = "introduce_concept"
    CLASSIFY_OR_COMPARE = "classify_or_compare"
    LEARNING_PATH = "learning_path"
    SOLVE_PROBLEM = "solve_problem"
    PROVE_STATEMENT = "prove_statement"
    FORMULA_REFERENCE = "formula_reference"
    REVISE = "revise"


class SectionKind(str, Enum):
    """Compiler-backed section kinds. No synthesized / presentation-only kinds.

    Each maps to a concrete source of truth:
      * PREREQUISITES / RELATED_CONCEPTS / NEXT_TOPICS — resolved graph names.
      * MAIN_EXPLANATION — concept ``definition_texts``.
      * FORMULA — concept ``formula_latex``.
      * WORKED_EXAMPLE — concept ``example_texts``.
      * PROOF / EXERCISE — IR objects recovered by concept id. Recovered theorem/property
        objects fold into MAIN_EXPLANATION (cited to their object id).
      * COMPARISON — the retrieved concepts' own definitions.
      * SUMMARY — a structured recap (name + difficulty + citations); no new prose.
    """

    PREREQUISITES = "prerequisites"
    MAIN_EXPLANATION = "main_explanation"
    FORMULA = "formula"
    WORKED_EXAMPLE = "worked_example"
    PROOF = "proof"
    EXERCISE = "exercise"
    COMPARISON = "comparison"
    RELATED_CONCEPTS = "related_concepts"
    NEXT_TOPICS = "next_topics"
    SUMMARY = "summary"
    GROUNDED_FACTS = "grounded_facts"  # disclaimer + facts when WHY cannot be answered


class SectionStatus(str, Enum):
    """Whether a section has real backing content."""

    PRESENT = "present"  # backed by a real compiler object
    EMPTY = "empty"  # the concept has no object of this kind in the index
    UNSUPPORTED_BY_INDEX = "unsupported_by_index"  # no representation anywhere / no repo


# --- source-field identifiers (where a cited item came from) ------------------
# Retrieval-index fields.
SOURCE_DEFINITION = "definition_texts"
SOURCE_FORMULA = "formula_latex"
SOURCE_EXAMPLE = "example_texts"
SOURCE_PREREQUISITE = "prerequisites"
SOURCE_RELATED = "related_concepts"
SOURCE_NEXT = "next_topics"
# Recovered IR object (locator is the object id, object_type carries the IR type).
SOURCE_OBJECT = "ir_object"
# Structural recap (no textual object; points at the concept itself).
SOURCE_CONCEPT = "concept"


class Citation(BaseModel):
    """A traceable reference from a plan item back to a compiler-produced object.

    ``concept_id`` is the owning concept (``None`` only when a graph name could not be
    resolved to an id — never a fabricated id). ``source_field`` names where the text
    came from; ``locator`` is the list index for index fields, or the IR ``object_id``
    for recovered objects. ``object_type`` carries the IR object type when applicable.
    """

    concept_id: str | None
    concept_name: str
    source_field: str
    locator: str
    object_type: str | None = None
    subject: str = ""
    chapter: str = ""


class ItemRef(BaseModel):
    """A selected content item inside a :class:`TeachingPlan` section.

    Carries the actual text/latex so the plan is self-contained and editable, plus the
    provenance needed to resolve a :class:`Citation` later. No resolved citation yet.
    """

    concept_id: str | None
    concept_name: str
    source_field: str
    locator: str
    object_type: str | None = None
    text: str = ""
    latex: list[str] = Field(default_factory=list)


class SectionSpec(BaseModel):
    """One ordered section of the intermediate :class:`TeachingPlan`."""

    kind: SectionKind
    status: SectionStatus
    item_refs: list[ItemRef] = Field(default_factory=list)
    note: str = ""


class TeachingPlan(BaseModel):
    """The intermediate 'what to teach' plan (Phase-5 mutable).

    Produced by stages 1–3 (intent → organize → strategy). Editing this object needs
    neither retrieval nor composition.
    """

    query: str
    intent: EducationalIntent
    strategy: TeachingStrategyKind
    primary_concept_id: str | None = None
    primary_concept_name: str = ""
    supporting_concept_ids: list[str] = Field(default_factory=list)
    question_type: "QuestionType | None" = None
    educational_goal: "EducationalGoal | None" = None
    sections: list[SectionSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PlanSection(BaseModel):
    """A resolved section of the final :class:`TutorPlan`."""

    kind: SectionKind
    status: SectionStatus
    items: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    note: str = ""


class TutorPlan(BaseModel):
    """The final deterministic teaching plan (not a natural-language answer).

    A fixed set of compiler-backed section slots. Absent slots are still present as
    ``PlanSection``s with ``EMPTY`` / ``UNSUPPORTED_BY_INDEX`` status so consumers get a
    complete, honest structure.
    """

    query: str
    intent: EducationalIntent
    strategy: TeachingStrategyKind
    primary_concept_id: str | None = None
    primary_concept_name: str = ""

    question_type: "QuestionType | None" = None
    educational_goal: "EducationalGoal | None" = None
    prerequisites: PlanSection
    main_explanation: PlanSection
    formula: PlanSection
    worked_example: PlanSection
    proof: PlanSection
    exercise: PlanSection
    comparison: PlanSection
    related_concepts: PlanSection
    suggested_next_topics: PlanSection
    summary: PlanSection
    grounded_facts: PlanSection = Field(
        default_factory=lambda: PlanSection(
            kind=SectionKind.GROUNDED_FACTS, status=SectionStatus.EMPTY))

    references: list[Citation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    deterministic: bool = True
