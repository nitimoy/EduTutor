"""Deterministic query feature extraction for routing.

Extracts observable, generalizable characteristics from the query *text* only.
No hardcoded educational concepts, no ML — just regexes and simple string checks.
An optional concept vocabulary (normalized concept names/aliases from the Knowledge
Index) lets the analyzer detect an *exact concept lookup* without hardcoding any
specific concept.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from pydantic import BaseModel, Field

# Interrogative / instructional lead-ins. Ordered longest-first where a phrase is a
# prefix of another so the most specific matches. All generic English, no domain.
_DEFINITION_LEAD = re.compile(r"^\s*(define|definition of|what (is|are|do|does)\b|what'?s\b)", re.IGNORECASE)
_EXPLANATION_LEAD = re.compile(r"^\s*(explain|describe|how (do|does|is|are|can)\b|why\b|discuss|elaborate)", re.IGNORECASE)
_COMPARISON_LEAD = re.compile(r"\b(difference between|compare|versus|vs\.?|distinguish between|contrast)\b", re.IGNORECASE)

# Mathematical notation / symbol-heavy signal (non-ASCII math, operators, digits+ops).
_MATH_SYMBOLS = set("=+×÷−∫∑∏√±≤≥≠≈∞θπαβγλμσΔ∂∇^_/*")
_MATH_TOKEN_RE = re.compile(r"[A-Za-z]\s*[=><]\s*[A-Za-z0-9]|\b\d+\s*[+\-*/^]\s*\d+")

# Quoted spans: "straight" or ‘curly’ / “curly”.
_QUOTED_RE = re.compile(r"[\"“”'‘’]([^\"“”'‘’]{2,})[\"“”'‘’]")

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset({
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with", "is",
    "are", "was", "were", "be", "what", "which", "how", "does", "do", "did",
    "the", "that", "this", "between", "difference", "explain", "define", "why",
})


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _content_words(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if len(w) > 1 and w not in _STOP]


class QueryFeatures(BaseModel):
    """Observable, deterministic characteristics of a query."""

    length_tokens: int = 0
    is_definition: bool = False        # "what is X", "define X"
    is_explanation: bool = False       # "how/why/explain X"
    is_comparison: bool = False        # "difference between X and Y"
    has_math_notation: bool = False    # symbols/operators/equation tokens
    has_quoted_phrase: bool = False
    quoted_phrases: list[str] = Field(default_factory=list)
    exact_concept_match: bool = False  # content words == a known concept's words
    matched_concept: Optional[str] = None


def analyze_query(
    query: str,
    concept_vocab: Optional[dict[frozenset, str]] = None,
) -> QueryFeatures:
    """Extract routing features from ``query``.

    Args:
        query: raw student query.
        concept_vocab: optional map from a frozenset of a concept's content words
            to its display name (built once from the Knowledge Index). Used to
            detect an exact concept lookup generically — the router never hardcodes
            concept names, it just checks whether the query's content words *are*
            some concept's content words.
    """
    text = _normalize(query)
    features = QueryFeatures()

    words = _content_words(text)
    features.length_tokens = len(words)

    features.is_comparison = bool(_COMPARISON_LEAD.search(text))
    # Definition vs explanation: comparison takes precedence over both if present.
    if not features.is_comparison:
        features.is_definition = bool(_DEFINITION_LEAD.match(text))
        features.is_explanation = bool(_EXPLANATION_LEAD.match(text))

    features.has_math_notation = (
        any(ch in _MATH_SYMBOLS for ch in text) or bool(_MATH_TOKEN_RE.search(text))
    )

    quoted = [m.group(1).strip() for m in _QUOTED_RE.finditer(text)]
    features.quoted_phrases = quoted
    features.has_quoted_phrase = bool(quoted)

    if concept_vocab:
        # Exact concept lookup if the query's content words (or a quoted phrase's)
        # exactly equal some concept's content words.
        candidates = [words] + [_content_words(p) for p in quoted]
        for cand in candidates:
            key = frozenset(cand)
            if key and key in concept_vocab:
                features.exact_concept_match = True
                features.matched_concept = concept_vocab[key]
                break

    return features


def build_concept_vocab(names_and_aliases: list[str]) -> dict[frozenset, str]:
    """Build the exact-lookup vocabulary from concept names/aliases.

    Keyed by the frozenset of each name's content words so word-order and stop
    words don't matter. Generic — the caller passes whatever the Knowledge Index
    contains; no concept is special-cased here.
    """
    vocab: dict[frozenset, str] = {}
    for name in names_and_aliases:
        key = frozenset(_content_words(name))
        if key:
            vocab.setdefault(key, name)
    return vocab
