"""Deterministic QuestionType classifier for the Tutor Brain.

Maps a student's raw query → QuestionType using first-match precedence on
pure regex/keyword predicates. Subject-agnostic; no concept names hardcoded.

QuestionType is *finer-grained* than EducationalIntent: it drives which
LessonPattern is applied, ensuring that the lesson structure is determined
by the question *type*, not by whichever educational object happens to exist.

Precedence (most specific → least):
    CONCEPTUAL_REASONING  — Why/How/Can/Should questions (before EXPLANATION)
    COMPARISON            — compare / difference / vs / contrast
    CLASSIFICATION        — types of / classify
    LEARNING_PATH         — what should I study / after / before / learn first
    EXAM_PREPARATION      — exam / frequently asked / important for exam
    REVISION              — summarize / revise / recap
    DERIVATION            — prove / derive
    FORMULA               — formula for / equation of
    WORKED_EXAMPLE        — solve / calculate / numerical
    PROCEDURE             — steps to / how to (procedural, not causal)
    APPLICATION           — applications / real life / used in
    EXPLANATION           — explain (without Why/How/Can opening)
    DEFINITION            — fallback
"""

from __future__ import annotations

import re

from backend.tutor.models import QuestionType

# ---------------------------------------------------------------------------
# Compiled patterns — ordered by decreasing specificity.
# ---------------------------------------------------------------------------

# Explicit worked-example override — "how do I solve", "how to solve", "how do I calculate"
# must route to WORKED_EXAMPLE, NOT CONCEPTUAL_REASONING, even though they start with "How".
_SOLVE_OVERRIDE = re.compile(
    r"\b(how\s+(?:do\s+i|to)\s+(?:solve|calculate|compute|evaluate|find)|solve\s+problems?\.?\s+on|how\s+do\s+i\s+(?:approach|do))\b",
    re.I,
)

# CONCEPTUAL_REASONING: causal / possibility questions.
# Must come BEFORE EXPLANATION because "how" / "can" / "should" also appear
# in explanation queries, but these require a different lesson structure.
_CONCEPTUAL_CUE = re.compile(
    r"^\s*(?:why|how\s+does|how\s+do|how\s+is|how\s+are|how\s+can|"
    r"can\s|could\s|should\s|is\s+it\s+(?:possible|true|correct|wrong)|"
    r"what\s+(?:happens|would\s+happen)|does\s+it|do\s+they)",
    re.I,
)
# Also capture mid-sentence "why" in short queries
_CONCEPTUAL_MID = re.compile(r"\bwhy\b", re.I)

_COMPARISON_CUE = re.compile(
    r"\b(compare|comparison|difference\s+between|differences\s+between|"
    r"\bvs\.?\b|versus|contrast|distinguish\s+between|"
    r"similarities?\s+(?:and|&)\s+differences?|relate\s+\w+\s+to)\b",
    re.I,
)

_CLASSIFICATION_CUE = re.compile(
    r"\b(types?\s+of|classification\s+of|classify|different\s+kinds?\s+of|"
    r"kinds?\s+of|categories?\s+of|list\s+the\s+types?)\b",
    re.I,
)

_LEARNING_PATH_CUE = re.compile(
    r"\b(what\s+should\s+i\s+study|study\s+(?:next|after|before)|"
    r"after\s+(?:studying|learning|finishing|matrices|determinants|"
    r"calculus|electrochemistry|sets|functions)|"
    r"before\s+learning|prerequisite|prerequisites\s+for|"
    r"learn\s+(?:first|before)|where\s+should\s+i\s+start|"
    r"how\s+(?:should\s+i\s+learn|do\s+i\s+learn|to\s+learn)|"
    r"what\s+to\s+study|study\s+path|learning\s+order|"
    r"can\s+i\s+learn\s+\w+\s+without)\b",
    re.I,
)

_EXAM_PREP_CUE = re.compile(
    r"\b(exam\s+prep(?:aration)?|important\s+for\s+exam|frequently\s+asked|"
    r"jee|neet|board\s+exam|past\s+(?:year|paper)|previous\s+year|"
    r"typical\s+problems?|important\s+questions?)\b",
    re.I,
)

_REVISION_CUE = re.compile(
    r"\b(revise|revision|summarize|summarise|summary\s+of|summarize\s+all|"
    r"recap|quick\s+review|revision\s+notes?|give\s+me\s+a\s+summary)\b",
    re.I,
)

