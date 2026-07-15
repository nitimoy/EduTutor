"""Knowledge Index Builder for deterministic retrieval."""

import logging
from typing import Any

from backend.compiler.models import EducationalIR
from backend.semantic.concepts.concept_models import ConceptIndex
from backend.semantic.relationships.relationship_models import RelationshipIndex
from backend.semantic.reasoning.reasoning_models import ReasoningIndex
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex

logger = logging.getLogger(__name__)


class KnowledgeIndexBuilder:
    """Flattens compiler output into self-contained search documents."""

    def build(
        self,
        ir: EducationalIR,
        concept_index: ConceptIndex,
        rel_index: RelationshipIndex,
        reasoning_index: ReasoningIndex,
    ) -> KnowledgeIndex:
        """Construct the flattened knowledge index."""
        logger.info(f"Building knowledge index for {ir.book.id}...")

        # 1. Build lookup maps for IR objects to resolve textual content
        object_map = {obj.id: obj for obj in ir.book.objects}
        
        # 2. Build lookup maps for Concept Names to resolve readable relationships
        concept_map = {c.id: c for c in concept_index.concepts}

        # 3. Process relationships to resolve graph contexts
        prerequisites_map: dict[str, list[str]] = {}
        related_map: dict[str, list[str]] = {}
        
        for rel in rel_index.relationships:
            if rel.relationship_type == "depends_on":
                prerequisites_map.setdefault(rel.source_id, []).append(rel.target_id)
            elif rel.relationship_type == "related_to":
                related_map.setdefault(rel.source_id, []).append(rel.target_id)
                related_map.setdefault(rel.target_id, []).append(rel.source_id)
        
        documents = []
        for concept in concept_index.concepts:
            # Gather definition texts
            def_texts = []
            for did in concept.definition_ids:
                if did in object_map:
                    def_texts.append(object_map[did].text)

            # Gather theorem texts (include in definition_texts for retrieval)
            for tid in concept.theorem_ids:
                if tid in object_map:
                    def_texts.append(object_map[tid].text)

            # Gather proof texts (include in definition_texts for retrieval)
            for pid in concept.proof_ids:
                if pid in object_map:
                    def_texts.append(object_map[pid].text)

            # Gather formulas
            form_latex = []
            for fid in concept.formula_ids:
                if fid in object_map:
                    form_latex.extend(object_map[fid].latex)

            # Gather examples
            ex_texts = []
            for eid in concept.example_ids:
                if eid in object_map:
                    ex_texts.append(object_map[eid].text)
            
            # Resolve readable names for prerequisites
            prereq_names = []
            for prereq_id in prerequisites_map.get(concept.id, []):
                if prereq_id in concept_map:
                    prereq_names.append(concept_map[prereq_id].name)
                    
            # Resolve readable names for related concepts
            rel_names = []
            for rel_id in related_map.get(concept.id, []):
                if rel_id in concept_map:
                    rel_names.append(concept_map[rel_id].name)

            # Deduplicate related names deterministically (dict preserves the
            # first-seen order, so the output is stable across runs).
            rel_names = list(dict.fromkeys(rel_names))
            prereq_names = list(dict.fromkeys(prereq_names))

            # Grab reasoning metadata
            difficulty = ""
            teaching_seq = 0
            reasoning = reasoning_index.concept_reasoning.get(concept.id)
            if reasoning:
                difficulty = reasoning.difficulty
                # Using length of teaching sequence as a proxy for depth/order if no global index exists
                # Or if there is a global sequence index we can use that.
                # For now, default to 0 and we can refine later.
            
            # Extract page_start from metadata
            page_start = concept.metadata.get("page_start") if concept.metadata else None

            doc = KnowledgeDocument(
                concept_id=concept.id,
                name=concept.name,
                aliases=concept.aliases,
                subject=concept.subject,
                chapter=concept.chapter,
                definition_texts=def_texts,
                formula_latex=form_latex,
                example_texts=ex_texts,
                prerequisites=prereq_names,
                next_topics=[], # Can be computed by inverting prerequisites
                related_concepts=rel_names,
                difficulty=difficulty,
                teaching_sequence_index=teaching_seq,
                page_start=page_start,
                book=concept.book,
            )
            documents.append(doc)
            
        # Optional: compute next_topics by inverting prerequisites
        # Build inverted map: prerequisite_name -> list of dependent concept names
        next_map: dict[str, list[str]] = {}
        for doc in documents:
            for prereq in doc.prerequisites:
                next_map.setdefault(prereq, []).append(doc.name)
        
        for doc in documents:
            doc.next_topics = list(dict.fromkeys(next_map.get(doc.name, [])))

        logger.info(f"Successfully built Knowledge Index with {len(documents)} documents.")
        return KnowledgeIndex(
            book_id=ir.book.id,
            documents=documents,
        )
