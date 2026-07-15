"""Concept name normalization, alias resolution, and deduplication."""

from __future__ import annotations

import re
import unicodedata

# Articles and filler words stripped during normalization.
_STRIP_WORDS = {"the", "a", "an", "of", "in", "on", "for", "and", "to", "with"}

# Common NCERT section-number prefix pattern (e.g. "7.2", "13.5.1").
_SECTION_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\s*")

# Standalone numbering tokens embedded in noisy repeated headings or page labels.
_SECTION_NUMBER_TOKEN_RE = re.compile(r"\b\d+(?:\.\d+)*\b")

# Common book/chapter labels that precede the real concept heading.
_LEADING_LABEL_RE = re.compile(r"^(?:unit|chapter)\s+\d+\s+", re.IGNORECASE)

# Trailing page number artifacts.
_TRAILING_PAGE_RE = re.compile(r"\s+\d+$")

# Trailing parenthetical qualifiers: "(continued)", "(Contd.)"
_PAREN_SUFFIX_RE = re.compile(r"\s*\((?:cont(?:inue)?d?\.?|contd\.?)\)\s*$", re.IGNORECASE)

# Roman numeral list markers at start: "I.", "II.", "III."
_ROMAN_PREFIX_RE = re.compile(r"^(?:I{1,3}|IV|VI{0,3}|IX|X)\.\s+", re.IGNORECASE)

# Blocklist for generic structural terms that shouldn't be concepts.
_BLOCKLIST = {
    "introduction", "summary", "conclusion", "preface", "objective", 
    "overview", "solution", "answer", "answers", "notes", "miscellaneous",
    "appendix", "appendices", "bibliography", "references",
    "exercises", "exercise", "all rights reserved", "copyright", "contents", 
    "index", "chapter", "part", "mathematics", "physics", "chemistry", "biology",
    "science", "unit", "topic", "formula"
}

_INSTRUCTIONAL_STARTERS = {
    "describe", "state", "explain", "distinguish", "calculate", "predict",
    "discuss", "determine", "find", "write", "show", "give", "define",
}

_SENTENCE_STARTERS = {"if", "thus", "here", "therefore", "hence", "when", "where"}

_SENTENCE_VERBS = {
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "does", "do", "did", "can", "could", "should", "would", "may", "might",
    "must", "depend", "depends", "know", "stand", "means", "occur", "occurs",
    "affected", "increase", "decrease", "contains", "follow", "get",
}

def _collapse_repeated_heading(text: str) -> str:
    """Collapse obvious duplicate heading artifacts into a single term."""
    tokens = [token for token in text.split() if token]
    if not tokens:
        return ""

    deduped: list[str] = []
    for token in tokens:
        if deduped and token == deduped[-1]:
            continue
        deduped.append(token)

    alpha_tokens = [token for token in deduped if re.search(r"[a-z]", token)]
    if alpha_tokens and len(set(alpha_tokens)) == 1:
        return alpha_tokens[0]

    return " ".join(deduped)


def _merge_split_word_tokens(tokens: list[str]) -> list[str]:
    """Merge OCR-split tokens like ['e', 'lectric', 'c', 'harge'] into words."""
    merged: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if len(token) == 1 and token.isalpha() and index + 1 < len(tokens):
            next_token = tokens[index + 1]
            if next_token.isalpha() and len(next_token) >= 2:
                merged.append(token + next_token)
                index += 2
                continue
        merged.append(token)
        index += 1
    return merged


def _looks_like_sentence(raw: str, normalized: str) -> bool:
    """Reject objective bullets and prose fragments that are not concept headings."""
    stripped = raw.strip()
    words = normalized.split()
    if len(words) < 4:
        return False

    first_word = words[0]
    if stripped.startswith(("•", "·", "-", "*")):
        return True
    if first_word in _INSTRUCTIONAL_STARTERS or first_word in _SENTENCE_STARTERS:
        return True
    if len(words) >= 8 and any(word in _SENTENCE_VERBS for word in words):
        return True
    if stripped.endswith((".", ";", ":")) and len(words) >= 6:
        return True
    if len(words) > 10:
        return True
    return False


def _salvage_unknown_heading(raw: str, normalized: str) -> bool:
    """Allow strong all-caps headings through even when chapter routing is still unknown."""
    stripped = raw.strip()
    words = normalized.split()
    if len(words) < 2:
        return False
    if not stripped.isupper():
        return False
    if any(word in _BLOCKLIST for word in words):
        return False
    return True

