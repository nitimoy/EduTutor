"""Tests for deterministic educational-intent detection."""

from backend.tutor.intent import detect_intent
from backend.tutor.models import EducationalIntent


def _intent(query: str) -> EducationalIntent:
    return detect_intent(query)[0]


def test_definition():
    assert _intent("What is an electric dipole?") == EducationalIntent.DEFINITION


def test_bare_concept_defaults_to_definition():
    assert _intent("electric dipole") == EducationalIntent.DEFINITION


def test_explanation():
    assert _intent("Explain how flux relates to charge") == EducationalIntent.EXPLANATION
    assert _intent("Why do conductors shield fields?") == EducationalIntent.EXPLANATION


def test_comparison_takes_precedence_over_definition():
    # "what is the difference between" is both a 'what is' and a comparison → comparison.
    assert _intent("What is the difference between AC and DC?") == EducationalIntent.COMPARISON


def test_proof_takes_precedence_over_formula():
    # 'derive ... formula' contains a formula cue but proof is checked first.
    assert _intent("Derive the formula for kinetic energy") == EducationalIntent.PROOF
    assert _intent("Prove Coulomb's law") == EducationalIntent.PROOF


def test_formula():
    assert _intent("What is the formula for Coulomb's law?") == EducationalIntent.FORMULA
    assert _intent("Give the equation of motion") == EducationalIntent.FORMULA


def test_worked_example():
    assert _intent("Give a worked example of a dipole") == EducationalIntent.WORKED_EXAMPLE
    assert _intent("Solve a numerical on boiling point") == EducationalIntent.WORKED_EXAMPLE


def test_prerequisite():
    assert _intent("What do I need to know before learning integration?") == EducationalIntent.PREREQUISITE
    assert _intent("prerequisites for calculus") == EducationalIntent.PREREQUISITE


def test_application():
    assert _intent("What are the applications of osmosis?") == EducationalIntent.APPLICATION
    assert _intent("Where is Coulomb's law used?") == EducationalIntent.APPLICATION


def test_revision():
    assert _intent("Revise electric dipole") == EducationalIntent.REVISION
    assert _intent("Give a summary of solutions") == EducationalIntent.REVISION


def test_deterministic():
    a = [_intent("What is an electric dipole?") for _ in range(5)]
    assert len(set(a)) == 1


def test_returns_features():
    intent, features = detect_intent("What is the difference between AC and DC?")
    assert intent == EducationalIntent.COMPARISON
    assert features.is_comparison
