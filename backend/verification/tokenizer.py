"""Deterministic text normalization for grounding checks.

Self-contained (no retrieval/generation import) so the verification layer has no
cross-layer coupling. ``content_words`` lowercases, strips punctuation, splits, and drops a
documented generic stop/function-word set plus single characters — leaving the *content*
words a grounding check compares. Connective/function words are intentionally removed so a
provider may rephrase ("the dipole is, therefore, ...") without being flagged, while any
genuinely new content word remains detectable.
"""

from __future__ import annotations

import re
import unicodedata

# Generic English stop/function words + common connectives a renderer may add while
# rephrasing. Subject-agnostic; contains no educational vocabulary and no content-bearing
# nouns (so real content words are never silently hidden).
STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with", "is", "are",
    "was", "were", "be", "been", "being", "am", "it", "its", "as", "at", "from", "by",
    "this", "that", "these", "those", "there", "here", "then", "thus", "therefore",
    "hence", "so", "such", "which", "who", "whom", "whose", "what", "when", "where",
    "why", "how", "we", "you", "they", "he", "she", "our", "your", "their", "his",
    "her", "them", "us", "can", "could", "should", "would", "will", "shall", "may",
    "might", "must", "do", "does", "did", "has", "have", "had", "not", "no", "yes",
    "if", "but", "also", "into", "about", "over", "under", "than", "very", "just",
    "each", "any", "all", "some", "more", "most", "one", "two",
    "important", "note", "example", "performed", "start", "follows", "begin",
    "additionally", "suppose", "consider", "however", "straightforward", "learn",
    "different", "ways", "manipulate", "help", "understand", "applications",
    "better", "details", "refer", "source", "since", "well", "now", "let", "given",
    "find", "want", "look", "analyze", "case", "above", "below", "following",
    "next", "previous", "first", "second", "third", "finally", "lastly", "often",
    "sometimes", "always", "never", "can", "cannot", "could", "would", "should",
    "must", "might", "may", "will", "shall", "ought", "need", "needs", "needed"
})

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def content_words(text: str) -> tuple[str, ...]:
    """Return the ordered content words of ``text`` (stop/function words dropped)."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return tuple(
        tok for tok in text.split()
        if len(tok) > 1 and tok not in STOP_WORDS
    )


def content_word_set(text: str) -> frozenset[str]:
    return frozenset(content_words(text))
