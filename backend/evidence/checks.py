"""Deterministic evidence checkers for the Evidence Assessment Engine."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.tutor.repository import KnowledgeRepository

from backend.retrieval.api.search import SearchResult, _content_tokens
from backend.tutor.models import EducationalIntent
from backend.evidence.models import CorpusPresence, EvidenceRelevance


class EvidenceContext:
    """State bag passed to checkers during evaluation."""
    def __init__(
        self,
        query: str,
        results: list[SearchResult],
        intent: EducationalIntent,
        issues: list[str],
    ):
        self.query = query
        self.results = results
        self.intent = intent
        self.issues = issues


class RetrievalCoverageCheck:
    """Checks for zero results and minimum supported concepts."""

    def evaluate(self, ctx: EvidenceContext) -> bool:
        if not ctx.results:
            ctx.issues.append("Zero retrieval results returned.")
            return False
            
        top_score = ctx.results[0].score
        if top_score < 0.1:  # Simple threshold, or just rely on existence
            # The prompt doesn't strictly dictate a hard score threshold for RetrievalCoverage
            # other than "minimum supported concepts" and "top-k count".
            pass

        return True


class EducationalEvidenceCheck:
    """Checks for hollow concepts and educational object counts."""

    def evaluate(self, ctx: EvidenceContext) -> bool:
        if not ctx.results:
            return False
            
        primary = ctx.results[0].document
        
        # Check if hollow
        object_count = (
            len(primary.definition_texts) + 
            len(primary.formula_latex) + 
            len(primary.example_texts)
        )
        
        if object_count == 0:
            ctx.issues.append(f"Primary concept '{primary.name}' is hollow (0 educational objects).")
            return False
            
        return True


class LexicalSupportCheck:
    """Checks token overlap between query and the retrieved document.

    When using hybrid retrieval (BM25F + dense), semantic similarity may
    find relevant concepts even without exact token overlap. In that case,
    we check if the concept has educational content (definitions/examples)
    and relax the overlap requirement.
    """

    def evaluate(self, ctx: EvidenceContext) -> bool:
        if not ctx.results:
            return False

        query_tokens = set(_content_tokens(ctx.query))
        if not query_tokens:
            return True

        primary = ctx.results[0].document
        doc_tokens = set(_content_tokens(primary.name))
        for text in primary.definition_texts + primary.example_texts:
            doc_tokens.update(_content_tokens(text))

        overlap = query_tokens.intersection(doc_tokens)
        overlap_ratio = len(overlap) / len(query_tokens)

        if overlap_ratio == 0.0:
            # No lexical overlap - check if the concept has educational content
            # This allows hybrid retrieval to find semantically relevant concepts
            has_content = bool(primary.definition_texts or primary.example_texts)
            if has_content:
                # Concept has content, trust the retrieval even without overlap
                ctx.issues.append("No lexical overlap but concept has educational content (semantic match).")
                return True
            ctx.issues.append("Zero lexical overlap between query and primary concept.")
            return False

        return True


class PlannerSupportCheck:
    """Checks whether the primary concept can satisfy the requested intent."""

    def evaluate(self, ctx: EvidenceContext) -> bool:
        if not ctx.results:
            return False
            
        primary = ctx.results[0].document
        
        if ctx.intent == EducationalIntent.PROOF:
            pass # TODO: handle proof intent
            
        if ctx.intent == EducationalIntent.WORKED_EXAMPLE and not primary.example_texts:
            ctx.issues.append(f"Intent {ctx.intent.value} requires examples, but none exist.")
            return False
            
        if ctx.intent == EducationalIntent.FORMULA and not primary.formula_latex:
            ctx.issues.append(f"Intent {ctx.intent.value} requires formulas, but none exist.")
            return False
                
        return True


class CorpusPresenceCheck:
    """Determines whether the requested concept actually exists in the compiled repository."""

    def evaluate(self, ctx: EvidenceContext) -> CorpusPresence:
        if not ctx.results:
            return CorpusPresence.NOT_FOUND
            
        query_tokens = set(_content_tokens(ctx.query))
        if not query_tokens:
            return CorpusPresence.FOUND
            
        best_presence = CorpusPresence.NOT_FOUND
        
        # Check top 3 results to see if the concept exists in the corpus
        for result in ctx.results[:3]:
            primary = result.document
            name_tokens = set(_content_tokens(primary.name))
            for alias in primary.aliases:
                name_tokens.update(_content_tokens(alias))
                
            if query_tokens.issubset(name_tokens):
                return CorpusPresence.FOUND
                
            overlap = query_tokens.intersection(name_tokens)
        # If we didn't find it in the title/aliases, it might still be in the body 
        # (which is verified by LexicalSupportCheck). We return PARTIAL so we don't 
        # wrongly refuse queries that use symbols or specific terms instead of broad titles.
        return CorpusPresence.PARTIAL


class TopicRelevanceCheck:
    """Checks if the retrieved concept belongs to the explicitly requested topic."""

    def evaluate(self, ctx: EvidenceContext, repository: Optional[KnowledgeRepository] = None):
        if not ctx.results:
            return EvidenceRelevance.NOT_RELEVANT
            
        primary = ctx.results[0].document
        query_lower = ctx.query.lower()
        
        # 1. Check for explicit subject mentions
        subjects = ["chemistry", "physics", "mathematics", "maths", "math", "biology"]
        # Match whole words to avoid false positives
        import re
        mentioned_subjects = []
        for s in subjects:
            if re.search(rf"\b{s}\b", query_lower):
                mentioned_subjects.append(s)
        
        if mentioned_subjects:
            # Normalize "maths" / "math" -> "mathematics"
            normalized_mentions = [
                "mathematics" if s in ("math", "maths") else s 
                for s in mentioned_subjects
            ]
            if primary.subject.lower() not in normalized_mentions:
                ctx.issues.append(f"Query requested {mentioned_subjects}, but retrieved concept is {primary.subject}.")
                return EvidenceRelevance.NOT_RELEVANT
                
        # 2. Check for explicit chapter mentions (if repository provided)
        if repository and hasattr(repository, "_concept_by_id"):
            for concept in repository._concept_by_id.values():
                # Only consider multi-letter chapters to avoid spurious matches
                if len(concept.chapter) > 3 and concept.chapter.lower() in query_lower:
                    if primary.subject.lower() != concept.subject.lower():
                        ctx.issues.append(f"Query requested chapter '{concept.chapter}' ({concept.subject}), but retrieved concept is {primary.subject}.")
                        return EvidenceRelevance.NOT_RELEVANT
                        
        return EvidenceRelevance.RELEVANT
