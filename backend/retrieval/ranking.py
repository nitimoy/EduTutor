"""Educational Concept Ranker to boost relevant educational results over pure BM25."""

import re
import unicodedata
from typing import Dict, List
from backend.retrieval.api.search import SearchResult, RankingBreakdown, _STOP_WORDS
from backend.tutor.profile import ResponseProfile
from backend.tutor.models import TeachingGoal, EducationalIntent

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")

# Classification query pattern — "types of X", "different kinds of X", etc.
_CLASSIFICATION_QUERY = re.compile(
    r"\b(types?\s+of|different\s+kinds?\s+of|kinds?\s+of|categories?\s+of|list\s+the\s+types?)\b",
    re.I,
)

# Concept-type keywords for disambiguation.
# When query mentions these, boost concepts that are about the base topic.
_CONCEPT_TYPE_KEYWORDS = {
    "relation": ["relation", "relations", "types of relations", "empty relation", 
                 "universal relation", "equivalence relation"],
    "function": ["function", "functions", "types of functions", "domain", "range",
                 "one-one", "onto", "bijective"],
    "matrix": ["matrix", "matrices", "types of matrices", "square matrix", 
               "zero matrix", "identity matrix"],
    "inverse": ["inverse", "inverse trigonometric", "principal value"],
}

