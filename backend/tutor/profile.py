"""Query response profiling — detecting depth, teaching goal, subject, and scope before retrieval.

Separates *what* to teach (intent) from *how much* to teach (depth) and the
*pedagogical strategy* (teaching goal). Also detects the subject domain to
enable subject-filtered retrieval, and the query scope to enable multi-concept retrieval.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from backend.retrieval.routing.analyzer import QueryFeatures
from backend.tutor.intent import detect_intent
from backend.tutor.models import EducationalIntent, ResponseDepth, TeachingGoal


class QueryScope(str, Enum):
    """The scope of a query — determines how many concepts to retrieve."""
    SINGLE_CONCEPT = "single_concept"      # "What is X?"
    MULTI_CONCEPT = "multi_concept"        # "Compare X and Y"
    CHAPTER_LEVEL = "chapter_level"        # "Teach me matrices"
    LEARNING_PATH = "learning_path"        # "What should I study before X?"


# ---------------------------------------------------------------------------
# Subject detection — lexical keyword matching, subject-agnostic patterns.
# ---------------------------------------------------------------------------

_MATH_KEYWORDS = re.compile(
    r"\b(matrix|matrices|determinant|determinants|calculus|integral|integrals"
    r"|derivative|derivatives|function|functions|relation|relations|set\b|sets\b"
    r"|symmetric|skew|transpose|inverse|polynomial|polynomials"
    r"|algebra|trigonometry|trigonometric|probability|permutation|combination"
    r"|sequence|sequences|series|limit|limits|continuity|differentiability"
    r"|maxima|minima|area|linear|quadratic|equation|equations"
    r"|vector|vectors|dot\s+product|cross\s+product"
    r"|complex\s+number|modulus|argument)\b",
    re.I,
)

_PHYSICS_KEYWORDS = re.compile(
    r"\b(electric|electricity|electrostatic|electrostatics|magnetic|magnetism"
    r"|force|forces|current|voltage|resistance|resistivity|capacitance|capacitor"
    r"|flux|charge|charges|coulomb|ohm|kirchhoff|wheatstone"
    r"|dipole|electric\s+dipole|magnetic\s+dipole"
    r"|electromagnetic|electromotive|emf"
    r"|gravitational|gravity|motion|velocity|acceleration|momentum"
    r"|thermodynamics|thermal|heat|temperature|entropy"
    r"|optics|reflection|refraction|wave|waves|frequency|wavelength"
    r"|nucleus|nuclear|radioactive|fission|fusion"
    r"|conductors?|insulators?|semiconductors?|diode|transistor)\b",
    re.I,
)

_CHEMISTRY_KEYWORDS = re.compile(
    r"\b(chemical|chemistry|reaction|reactions|solution|solutions|acid|acids"
    r"|base|bases|electrochemistry|electrolysis|electrode|electrodes"
    r"|battery|cell|galvanic|electrolytic|faraday"
    r"|molecule|molecules|bond|bonds|bonding|covalent|ionic|metallic"
    r"|compound|compounds|element|elements|periodic"
    r"|organic|inorganic|hydrocarbon|alkane|alkene|alkyne"
    r"|oxidation|reduction|redox|oxidizing|reducing"
    r"|equilibrium|thermodynamics|thermochemistry|enthalpy|entropy|gibbs"
    r"|kinetics|catalyst|rate\s+of\s+reaction"
    r"|coordination|complex\s+compound|ligand|isomerism"
    r"|polymer|polymers|biomolecule|protein|carbohydrate|lipid)\b",
    re.I,
)

# Subject name normalization
_SUBJECT_NORMALIZE: dict[str, str] = {
    "math": "mathematics",
    "maths": "mathematics",
    "physics": "physics",
    "chemistry": "chemistry",
}


def detect_subject(query: str) -> Optional[str]:
    """Detect the academic subject from query keywords.

    Returns ``"mathematics"``, ``"physics"``, or ``"chemistry"`` if a subject
    is detected with confidence, or ``None`` if the query is ambiguous.
    Deterministic: identical inputs always produce identical outputs.
    """
    if not query:
        return None

    text = query.lower()

    # Check for explicit subject mentions first (highest confidence).
    for name, normalized in _SUBJECT_NORMALIZE.items():
        if re.search(rf"\b{name}\b", text):
            return normalized

    # Count keyword hits per subject.
    math_hits = len(_MATH_KEYWORDS.findall(text))
    physics_hits = len(_PHYSICS_KEYWORDS.findall(text))
    chemistry_hits = len(_CHEMISTRY_KEYWORDS.findall(text))

    hits = {
        "mathematics": math_hits,
        "physics": physics_hits,
        "chemistry": chemistry_hits,
    }

    max_hits = max(hits.values())
    if max_hits == 0:
        return None

    # Require at least 1 keyword and a clear winner (no tie at the top).
    winners = [s for s, h in hits.items() if h == max_hits]
    if len(winners) == 1:
        return winners[0]

    # Tie — return None (ambiguous).
    return None


# ---------------------------------------------------------------------------
# Query Scope Detection — determines how many concepts to retrieve.
# ---------------------------------------------------------------------------

# Broad topic patterns: linguistically universal, NOT topic-specific.
# These detect when a user asks for an overview of a broad area.
# Works for ANY subject: math, physics, chemistry, biology, etc.
_BROAD_TOPIC_CUE = re.compile(
    r"\b(tell\s+me\s+about\s+)"
    r"|(\bwhat\s+(?:are|is)\s+(?:all\s+the\s+)?(?:the\s+)?(?:types?\s+of|kinds?\s+of|aspects?\s+of|parts?\s+of)\b)"
    r"|(\bgive\s+(?:me\s+)?(?:an?\s+)?(?:overview|summary|introduction|brief)\s+(?:of|about)\b)"
    r"|(\blist\s+(?:all\s+)?(?:the\s+)?(?:types?\s+of|kinds?\s+of|aspects?\s+of)\b)"
    r"|(\bexplain\s+(?:all\s+about|the\s+basics?\s+of|the\s+fundamentals?\s+of)\b)"
    r"|(\bteach\s+(?:me\s+)?(?:the\s+)?(?:basics?\s+of|fundamentals?\s+of|introduction\s+to)\b)"
    r"|(\bhow\s+(?:does|do)\s+\w+\s+(?:work|operate|function)\b)"
    r"|(\bwhat\s+(?:are|is)\s+\w+\s+used?\s+for\b)",
    re.I,
)

# Multi-concept patterns: "compare X and Y", "difference between X and Y"
_MULTI_CONCEPT_CUE = re.compile(
    r"\b(compare|difference\s+between|differences\s+between|vs\.?|versus"
    r"|relate\s+\w+\s+to)\b",
    re.I,
)

# Learning path patterns: "what should I study before X"
_LEARNING_PATH_CUE = re.compile(
    r"\b(prerequisite|prerequisites|before\s+(?:learning|studying)"
    r"|what\s+should\s+i\s+study\s+before"
    r"|where\s+should\s+i\s+start)\b",
    re.I,
)


def detect_scope(query: str, intent: EducationalIntent) -> QueryScope:
    """Detect the scope of a query — how many concepts to retrieve.

    Returns QueryScope enum indicating whether the query needs:
    - SINGLE_CONCEPT: one concept (e.g., "What is X?")
    - MULTI_CONCEPT: two or more concepts (e.g., "Compare X and Y")
    - CHAPTER_LEVEL: entire chapter coverage (e.g., "Teach me matrices")
    - LEARNING_PATH: prerequisite graph traversal (e.g., "What should I study before X?")
    """
    text = query.lower().strip()

    # Learning path queries
    if _LEARNING_PATH_CUE.search(text):
        return QueryScope.LEARNING_PATH

    # Multi-concept queries (comparison)
    if _MULTI_CONCEPT_CUE.search(text):
        return QueryScope.MULTI_CONCEPT

    # Broad topic queries detected by linguistic patterns (subject-agnostic)
    if _BROAD_TOPIC_CUE.search(text):
        return QueryScope.CHAPTER_LEVEL

    # Check for revision/exam prep with broad scope
    if intent == EducationalIntent.REVISION:
        return QueryScope.CHAPTER_LEVEL

    # Default: single concept
    return QueryScope.SINGLE_CONCEPT


class ResponseProfile(BaseModel):
    """The full pedagogical profile of the user's request."""

    query: str
    intent: EducationalIntent
    depth: ResponseDepth
    goal: TeachingGoal
    subject: Optional[str] = None
    scope: QueryScope = QueryScope.SINGLE_CONCEPT


