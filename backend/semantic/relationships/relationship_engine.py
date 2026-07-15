import logging
import re
from typing import Any

from backend.compiler.models import EducationalIR, EducationalObject
from backend.semantic.concepts.concept_models import ConceptIndex, Concept
from backend.semantic.relationships.relationship_models import Relationship, RelationshipIndex

logger = logging.getLogger(__name__)


class RelationshipEngine:
    """Infers semantic relationships from structural and textual signals."""

    def __init__(self) -> None:
        self.relationships: list[Relationship] = []

    def build(self, ir: EducationalIR, concept_index: ConceptIndex) -> RelationshipIndex:
        """Run relationship inference."""
        self.relationships = []
        
        # Build quick lookups
        concept_map = {c.id: c for c in concept_index.concepts}
        object_map = {o.id: o for o in ir.book.objects}
        
        # 1. Concept Hierarchy Inference
        self._infer_concept_hierarchy(concept_map)

        # 2. Object Type Inference
        self._infer_object_types(concept_index)

        # 3. Object Context Inference
        self._infer_object_context(ir.book.objects)

        # 4. Textual Reference Inference
        self._infer_textual_references(ir.book.objects, concept_map)

        # Deduplicate relationships, keeping the highest-confidence variant of
        # each (source, target, type) edge.
        unique_rels: dict[tuple[str, str, str], Relationship] = {}
        for r in self.relationships:
            key = (r.source_id, r.target_id, r.relationship_type)
            if key not in unique_rels or unique_rels[key].confidence < r.confidence:
                unique_rels[key] = r

        # Emit edges in a deterministic order so the exported artifact is
        # byte-for-byte reproducible regardless of dict/set iteration order.
        ordered = sorted(
            unique_rels.values(),
            key=lambda r: (r.source_id, r.target_id, r.relationship_type),
        )

        return RelationshipIndex(
            book_id=ir.book.id,
            relationships=ordered,
        )

    def _add(self, source: str, target: str, rel_type: str, conf: float, evidence: str, method: str) -> None:
        if source == target:
            return
        self.relationships.append(
            Relationship(
                source_id=source,
                target_id=target,
                relationship_type=rel_type,
                confidence=conf,
                evidence=evidence,
                inference_method=method
            )
        )

    def _infer_concept_hierarchy(self, concept_map: dict[str, Concept]) -> None:
        for cid, concept in concept_map.items():
            if concept.parent_id and concept.parent_id in concept_map:
                parent = concept_map[concept.parent_id]
                relation_type = self._hierarchy_relation_type(concept, parent)
                if relation_type is None:
                    continue
                self._add(
                    source=cid,
                    target=parent.id,
                    rel_type=relation_type,
                    conf=0.9,
                    evidence=f"'{concept.name}' is nested under '{parent.name}'",
                    method="concept_hierarchy"
                )

    def _infer_object_types(self, concept_index: ConceptIndex) -> None:
        for ref in concept_index.references:
            if ref.object_type in ("example", "worked_example"):
                self._add(
                    source=ref.concept_id,
                    target=ref.object_id,
                    rel_type="illustrated_by",
                    conf=0.9,
                    evidence=f"Example {ref.object_id} belongs to concept {ref.concept_id}",
                    method="object_type_mapping"
                )
            elif ref.object_type in ("exercise", "exercise_question"):
                self._add(
                    source=ref.concept_id,
                    target=ref.object_id,
                    rel_type="tested_by",
                    conf=0.9,
                    evidence=f"Exercise {ref.object_id} belongs to concept {ref.concept_id}",
                    method="object_type_mapping"
                )

    def _infer_object_context(self, objects: list[EducationalObject]) -> None:
        sorted_objs = sorted(objects, key=lambda o: (o.page, o.reading_order))
        
        last_obj: EducationalObject | None = None
        for obj in sorted_objs:
            if obj.type == "proof" and last_obj and last_obj.type in ("theorem", "property", "concept"):
                self._add(
                    source=obj.id,
                    target=last_obj.id,
                    rel_type="explains",
                    conf=0.8,
                    evidence="Proof immediately follows theorem/property",
                    method="object_context"
                )
            # Skip empty objects when tracking context
            if (obj.title or obj.text) and obj.type != "figure":
                last_obj = obj

    def _infer_textual_references(self, objects: list[EducationalObject], concept_map: dict[str, Concept]) -> None:
        # Build regex for concept lookup
        # Map lowercased alias to concept ID.
        alias_to_cid: dict[str, str] = {}
        for cid, concept in concept_map.items():
            # Include name and all aliases
            names = [concept.name] + concept.aliases
            for name in names:
                if len(name) > 4:  # Avoid matching short trivial words
                    alias_to_cid[name.lower()] = cid

        if not alias_to_cid:
            return

        # Sort aliases by (length desc, alias asc) so matching prefers the
        # longest phrase and ties break deterministically (independent of dict
        # iteration order / hash seed).
        sorted_aliases = sorted(alias_to_cid.keys(), key=lambda a: (-len(a), a))
        # Escape for regex and join with OR
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted_aliases)) + r")\b", re.IGNORECASE)

        for obj in objects:
            text = f"{obj.title} {obj.text}".strip()
            if not text:
                continue

            # Deterministic dedup: one edge per matched concept, and the
            # evidence phrase is the lexicographically smallest match so the
            # exported record is byte-stable across runs.
            evidence_by_cid: dict[str, str] = {}
            for match in pattern.findall(text):
                cid = alias_to_cid.get(match.lower())
                if not cid:
                    continue
                existing = evidence_by_cid.get(cid)
                if existing is None or match.lower() < existing:
                    evidence_by_cid[cid] = match.lower()

            for cid in sorted(evidence_by_cid):
                self._add(
                    source=obj.id,
                    target=cid,
                    rel_type="depends_on",
                    conf=0.7,
                    evidence=f"Textual mention of '{evidence_by_cid[cid]}'",
                    method="textual_reference",
                )

    def _hierarchy_relation_type(self, concept: Concept, parent: Concept) -> str:
        """Choose the semantic edge type for a structural child-parent link.

        Purely subject-agnostic: the decision is driven by generic lexical
        signals in the concept names (taxonomy words, named laws, "effect of"
        framing) that hold uniformly across Mathematics, Physics, and
        Chemistry.  No subject, chapter, or concept name is special-cased.
        """
        child_name = concept.name.lower()
        parent_name = parent.name.lower()

        # A parent that is itself a taxonomy bucket ("Types of ...", "Kinds of
        # ...") groups siblings rather than being a prerequisite for them.
        if any(parent_name.startswith(prefix) for prefix in ("types of ", "kinds of ", "kind of ", "classification of ")):
            return "related_to"

        # A child that enumerates a taxonomy or an "effect of" relationship is a
        # sibling/association, not a dependency.
        if any(term in child_name for term in ("types of", "kind of", "classification")):
            return "related_to"
        if child_name.startswith("effect of "):
            return "related_to"

        # Named laws explain the phenomenon they are nested under.
        if child_name.endswith(" law") or child_name.endswith("'s law"):
            return "explains"

        return "depends_on"