def normalize_concept_name(raw: str) -> str:
    """Normalize a raw concept name to a canonical form.

    Steps:
      1. Unicode NFKC normalization.
      2. Strip section numbers ("7.2 Integration" → "Integration").
      3. Strip parenthetical suffixes ("(continued)").
      4. Strip roman-numeral list prefixes.
      5. Collapse whitespace, lowercase.
      6. Remove filler words.
      7. Strip trailing punctuation.
    """
    text = unicodedata.normalize("NFKC", raw).strip()
    text = _SECTION_NUMBER_RE.sub("", text)
    text = _PAREN_SUFFIX_RE.sub("", text)
    text = _ROMAN_PREFIX_RE.sub("", text)
    text = _LEADING_LABEL_RE.sub("", text)
    # Normalize unicode quotes to straight quotes
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    
    # Fix OCR artifacts for apostrophe-s (e.g. "Coulomb ' s Law" or "Gauss 'S")
    text = re.sub(r"\s+'\s*s\b", "'s", text, flags=re.IGNORECASE)
    
    # Remove all non-alphanumeric characters except spaces and hyphens
    text = re.sub(r"[^\w\s\-']", " ", text)
    text = _SECTION_NUMBER_TOKEN_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()

    words = _merge_split_word_tokens(text.split())
    words = [w for w in words if w not in _STRIP_WORDS]
    text = " ".join(words)

    text = _TRAILING_PAGE_RE.sub("", text)
    text = text.rstrip(".:;,")
    return _collapse_repeated_heading(text)


def display_name(raw: str) -> str:
    """Produce a human-readable display name (title-cased, number-stripped)."""
    text = _SECTION_NUMBER_RE.sub("", raw).strip()
    text = _PAREN_SUFFIX_RE.sub("", text).strip()
    text = _LEADING_LABEL_RE.sub("", text)
    text = _SECTION_NUMBER_TOKEN_RE.sub(" ", text)
    text = _TRAILING_PAGE_RE.sub("", text)
    words = [word for word in re.split(r"\s+", text.strip()) if word]
    words = _merge_split_word_tokens(words)
    deduped: list[str] = []
    for word in words:
        if deduped and word.lower() == deduped[-1].lower():
            continue
        deduped.append(word)
    text = " ".join(deduped).strip(" .:;,-")
    if text.isupper() and len(text) > 4:
        text = text.title()
    return text


def is_alias(name_a: str, name_b: str) -> bool:
    """Return True only if the normalized names are exactly equal.
    
    Sub-concepts (like 'symmetric matrix' and 'matrix') are no longer aliases.
    """
    return name_a == name_b


class ConceptResolver:
    """Deduplicates concept candidates within a chapter scope and builds hierarchy."""

    def __init__(self) -> None:
        # chapter → normalized_name → (canonical_name, chapter, set_of_aliases)
        self._registry: dict[str, dict[str, tuple[str, str, set[str]]]] = {}

    def resolve(
        self, raw_name: str, chapter: str
    ) -> tuple[str, str, list[str]]:
        """Resolve a raw concept name within a chapter.

        Returns (canonical_normalized, display_name, aliases).
        """
        norm = normalize_concept_name(raw_name)
        disp = display_name(raw_name)
        
        if not norm or norm in _BLOCKLIST:
            return "", disp, []

        if _looks_like_sentence(raw_name, norm):
            return "", disp, []

        if chapter == "Unknown Chapter" and not _salvage_unknown_heading(raw_name, norm):
            return "", disp, []

        # Must have at least one alphabetic word of length 2+
        if not re.search(r'[a-z]{2,}', norm):
            return "", disp, []

        # Reject names that are overly symbol-heavy (> 30% non-alphanumeric)
        alnum_count = sum(1 for c in norm if c.isalnum() or c.isspace())
        if len(norm) > 0 and (alnum_count / len(norm)) < 0.7:
            return "", disp, []

        chapter_registry = self._registry.setdefault(chapter, {})

        # Check if this name aliases an existing canonical entry.
        for canonical_norm, (canonical_disp, _chapter, aliases) in chapter_registry.items():
            if is_alias(norm, canonical_norm):
                aliases.add(disp)
                aliases.add(norm)
                return canonical_norm, canonical_disp, sorted(aliases - {canonical_disp})

        # New canonical entry.
        chapter_registry[norm] = (disp, chapter, {disp, norm})
        return norm, disp, []

    def all_canonical(self) -> dict[str, dict[str, tuple[str, str, list[str]]]]:
        """Return chapter → norm → (display, chapter, aliases) for all resolved concepts."""
        result: dict[str, dict[str, tuple[str, str, list[str]]]] = {}
        for chapter, entries in self._registry.items():
            result[chapter] = {}
            for norm, (disp, ch, aliases) in entries.items():
                result[chapter][norm] = (disp, ch, sorted(aliases - {disp}))
        return result

    def find_parents(self) -> dict[str, dict[str, str]]:
        """Discover parent-child relationships for concepts within each chapter.
        
        Returns:
            chapter -> child_norm -> parent_norm
        """
        hierarchy: dict[str, dict[str, str]] = {}
        
        for chapter, entries in self._registry.items():
            hierarchy[chapter] = {}
            # Sort norms by length so we can find the longest matching substring
            norms = sorted(entries.keys(), key=len)
            
            for i, child_norm in enumerate(norms):
                best_parent: str | None = None
                # Look at all shorter norms
                for parent_norm in norms[:i]:
                    # Need at least 4 chars to be a meaningful parent
                    if len(parent_norm) < 4:
                        continue
                    # A parent must be a distinct word boundary match inside the child, 
                    # or at least a simple substring match for now.
                    if parent_norm in child_norm:
                        # If there are multiple, we take the longest one (which will 
                        # be the last one we see, since norms is sorted by length).
                        best_parent = parent_norm
                
                if best_parent:
                    hierarchy[chapter][child_norm] = best_parent
                    
        return hierarchy
