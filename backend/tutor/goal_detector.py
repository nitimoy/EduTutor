"""Educational Goal Detector.

Resolves a (QuestionType, query) pair → EducationalGoal.

This is the bridge between *what* was asked (QuestionType — structural) and
*why* it was asked (EducationalGoal — intent). Two students can ask the same
type of question with completely different learning goals:

    "Explain matrix multiplication."
    QuestionType  → EXPLANATION
    EducationalGoal → CONCEPTUAL_UNDERSTANDING   (definition + meaning + formula)

    "Explain matrix multiplication for board exams."
    QuestionType  → EXPLANATION
    EducationalGoal → EXAM_PREPARATION            (key points + typical problems)

    "Why does matrix multiplication not commute?"
    QuestionType  → CONCEPTUAL_REASONING
    EducationalGoal → UNDERSTAND_PRINCIPLE        (first-principles reasoning)

Cue detection is lexical (regex), deterministic, and subject-agnostic.
Goal cues override the default QuestionType → EducationalGoal mapping.

Pipeline position:
    classify(query) → QuestionType
    detect_goal(QuestionType, query) → EducationalGoal
    pattern_for(EducationalGoal) → LessonPattern
"""

from __future__ import annotations

import re

from backend.tutor.models import EducationalGoal, QuestionType

# ---------------------------------------------------------------------------
# Context-cue patterns — override the default QT mapping when matched.
# ---------------------------------------------------------------------------

# Exam / competitive context: overrides almost any QuestionType.
_EXAM_CUE = re.compile(
    r"\b(for\s+(?:board|jee|neet|exam(?:s)?)|board\s+exam|important\s+for|"
    r"frequently\s+asked|past\s+(?:year|paper)|competitive\s+exam|"
    r"typical\s+(?:question|problem)|exam\s+(?:prep|ready|wise))\b",
    re.I,
)

# "From first principles", "intuitively", "physically" → UNDERSTAND_PRINCIPLE.
_PRINCIPLE_CUE = re.compile(
    r"\b(from\s+first\s+principles?|intuitively|physically|mathematically|"
    r"fundamental(?:ly)?|underlying\s+reason|at\s+its\s+core|"
    r"deep(?:er)?\s+understanding)\b",
    re.I,
)

# Revision / quick-recap override.
_REVISION_CUE = re.compile(
    r"\b(revise|revision|quick\s+(?:review|recap)|summarize|summary|recap)\b",
    re.I,
)

# Problem-solving context: "step by step", "work through".
_PROBLEM_SOLVING_CUE = re.compile(
    r"\b(step[\s-]by[\s-]step|work(?:ing)?\s+through|walk\s+(?:me\s+)?through|"
    r"step\s+by\s+step\s+solution)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Default QuestionType → EducationalGoal mapping (no context cues found).
# ---------------------------------------------------------------------------

_DEFAULT: dict[QuestionType, EducationalGoal] = {
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


def detect_goal(question_type: QuestionType, query: str) -> EducationalGoal:
    """Resolve ``question_type`` + ``query`` cues → :class:`EducationalGoal`.

    Context cues override the default mapping. Multiple cues can appear in a
    query; priority order is: EXAM > PROBLEM_SOLVING > UNDERSTAND_PRINCIPLE >
    QUICK_REVISION > default.
    """
    text = query.strip() if query else ""

    # Highest priority: explicit exam context overrides everything.
    if _EXAM_CUE.search(text):
        return EducationalGoal.EXAM_PREPARATION

    # Problem-solving override: "step by step" + worked example type.
    if _PROBLEM_SOLVING_CUE.search(text):
        return EducationalGoal.PROBLEM_SOLVING

    # First-principles / intuition cues → UNDERSTAND_PRINCIPLE
    # (even if the QuestionType is EXPLANATION, not CONCEPTUAL_REASONING).
    if _PRINCIPLE_CUE.search(text):
        return EducationalGoal.UNDERSTAND_PRINCIPLE

    # Revision cue — takes precedence over default for explanation types.
    if _REVISION_CUE.search(text):
        return EducationalGoal.QUICK_REVISION

    return _DEFAULT.get(question_type, EducationalGoal.CONCEPTUAL_UNDERSTANDING)
