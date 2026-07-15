"""Deterministic educational-intent detection for the Tutor Brain.

Reuses the frozen retrieval query analyzer (``analyze_query`` / ``QueryFeatures``) for
the observable features it already computes (definition / explanation / comparison form,
math notation, quoted phrase, length) and layers a first-match precedence rule table on
top for the intents the analyzer doesn't name (proof, formula, worked_example,
prerequisite, application, revision).

Pure regex/keyword predicates over the query text — subject-agnostic, no hardcoded
educational concepts, no ML. First match wins, mirroring ``routing/rules.py``.
"""

from __future__ import annotations

import re

from backend.retrieval.routing.analyzer import QueryFeatures, analyze_query
from backend.tutor.models import EducationalIntent

# Generic lexical cues. All subject-agnostic; none names a concept.
_PROOF_CUE = re.compile(r"\b(prove|proof|derive|derivation|derived|show that)\b", re.I)
_FORMULA_CUE = re.compile(r"\b(formula|equation|expression for|write the expression)\b", re.I)
_WORKED_EXAMPLE_CUE = re.compile(
    r"\b(worked example|example|solve|calculate|compute|evaluate|numerical|problem)\b", re.I
)
_PREREQUISITE_CUE = re.compile(
    r"\b(prerequisite|prerequisites|need to know|needed to|required to understand"
    r"|before learning|know before|come before|comes before"
    r"|where should i start|how to learn|how should i learn)\b",
    re.I,
)
_CLASSIFICATION_CUE = re.compile(
    r"\b(types of|classification|classify|different kinds of|types)\b",
    re.I,
)
_APPLICATION_CUE = re.compile(
    r"\b(applications?|used|uses|use of|applied|real[- ]life|daily life|everyday)\b", re.I
)
_REVISION_CUE = re.compile(
    r"\b(revise|revision|summary|summarise|summarize|recap|revision notes)\b", re.I
)


def detect_intent(query: str) -> tuple[EducationalIntent, QueryFeatures]:
    """Classify ``query`` into an :class:`EducationalIntent`.

    Returns the intent plus the underlying :class:`QueryFeatures` (useful to the
    organizer / strategy stages and to tests). Deterministic: a given query always
    yields the same intent.
    """
    features = analyze_query(query)
    text = query or ""

    # First-match precedence (most specific → least). Comparison is decided by the
    # frozen analyzer; the rest are lexical cues checked before the generic
    # explanation/definition fallbacks.
    if features.is_comparison:
        return EducationalIntent.COMPARISON, features
    if _PROOF_CUE.search(text):
        return EducationalIntent.PROOF, features
    if _FORMULA_CUE.search(text):
        return EducationalIntent.FORMULA, features
    if _WORKED_EXAMPLE_CUE.search(text):
        return EducationalIntent.WORKED_EXAMPLE, features
    if _CLASSIFICATION_CUE.search(text):
        return EducationalIntent.EXPLANATION, features
    if _PREREQUISITE_CUE.search(text):
        return EducationalIntent.PREREQUISITE, features
    if _APPLICATION_CUE.search(text):
        return EducationalIntent.APPLICATION, features
    if _REVISION_CUE.search(text):
        return EducationalIntent.REVISION, features
    if features.is_explanation:
        return EducationalIntent.EXPLANATION, features
    # Bare concept lookups and "what is X" both fall through to definition, the safest
    # compiler-backed default (every concept carries a name, usually a definition).
    return EducationalIntent.DEFINITION, features
