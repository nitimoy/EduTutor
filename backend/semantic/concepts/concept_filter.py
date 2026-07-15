import re
from enum import Enum
import logging
from typing import Any

from backend.compiler.models import EducationalIR, EducationalObject
from backend.semantic.concepts.concept_builder import (
    _break_parent_cycles,
    _prune_dangling_parents,
    _rebuild_sub_concepts,
)
from backend.semantic.concepts.concept_models import Concept, ConceptIndex, ConceptReference

logger = logging.getLogger(__name__)

class ConceptStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    PROBABLE = "PROBABLE"
    REJECTED = "REJECTED"


class ConceptFilter:
    """Filters noisy candidate concepts deterministically."""

    # Common English stop words to filter conversational/explanatory text
    STOP_WORDS = {
        "the", "and", "a", "to", "of", "in", "i", "is", "that", "it", "on", "you", 
        "this", "for", "but", "with", "are", "have", "be", "at", "or", "as", "was", 
        "so", "if", "out", "not", "we", "can", "they", "by", "what", "how", "why",
        "which", "there", "their", "will", "would", "from", "when", "an", "then"
    }

    FRONT_MATTER_RE = re.compile(r'(editorial committee|chief advisor|publication|acknowledgement|foreword|preface|contents|copyright|all rights reserved|ncert)', re.I)
    STRUCTURAL_RE = re.compile(r'^(chapter \d+|summary|introduction|exercises?|conclusion|objectives?|appendix|answers?)$', re.I)
    METADATA_RE = re.compile(r'^(isbn|pd \d+t|price :|reprint|edition|printed on|published at)', re.I)

    def filter(self, index: ConceptIndex, ir: EducationalIR) -> ConceptIndex:
        """Filters a ConceptIndex, returning only accepted/probable concepts."""
        obj_map = {obj.id: obj for obj in ir.book.objects}
        
        filtered_concepts = []
        accepted = 0
        probable = 0
        rejected = 0

        # Group references by concept_id
        concept_refs = {}
        for ref in index.references:
            concept_refs.setdefault(ref.concept_id, []).append(ref)

        for concept in index.concepts:
            refs = concept_refs.get(concept.id, [])
            score, status, reason = self._score_concept(concept, refs, obj_map)
            concept.confidence = score  # Override confidence with filter score
            
            if status in (ConceptStatus.ACCEPTED, ConceptStatus.PROBABLE):
                filtered_concepts.append(concept)
                if status == ConceptStatus.ACCEPTED:
                    accepted += 1
                else:
                    probable += 1
            else:
                rejected += 1
                logger.info(f"Rejected Concept: '{concept.name}' (Score: {score:.2f}) Reason: {reason}")

        logger.info(f"Concept Filtering: {accepted} accepted, {probable} probable, {rejected} rejected")

        # Dropping concepts can leave survivors pointing at a rejected parent,
        # so re-enforce parent-graph integrity (dangling parents, cycles, and
        # child lists) on the filtered set before returning.
        surviving = {c.id: c for c in filtered_concepts}
        _prune_dangling_parents(surviving)
        _break_parent_cycles(surviving)
        _rebuild_sub_concepts(surviving)

        # Update index with filtered concepts
        # We also need to filter references pointing to rejected concepts
        valid_ids = {c.id for c in filtered_concepts}
        filtered_references = [ref for ref in index.references if ref.concept_id in valid_ids]
        
        # Calculate unlinked objects
        linked_obj_ids = {ref.object_id for ref in filtered_references}
        all_obj_ids = {obj.id for obj in ir.book.objects if obj.type in ("paragraph", "heading", "definition", "theorem", "example", "exercise", "calculation_step", "formula", "figure", "table", "important_note")}
        unlinked_obj_ids = sorted(list(all_obj_ids - linked_obj_ids))

        return ConceptIndex(
            book_id=index.book_id,
            concepts=filtered_concepts,
            references=filtered_references,
            unlinked_object_ids=unlinked_obj_ids
        )

    def _score_concept(self, concept: Concept, refs: list[ConceptReference], obj_map: dict[str, EducationalObject]) -> tuple[float, ConceptStatus, str]:
        """Calculates confidence score and classifies the candidate concept."""
        score = 0.0
        reasons = []

        # 1. Linguistic Signals
        name = concept.name
        
        # Immediate rejection for known junk patterns
        if self.FRONT_MATTER_RE.search(name) or self.STRUCTURAL_RE.search(name) or self.METADATA_RE.search(name):
            return 0.0, ConceptStatus.REJECTED, "Matches structural/front-matter pattern"

        words = [w for w in re.split(r'\s+', name) if w]
        word_count = len(words)
        
        if word_count == 0:
            return 0.0, ConceptStatus.REJECTED, "Empty name"
            
        if word_count > 6:
            score -= 0.5
            reasons.append("Too long (>6 words)")
            
        # Punctuation density
        punct_count = len(re.findall(r'[^\w\s]', name))
        if punct_count > 3 or (punct_count > 1 and word_count <= 2):
            score -= 0.5
            reasons.append("High punctuation density")
            
        # Stop-word ratio
        stop_count = sum(1 for w in words if w.lower() in self.STOP_WORDS)
        if word_count > 0 and stop_count / word_count >= 0.5:
            score -= 0.4
            reasons.append("High stop-word ratio")

        # Start with lower case and not a formula (e.g. not x, y)
        if name[0].islower() and word_count > 2:
            score -= 0.2
            reasons.append("Starts with lowercase")

        # 2. Structural Signals
        # Look at the source object type that generated this concept
        source_type = concept.metadata.get("source_type")
        
        if source_type == "heading":
            score += 0.6
            reasons.append("Sourced from heading")
        elif source_type in ("definition", "theorem", "property", "concept"):
            score += 0.5
            reasons.append(f"Sourced from definitional block ({source_type})")
        elif source_type == "paragraph":
            score -= 0.1
            reasons.append("Sourced from plain paragraph")

        # 3. Educational Signals
        linked_count = (
            len(concept.definition_ids) * 2 +  # Definitions carry more weight
            len(concept.formula_ids) +
            len(concept.property_ids) +
            len(concept.theorem_ids) +
            len(concept.proof_ids) +
            len(concept.example_ids) +
            len(concept.exercise_ids) +
            len(concept.figure_ids) +
            len(concept.table_ids)
        )
        
        if linked_count > 0:
            score += min(0.5, linked_count * 0.1)
            reasons.append(f"Linked to {linked_count} educational objects")
        else:
            # Severe penalty for "hollow" concepts (0 educational objects)
            score -= 0.5
            reasons.append("Hollow concept (0 educational objects)")
            
        # Occurrence frequency (how many objects are linked)
        if len(refs) > 1:
            score += min(0.3, len(refs) * 0.05)
            reasons.append(f"Appears in {len(refs)} source objects")

        # Normalization and boundaries
        # Ensure score is within [0.0, 1.0] for positive evaluation
        final_score = max(0.0, min(1.0, score))
        
        if final_score >= 0.75:
            status = ConceptStatus.ACCEPTED
        elif final_score >= 0.50:
            status = ConceptStatus.PROBABLE
        else:
            status = ConceptStatus.REJECTED
            
        return final_score, status, ", ".join(reasons)