_VERY_DETAILED_CUE = re.compile(r"\b(everything|all about|comprehensive|in depth|exhaustively)\b", re.I)
_LONG_CUE = re.compile(r"\b(in detail|detailed|elaborate on|teach me)\b", re.I)
_SHORT_CUE = re.compile(r"\b(brief|short|quick|simply|tl;dr|summary|what is|define)\b", re.I)


def _detect_depth(query: str, features: QueryFeatures) -> ResponseDepth:
    """Determine the required depth of the response based on lexical cues and length."""
    text = query or ""
    
    if _VERY_DETAILED_CUE.search(text):
        return ResponseDepth.VERY_DETAILED
    if _LONG_CUE.search(text):
        return ResponseDepth.LONG
        
    # If the user explicitly asks for short/brief, or asks a simple definitional question.
    if _SHORT_CUE.search(text):
        return ResponseDepth.SHORT
        
    # If it's a "why" or "how" question without length modifiers, it needs a bit more room.
    if features.is_explanation:
        return ResponseDepth.MEDIUM
        
    # Default fallback.
    return ResponseDepth.MEDIUM


def _detect_goal(intent: EducationalIntent) -> TeachingGoal:
    """Map the raw educational intent to a concrete pedagogical goal."""
    if intent in (EducationalIntent.DEFINITION, EducationalIntent.EXPLANATION):
        return TeachingGoal.INTRODUCE_CONCEPT
    if intent == EducationalIntent.COMPARISON:
        return TeachingGoal.CLASSIFY_OR_COMPARE
    if intent == EducationalIntent.PREREQUISITE:
        return TeachingGoal.LEARNING_PATH
    if intent in (EducationalIntent.WORKED_EXAMPLE, EducationalIntent.APPLICATION):
        return TeachingGoal.SOLVE_PROBLEM
    if intent == EducationalIntent.PROOF:
        return TeachingGoal.PROVE_STATEMENT
    if intent == EducationalIntent.FORMULA:
        return TeachingGoal.FORMULA_REFERENCE
    if intent == EducationalIntent.REVISION:
        return TeachingGoal.REVISE
    return TeachingGoal.INTRODUCE_CONCEPT


class ResponseProfiler:
    """Builds the response profile dictating depth and teaching goal."""

    @staticmethod
    def build(query: str) -> ResponseProfile:
        intent, features = detect_intent(query)
        return ResponseProfile(
            query=query,
            intent=intent,
            depth=_detect_depth(query, features),
            goal=_detect_goal(intent),
            subject=detect_subject(query),
            scope=detect_scope(query, intent),
        )
