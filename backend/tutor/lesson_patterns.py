"""Lesson Patterns — fixed, educational-goal-driven slot templates.

Pipeline:
    QuestionType → EducationalGoal → LessonPattern

A LessonPattern defines:
  - Which SectionKinds are REQUIRED (always included, even if empty).
  - Which SectionKinds are OPTIONAL (included only if present in the index).
  - Which SectionKinds are BLOCKED (never included, regardless of data).
  - Whether a disclaimer is emitted when evidence is PARTIALLY_SUPPORTED or INSUFFICIENT.
  - Whether the LEARNING_PATH strategy should use the chapter hierarchy.

The EducationalGoal layer (between QuestionType and LessonPattern) allows the
same QuestionType to produce different lesson structures based on the student's
actual learning context. For example:

    QuestionType.EXPLANATION + goal=CONCEPTUAL_UNDERSTANDING
        → definition + formula + meaning

    QuestionType.EXPLANATION + goal=EXAM_PREPARATION
        → key points + formula + typical problems

    QuestionType.EXPLANATION + goal=UNDERSTAND_PRINCIPLE
        → principle + reasoning + concept (same pattern as UNDERSTAND_PRINCIPLE)

The EXPLANATION/CONCEPTUAL_UNDERSTANDING pattern and the UNDERSTAND_PRINCIPLE
pattern are explicitly kept different to support the separation:

    "Explain Coulomb's law."           → CONCEPTUAL_UNDERSTANDING
    "Why does Coulomb's law follow     → UNDERSTAND_PRINCIPLE
     an inverse-square relationship?"
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.tutor.models import EducationalGoal, QuestionType, SectionKind

SK = SectionKind  # alias for readability


@dataclass(frozen=True)
class LessonPattern:
    """The fixed slot template for one EducationalGoal.

    Attributes
    ----------
    required:
        Sections always present in the plan (may be EMPTY if data is absent).
    optional:
        Sections included only when backed by index data.
    blocked:
        Sections that must never appear for this goal.
    disclaimer_if_partial:
        When ``EvidenceSufficiency`` is PARTIALLY_SUPPORTED or INSUFFICIENT,
        emit a ``GROUNDED_FACTS`` disclaimer section before the answer.
    use_chapter_hierarchy:
        For LEARNING_PATH: use ``next_topics`` from the chapter document.
    """

    required: tuple[SK, ...] = field(default_factory=tuple)
    optional: tuple[SK, ...] = field(default_factory=tuple)
    blocked: tuple[SK, ...] = field(default_factory=tuple)
    disclaimer_if_partial: bool = False
    use_chapter_hierarchy: bool = False

    def ordered_sections(self) -> tuple[SK, ...]:
        """Return required + optional in canonical display order."""
        seen: set[SK] = set()
        out: list[SK] = []
        for kind in _CANONICAL_ORDER:
            if kind in self.blocked:
                continue
            if kind in self.required or kind in self.optional:
                if kind not in seen:
                    out.append(kind)
                    seen.add(kind)
        return tuple(out)

    def is_blocked(self, kind: SK) -> bool:
        return kind in self.blocked


# Canonical display order (mirrors TutorPlan field declaration order).
_CANONICAL_ORDER: tuple[SK, ...] = (
    SK.GROUNDED_FACTS,
    SK.PREREQUISITES,
    SK.MAIN_EXPLANATION,
    SK.FORMULA,
    SK.COMPARISON,
    SK.WORKED_EXAMPLE,
    SK.PROOF,
    SK.EXERCISE,
    SK.RELATED_CONCEPTS,
    SK.NEXT_TOPICS,
    SK.SUMMARY,
)

# ---------------------------------------------------------------------------
# Pattern registry — one entry per EducationalGoal.
# ---------------------------------------------------------------------------

LESSON_PATTERNS: dict[EducationalGoal, LessonPattern] = {

    # CONCEPTUAL_UNDERSTANDING: what the concept is, how it works, its formula.
    # "Explain Coulomb's law." → definition + formula + meaning + related
    EducationalGoal.CONCEPTUAL_UNDERSTANDING: LessonPattern(
        required=(SK.MAIN_EXPLANATION,),
        optional=(SK.PREREQUISITES, SK.FORMULA, SK.RELATED_CONCEPTS, SK.SUMMARY),
        blocked=(),
    ),

    # UNDERSTAND_PRINCIPLE: *why* or *how* something works — first-principles reasoning.
    # "Why does Coulomb's law follow an inverse-square relationship?"
    # → causal principle + supporting concepts. WORKED_EXAMPLE is blocked as lead.
    # disclaimer_if_partial=True: if the textbook doesn't explain WHY, say so.
    EducationalGoal.UNDERSTAND_PRINCIPLE: LessonPattern(
        required=(SK.MAIN_EXPLANATION,),
        optional=(SK.FORMULA, SK.RELATED_CONCEPTS, SK.SUMMARY),
        blocked=(SK.EXERCISE, SK.COMPARISON),
        disclaimer_if_partial=True,
    ),

    # EXAM_PREPARATION: board/JEE/NEET exam focus.
    # Key formulae, worked problems, summary.
    EducationalGoal.EXAM_PREPARATION: LessonPattern(
        required=(SK.SUMMARY,),
        optional=(SK.FORMULA, SK.WORKED_EXAMPLE, SK.MAIN_EXPLANATION,
                  SK.RELATED_CONCEPTS, SK.NEXT_TOPICS),
        blocked=(SK.PROOF, SK.COMPARISON),
    ),

    # PROBLEM_SOLVING: solve a specific numerical / procedural problem.
    EducationalGoal.PROBLEM_SOLVING: LessonPattern(
        required=(SK.WORKED_EXAMPLE,),
        optional=(SK.MAIN_EXPLANATION, SK.FORMULA, SK.EXERCISE, SK.SUMMARY),
        blocked=(SK.COMPARISON, SK.PROOF),
        disclaimer_if_partial=True,
    ),

    # PROOF_AND_DERIVATION: derive or prove something rigorously.
    EducationalGoal.PROOF_AND_DERIVATION: LessonPattern(
        required=(SK.PROOF,),
        optional=(SK.MAIN_EXPLANATION, SK.FORMULA, SK.SUMMARY),
        blocked=(SK.WORKED_EXAMPLE, SK.COMPARISON),
        disclaimer_if_partial=True,
    ),

    # QUICK_REVISION: fast recap — key concepts, formulae, definitions.
    EducationalGoal.QUICK_REVISION: LessonPattern(
        required=(SK.SUMMARY,),
        optional=(SK.MAIN_EXPLANATION, SK.FORMULA, SK.RELATED_CONCEPTS),
        blocked=(SK.COMPARISON, SK.PROOF),
    ),

    # LEARNING_PATH: what to study next / prerequisite order.
    # WORKED_EXAMPLE and FORMULA are blocked — this is a study-path, not a lesson.
    EducationalGoal.LEARNING_PATH: LessonPattern(
        required=(SK.PREREQUISITES, SK.NEXT_TOPICS),
        optional=(SK.RELATED_CONCEPTS, SK.SUMMARY),
        blocked=(SK.WORKED_EXAMPLE, SK.FORMULA, SK.PROOF, SK.EXERCISE, SK.COMPARISON),
        disclaimer_if_partial=True,
        use_chapter_hierarchy=True,
    ),

    # STRUCTURED_COMPARISON: compare two or more concepts side-by-side.
    # WORKED_EXAMPLE is permanently blocked.
    EducationalGoal.STRUCTURED_COMPARISON: LessonPattern(
        required=(SK.COMPARISON,),
        optional=(SK.RELATED_CONCEPTS, SK.SUMMARY),
        blocked=(SK.WORKED_EXAMPLE, SK.EXERCISE, SK.PROOF),
        disclaimer_if_partial=True,
    ),
}


def pattern_for(educational_goal: EducationalGoal) -> LessonPattern:
    """Return the :class:`LessonPattern` for ``educational_goal``."""
    return LESSON_PATTERNS[educational_goal]


# ---------------------------------------------------------------------------
# QuestionType → default EducationalGoal (kept here as a convenience alias
# for callers that haven't run the goal detector yet).
# ---------------------------------------------------------------------------

_QT_DEFAULT_GOAL: dict[QuestionType, EducationalGoal] = {
    QuestionType.DEFINITION:           EducationalGoal.CONCEPTUAL_UNDERSTANDING,
    QuestionType.EXPLANATION:          EducationalGoal.CONCEPTUAL_UNDERSTANDING,
    QuestionType.CONCEPTUAL_REASONING: EducationalGoal.UNDERSTAND_PRINCIPLE,
    QuestionType.COMPARISON:           EducationalGoal.STRUCTURED_COMPARISON,
    QuestionType.CLASSIFICATION:       EducationalGoal.CONCEPTUAL_UNDERSTANDING,
    QuestionType.PROCEDURE:            EducationalGoal.PROBLEM_SOLVING,
    QuestionType.FORMULA:              EducationalGoal.CONCEPTUAL_UNDERSTANDING,
    QuestionType.DERIVATION:           EducationalGoal.PROOF_AND_DERIVATION,
    QuestionType.WORKED_EXAMPLE:       EducationalGoal.PROBLEM_SOLVING,
    QuestionType.LEARNING_PATH:        EducationalGoal.LEARNING_PATH,
    QuestionType.REVISION:             EducationalGoal.QUICK_REVISION,
    QuestionType.EXAM_PREPARATION:     EducationalGoal.EXAM_PREPARATION,
    QuestionType.APPLICATION:          EducationalGoal.CONCEPTUAL_UNDERSTANDING,
}


def default_goal_for(question_type: QuestionType) -> EducationalGoal:
    """Default goal when no contextual cue is present."""
    return _QT_DEFAULT_GOAL.get(question_type, EducationalGoal.CONCEPTUAL_UNDERSTANDING)