_DERIVATION_CUE = re.compile(
    r"\b(prove|proof\s+(?:of|that)|derive|derivation|derived|show\s+that|"
    r"deduce)\b",
    re.I,
)

_FORMULA_CUE = re.compile(
    r"\b(formula\s+(?:for|of)|equation\s+(?:for|of)|write\s+the\s+expression|"
    r"expression\s+for|what\s+is\s+the\s+formula)\b",
    re.I,
)

_WORKED_EXAMPLE_CUE = re.compile(
    r"\b(solve|calculate|compute|evaluate|find\s+the\s+value|numerical|"
    r"worked\s+example|example\s+of|step.by.step\s+solution|"
    r"(?:solve\s+)?the\s+following|"
    r"multiply|add|subtract|divide|simplify|expand|factor|reduce)\b",
    re.I,
)

_PROCEDURE_CUE = re.compile(
    r"\b(steps?\s+(?:to|for)|method\s+(?:to|for|of)|process\s+of|"
    r"procedure\s+(?:to|for)|how\s+to\s+(?:find|solve|calculate|compute|do))\b",
    re.I,
)

_APPLICATION_CUE = re.compile(
    r"\b(applications?\s+of|used\s+(?:in|for)|uses?\s+of|real[- ]life|"
    r"daily\s+life|everyday|practical\s+use|where\s+(?:is|are)\s+\w+\s+used)\b",
    re.I,
)

_EXPLANATION_CUE = re.compile(
    r"\b(explain|explanation\s+of|describe|elaborate|what\s+is\s+meant|"
    r"what\s+does\s+\w+\s+mean|meaning\s+of)\b",
    re.I,
)


def classify(query: str) -> tuple[QuestionType, str]:
    """Classify ``query`` into a :class:`QuestionType`.

    Returns ``(question_type, matched_pattern_key)`` where the key is a
    short string naming the rule that fired (useful in tests / traces).
    Deterministic: identical inputs always produce identical outputs.
    """
    text = query.strip() if query else ""

    # --- precedence rules ---------------------------------------------------

    # WORKED_EXAMPLE override: "how do I solve", "solve problems on" must route
    # to WORKED_EXAMPLE even though they start with "How". This must fire before
    # the CONCEPTUAL_REASONING check.
    if _SOLVE_OVERRIDE.search(text) or _WORKED_EXAMPLE_CUE.search(text):
        # But only if it isn't a comparison or classification.
        if not _COMPARISON_CUE.search(text) and not _CLASSIFICATION_CUE.search(text):
            return QuestionType.WORKED_EXAMPLE, "solve_override"

    # CONCEPTUAL_REASONING beats everything else: "Why does X?", "How does X?",
    # "Can X?", "Should X?" — causal/possibility framing.
    if _CONCEPTUAL_CUE.search(text) or _CONCEPTUAL_MID.search(text):
        return QuestionType.CONCEPTUAL_REASONING, "conceptual_cue"

    if _COMPARISON_CUE.search(text):
        return QuestionType.COMPARISON, "comparison_cue"

    if _CLASSIFICATION_CUE.search(text):
        return QuestionType.CLASSIFICATION, "classification_cue"

    if _LEARNING_PATH_CUE.search(text):
        return QuestionType.LEARNING_PATH, "learning_path_cue"

    if _EXAM_PREP_CUE.search(text):
        return QuestionType.EXAM_PREPARATION, "exam_prep_cue"

    if _REVISION_CUE.search(text):
        return QuestionType.REVISION, "revision_cue"

    if _DERIVATION_CUE.search(text):
        return QuestionType.DERIVATION, "derivation_cue"

    if _FORMULA_CUE.search(text):
        return QuestionType.FORMULA, "formula_cue"

    if _PROCEDURE_CUE.search(text):
        return QuestionType.PROCEDURE, "procedure_cue"

    if _APPLICATION_CUE.search(text):
        return QuestionType.APPLICATION, "application_cue"

    if _EXPLANATION_CUE.search(text):
        return QuestionType.EXPLANATION, "explanation_cue"

    # Fallback: bare "what is X" / concept lookup → DEFINITION
    return QuestionType.DEFINITION, "fallback"
