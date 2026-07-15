"""Deterministic lexical retrieval over the Knowledge Index.

The ranker is a BM25F-style field-weighted lexical scorer with bounded
exact-match boosts on top. It is fully deterministic (no embeddings, no
randomness, tie-breaks resolved by a stable key) and subject-agnostic — every
signal comes from generic lexical processing of the query and the document
fields, never from hardcoded subjects or concept names.

Design notes:
  * Text is normalized locally (NFKC, lowercase, punctuation stripped),
    tokenized, stripped of stop words / question words, and lightly stemmed for
    plurals. This is deliberately *not* the concept-heading normalizer used by
    the compiler: that one merges stray single characters into the next word to
    repair OCR ("e lectric" -> "electric"), which corrupts natural-language
    queries ("a solution" -> "asolution"). Retrieval owns its own tokenizer.
  * BM25F scores each document over weighted fields (name > aliases >
    definitions > examples) with per-collection IDF and length normalization,
    so a concise concept name outranks a long/noisy block that merely mentions
    a term.
  * Three mutually exclusive exact-match tiers (query token sequence equals the
    name / an alias / is a subset of the name) add a single bounded boost so
    exact concept lookups rank first, without the additive double-counting that
    previously inflated partial matches.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex

# Generic English stop words plus interrogative/instructional framing words that
# carry no retrieval signal. Subject-agnostic.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with",
        "is", "are", "was", "were", "be", "been", "being", "am",
        "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
        "does", "do", "did", "can", "could", "should", "would", "will", "shall",
        "explain", "define", "describe", "state", "give", "list", "write",
        "mean", "meant", "means", "tell", "about", "between", "into", "by",
        "that", "this", "these", "those", "it", "its", "as", "at", "from",
    }
)

# BM25F parameters.
_K1 = 1.5
_B = 0.75
# Per-field boosts: a match in the concept name matters far more than a mention
# buried in an example.
_FIELD_WEIGHTS: dict[str, float] = {
    "name": 3.0,
    "alias": 2.5,
    "definition": 1.0,
    "example": 0.5,
}

# Bounded, mutually exclusive exact-match boosts (largest wins, only one fires).
_EXACT_NAME_BOOST = 1000.0
_EXACT_ALIAS_BOOST = 500.0
_NAME_SUPERSET_BOOST = 100.0

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_ES_SUFFIXES = ("sses", "shes", "ches", "xes", "zes", "ses")


def _stem(word: str) -> str:
    """Conservative, deterministic plural stemmer for lexical normalization.

    Collapses common English plural forms to a shared stem so that e.g.
    "solution"/"solutions" and "property"/"properties" match. Deliberately
    minimal (no derivational stemming) to avoid over-merging distinct terms.
    """
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in _ES_SUFFIXES:
        if word.endswith(suffix):
            return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _content_tokens(text: str) -> list[str]:
    """Normalize, tokenize, drop stop words / single chars, and stem.

    Returns the ordered content tokens of ``text``. Order is preserved so the
    exact-match tier can compare token *sequences* (which distinguishes
    "Liquid Solutions" from "Liquid-Liquid Solutions").
    """
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return [
        _stem(tok)
        for tok in text.split()
        if len(tok) > 1 and tok not in _STOP_WORDS
    ]


def _counts(tokens: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tokens:
        out[t] = out.get(t, 0) + 1
    return out


@dataclass
class RankingBreakdown:
    bm25: float = 0.0
    title_match: float = 0.0
    phrase_match: float = 0.0
    alias_match: float = 0.0
    object_priority: float = 0.0
    chapter_context: float = 0.0
    final_score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    score: float
    document: KnowledgeDocument
    ranking_breakdown: RankingBreakdown | None = None


class _DocTokens:
    """Precomputed per-field token bags and exact-match signatures for a doc."""

    __slots__ = ("doc", "name_seq", "alias_seqs", "fields", "field_terms", "sort_name")

    def __init__(self, doc: KnowledgeDocument) -> None:
        self.doc = doc
        self.sort_name = doc.name.lower()

        name_tokens = _content_tokens(doc.name)
        self.name_seq: tuple[str, ...] = tuple(name_tokens)
        self.alias_seqs: set[tuple[str, ...]] = {
            tuple(_content_tokens(a)) for a in doc.aliases
        }

        alias_tokens: list[str] = []
        for alias in doc.aliases:
            alias_tokens.extend(_content_tokens(alias))
        def_tokens: list[str] = []
        for text in doc.definition_texts:
            def_tokens.extend(_content_tokens(text))
        ex_tokens: list[str] = []
        for text in doc.example_texts:
            ex_tokens.extend(_content_tokens(text))

        # field -> {term: term-frequency}
        self.fields: dict[str, dict[str, int]] = {
            "name": _counts(name_tokens),
            "alias": _counts(alias_tokens),
            "definition": _counts(def_tokens),
            "example": _counts(ex_tokens),
        }
        # Union of all terms in the doc (for df computation).
        self.field_terms: set[str] = set()
        for counts in self.fields.values():
            self.field_terms.update(counts)


class RetrievalAPI:
    """Deterministic BM25F keyword search over a Knowledge Index."""

    def __init__(self, path: Path):
        self.documents: list[KnowledgeDocument] = []
        self._docs: list[_DocTokens] = []
        self._idf: dict[str, float] = {}
        self._avg_len: dict[str, float] = {}

        if path.exists():
            if path.is_file():
                idx = KnowledgeIndex.model_validate_json(path.read_text())
                self.documents = idx.documents
            else:
                for idx_path in path.rglob("knowledge_index.json"):
                    idx = KnowledgeIndex.model_validate_json(idx_path.read_text())
                    self.documents.extend(idx.documents)
            self._build()

    def _build(self) -> None:
        """Precompute token bags, per-field average lengths, and IDF."""
        self._docs = [_DocTokens(doc) for doc in self.documents]
        n = len(self._docs)
        if n == 0:
            return

        field_len_totals: dict[str, int] = {f: 0 for f in _FIELD_WEIGHTS}
        df: dict[str, int] = {}
        for dt in self._docs:
            for field, counts in dt.fields.items():
                field_len_totals[field] += sum(counts.values())
            for term in dt.field_terms:
                df[term] = df.get(term, 0) + 1

        self._avg_len = {
            field: (total / n) for field, total in field_len_totals.items()
        }
        # BM25 idf with +0.5 smoothing; the "1 +" form keeps it non-negative so a
        # term occurring in most documents never subtracts from the score.
        self._idf = {
            term: math.log(1.0 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return the top_k documents ranked deterministically for the query."""
        query_seq = tuple(_content_tokens(query))
        if not query_seq:
            return []
        unique_terms = set(query_seq)

        scored: list[tuple[float, str, str, KnowledgeDocument]] = []
        for dt in self._docs:
            score = self._bm25f(unique_terms, dt)
            score += self._exact_boost(query_seq, unique_terms, dt)
            if score > 0.0:
                scored.append((score, dt.sort_name, dt.doc.concept_id, dt.doc))

        # Deterministic ordering: score desc, then name, then id.
        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        return [SearchResult(score=round(s, 6), document=doc) for s, _, _, doc in scored[:top_k]]

    def _bm25f(self, query_terms: set[str], dt: _DocTokens) -> float:
        """BM25F score: saturate the field-weighted term frequency once."""
        score = 0.0
        for term in query_terms:
            idf = self._idf.get(term, 0.0)
            if idf <= 0.0:
                continue
            weighted_tf = 0.0
            for field, counts in dt.fields.items():
                tf = counts.get(term, 0)
                if tf == 0:
                    continue
                avg_len = self._avg_len.get(field, 0.0) or 1.0
                field_len = sum(counts.values())
                denom = 1.0 - _B + _B * (field_len / avg_len)
                weighted_tf += _FIELD_WEIGHTS[field] * tf / denom
            if weighted_tf > 0.0:
                score += idf * (weighted_tf * (_K1 + 1.0)) / (_K1 + weighted_tf)
        return score

    def _exact_boost(
        self, query_seq: tuple[str, ...], query_terms: set[str], dt: _DocTokens
    ) -> float:
        """One bounded boost for an exact/subset name or alias hit.

        Compares the query's content-token *sequence* against the document's, so
        "vapour pressure liquid solutions" exactly matches "Vapour Pressure of
        Liquid Solutions" but not "Vapour Pressure of Liquid-Liquid Solutions".
        """
        if query_seq == dt.name_seq:
            return _EXACT_NAME_BOOST
        if query_seq in dt.alias_seqs:
            return _EXACT_ALIAS_BOOST
        if query_terms and query_terms.issubset(set(dt.name_seq)):
            # Every query content-word appears in the concept name.
            return _NAME_SUPERSET_BOOST
        return 0.0