def _normalize(text: str) -> str:
    """Normalize and tokenize text for comparison."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return text

def _tokenize(text: str) -> set[str]:
    """Tokenize and remove stop words."""
    return {
        tok for tok in _normalize(text).split()
        if len(tok) > 1 and tok not in _STOP_WORDS
    }


# Map teaching goals to fields that indicate an object satisfies that goal.
# If a document has these fields populated, it gets an educational priority boost.
OBJECT_PRIORITIES: Dict[TeachingGoal, List[str]] = {
    TeachingGoal.INTRODUCE_CONCEPT: ["definition_texts", "paragraphs"],
    TeachingGoal.CLASSIFY_OR_COMPARE: ["classifications", "tables", "comparisons"],
    TeachingGoal.LEARNING_PATH: ["prerequisites"],
    TeachingGoal.SOLVE_PROBLEM: ["example_texts", "exercises"],
    TeachingGoal.PROVE_STATEMENT: ["proofs", "derivations"],
    TeachingGoal.FORMULA_REFERENCE: ["formula_latex", "summaries"],
    TeachingGoal.REVISE: ["formula_latex", "summaries"],
}


class ConceptRanker:
    """Re-ranks Candidate Documents using additive boosts.
    
    Keeps the underlying BM25 score and adds heuristic boosts on top.
    Boost weights:
    - Exact Title Match: +2.0 (query tokens ⊂ title tokens)
    - Name-in-Query: +1.5 (title tokens ⊂ query tokens — concept is the base of a broader query)
    - Partial Title Match: up to +0.5 (intersection-based)
    - Exact Phrase: +0.5
    - Alias Match: +0.3
    - Object Priority: +0.75
    - Chapter Context: +0.2
    - Classification Boost: +1.0 (for "types of X" queries matching the base concept)
    """
    
    def rank(self, query: str, profile: ResponseProfile, results: list[SearchResult]) -> list[SearchResult]:
        if not results:
            return []

        q_tokens = _tokenize(query)
        q_norm = _normalize(query)
        is_classification = bool(_CLASSIFICATION_QUERY.search(query))
        is_definition = profile.intent == EducationalIntent.DEFINITION
        # Detect operation/manipulation intent in query
        is_operation_query = bool(re.search(
            r'\b(manipulation|operations?|methods?|techniques?|arithmetic|algebra)\b',
            query, re.I))

        reranked = []
        for r in results:
            breakdown = RankingBreakdown(bm25=r.score)
            reasons = []
            final_score = r.score

            # 0. Hollow concept penalty: concepts with 0 educational objects
            #    are fragments or empty entries and should not rank highly.
            object_count = (
                len(r.document.definition_texts) +
                len(r.document.formula_latex) +
                len(r.document.example_texts)
            )
            if object_count == 0:
                final_score -= 3.0
                reasons.append("Hollow concept penalty")

            # 0b. For definition queries, cap BM25 contribution for concepts without definitions.
            #     But skip the cap if the concept name is an EXACT match for the query
            #     (e.g., "Matrix" for "what is matrix?") — the user clearly wants that concept.
            title_tokens_check = _tokenize(r.document.name)
            is_exact_name_match = q_tokens and q_tokens.issubset(title_tokens_check)
            if is_definition and not r.document.definition_texts and r.document.example_texts and not is_exact_name_match:
                # Cap BM25 at 5.0 for concepts with only examples (unless exact name match)
                if breakdown.bm25 > 5.0:
                    final_score -= (breakdown.bm25 - 5.0)
                    breakdown.bm25 = 5.0
                    reasons.append("BM25 capped (no definitions)")
            
            # 1. Exact Title Match (query tokens ⊂ title tokens)
            title_norm = _normalize(r.document.name)
            title_tokens = _tokenize(r.document.name)

            if q_tokens and title_tokens.issubset(q_tokens):
                # 2. Name-in-Query: the concept name is a subset of the query
                #    (e.g., "Matrix" for "what is matrix?")
                #    This is the BEST match — the concept IS what was asked.
                coverage = len(title_tokens) / len(q_tokens) if q_tokens else 0
                boost = round(2.5 * coverage, 2)
                breakdown.title_match = boost
                final_score += boost
                reasons.append(f"Name-in-query ({coverage:.0%} coverage)")
            elif q_tokens and q_tokens.issubset(title_tokens):
                # 1b. Query tokens in title: concept contains the query but is more specific
                #     (e.g., "probability" in "Multiplication Theorem on Probability")
                #     Give a moderate boost but prefer exact name matches.
                coverage = len(q_tokens) / len(title_tokens) if title_tokens else 0
                boost = round(1.0 * coverage, 2)
                breakdown.title_match = boost
                final_score += boost
                reasons.append(f"Query-in-title ({coverage:.0%} coverage)")
            elif q_tokens:
                intersection = len(q_tokens.intersection(title_tokens))
                partial = (intersection / max(len(q_tokens), len(title_tokens))) * 0.5
                breakdown.title_match = round(partial, 2)
                final_score += breakdown.title_match
                if partial > 0:
                    reasons.append("Partial title match")
                
            # 3. Exact Phrase Match
            if q_norm in title_norm and q_norm != title_norm:
                breakdown.phrase_match = 0.5
                final_score += 0.5
                reasons.append("Exact phrase match")
                
            # 4. Alias Match (using only compiler metadata)
            for alias in r.document.aliases:
                if q_norm in _normalize(alias):
                    breakdown.alias_match = 0.3
                    final_score += 0.3
                    reasons.append("Alias match")
                    break
                    
            # 5. Educational Object Priority
            priority_fields = OBJECT_PRIORITIES.get(profile.goal, [])
            has_priority = False
            for field in priority_fields:
                if hasattr(r.document, field) and getattr(r.document, field):
                    has_priority = True
                    break

            if has_priority:
                breakdown.object_priority = 0.75
                final_score += 0.75
                reasons.append(f"{profile.goal.value} preferred")

            # 5b. Definition content boost: for "what is X" / "define X" queries,
            #     strongly boost concepts that have definitions over those with only examples.
            if is_definition and r.document.definition_texts:
                def_boost = min(5.0, len(r.document.definition_texts) * 0.5)
                breakdown.object_priority = max(breakdown.object_priority, def_boost)
                final_score += def_boost
                reasons.append(f"Definition content ({len(r.document.definition_texts)} defs)")
            elif is_definition and not r.document.definition_texts and r.document.example_texts:
                # Penalize concepts with only examples when user wants a definition
                # But don't penalize operation concepts for operation queries
                if not (is_operation_query and any(op in r.document.name.lower() for op in ['operation', 'multiplication', 'addition', 'subtraction', 'transpose', 'scalar', 'negative'])):
                    final_score -= 10.0
                    reasons.append("No definitions (examples only)")

            # 5c. Operation concept boost: for queries about manipulation/operations,
            #     boost concepts that are about operations (addition, multiplication, etc.)
            if is_operation_query:
                name_lower = r.document.name.lower()
                if any(op in name_lower for op in ['operation', 'multiplication', 'addition', 'subtraction', 'transpose', 'scalar', 'negative', 'inverse']):
                    op_boost = 15.0
                    final_score += op_boost
                    reasons.append(f"Operation concept match")
                
            # 6. Chapter Context (Basic keyword match for now, kept small)
            if r.document.chapter and _normalize(r.document.chapter) in q_norm:
                breakdown.chapter_context = 0.2
                final_score += 0.2
                reasons.append("Chapter match")

            # 7. Classification boost: for "types of X" queries, boost the base concept
            #    (e.g., "Matrix" for "types of matrices") if it matches the subject word.
            if is_classification and title_tokens:
                # Extract the subject word from the query (the word after "types of", etc.)
                subj_match = re.search(
                    r"(?:types?\s+of|different\s+kinds?\s+of|kinds?\s+of|categories?\s+of)\s+(\w+)",
                    query, re.I,
                )
                if subj_match:
                    subj_word = _normalize(subj_match.group(1))
                    if subj_word and subj_word in title_tokens:
                        # The concept name contains the subject word — strong boost
                        classification_boost = 1.0
                        breakdown.object_priority = max(
                            breakdown.object_priority, classification_boost)
                        final_score += classification_boost
                        reasons.append("Classification subject match")

            # 8. Concept-type disambiguation: when query mentions a base concept type,
            #    boost concepts that are about that type, not related concepts.
            #    E.g., "checking whether a relation is a function" should boost
            #    "Types of Relations" over "Invertible Function".
            for concept_type, type_keywords in _CONCEPT_TYPE_KEYWORDS.items():
                if concept_type in q_tokens:
                    # Check if this concept is about the same topic
                    concept_name_lower = _normalize(r.document.name)
                    for kw in type_keywords:
                        if kw in concept_name_lower:
                            # Same topic — boost
                            type_boost = 0.5
                            breakdown.alias_match = max(breakdown.alias_match, type_boost)
                            final_score += type_boost
                            reasons.append(f"Concept-type match ({concept_type})")
                            break
                    # Check if this concept is too specific (e.g., "Invertible Function"
                    # when query is about "relation is a function")
                    # Penalize concepts that are more specific than the query topic
                    specificity_penalty = 0.0
                    if concept_type == "relation" and "function" in title_tokens:
                        # Query is about relations, but concept is about functions
                        specificity_penalty = -0.3
                    elif concept_type == "function" and "relation" in title_tokens:
                        # Query is about functions, but concept is about relations
                        specificity_penalty = -0.3
                    if specificity_penalty < 0:
                        final_score += specificity_penalty
                        reasons.append(f"Specificity penalty ({concept_type})")
                    break

            breakdown.final_score = round(final_score, 4)
            breakdown.reasons = reasons
            
            # Create a new result with the updated score and breakdown
            reranked.append(
                SearchResult(
                    score=breakdown.final_score,
                    document=r.document,
                    ranking_breakdown=breakdown
                )
            )

        # Sort descending by final score
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked
