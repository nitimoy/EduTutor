"""Deterministic concept discovery and object linking.

Walks the Educational IR to discover canonical concepts from structural
signals (headings, section titles, definition/theorem titles) and links
every relevant educational object to its parent concept.

No LLM.  No embeddings.  Pure heuristic extraction.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from backend.compiler.models import (
    EducationalIR,
    EducationalObject,
    ObjectType,
)
from backend.semantic.concepts.concept_models import (
    Concept,
    ConceptIndex,
    ConceptReference,
)
from backend.semantic.concepts.concept_resolver import (
    ConceptResolver,
    normalize_concept_name,
)

logger = logging.getLogger(__name__)

_COMPOSITE_HEADING_SPLIT_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
_RELATION_NAME_RE = re.compile(r"\bis called\s+([A-Za-z][A-Za-z\- ]{2,80}?)\s*,?\s+if\b", re.IGNORECASE)
_FUNCTION_NAME_RE = re.compile(r"\bis (?:defined|said) to be\s+([A-Za-z][A-Za-z\-() ]{2,80}?)\s*,?\s+if\b", re.IGNORECASE)
_FUNCTION_NAME_SUFFIX_RE = re.compile(r"\s*\(or\s+[^)]*\)", re.IGNORECASE)
_COMPOSITE_HEADING_KEYWORDS = ("relation", "relations", "function", "functions")
_NAMED_LAW_RE = re.compile(r"\bknown as\s+([A-Z][A-Za-z'’\- ]+?law)\b", re.IGNORECASE)
_NUMBERED_DEFINITION_RE = re.compile(r"^(definition|theorem|property|concept|key concept)\s+\d+\b", re.IGNORECASE)

# Patterns that indicate a paragraph contains a definition
_DEFINITION_PATTERNS = re.compile(
    r'\b(is (?:defined|said (?:to be )?|known|called|referred|termed|considered) as\b'
    r'|is (?:a|an|the)\s+(?:type|kind|form|class|category|variant|version|example|instance)\s+of\b'
    r'|refers to\b|means that\b|can be (?:defined|described|expressed|written|stated|represented)\b'
    r'|is (?:given|expressed|written|stated|represented) by\b'
    r'|defined as\b|called a\b|known as a\b|termed as\b'
    r'|is (?:essentially|basically|fundamentally)\b'
    r'|consists of\b|involves\b|comprises\b'
    r'|is said to be\b'
    r'|if it has\b'
    r'|are those which\b'
    r'|are substances which\b'
    r'|is the branch of\b'
    r'|is a branch of\b'
    r'|is the study of\b'
    r'|is concerned with\b'
    r'|deals with\b'
    r'|involves the\b'
    r'|is the process of\b'
    r'|is the science of\b'
    r'|is the field of\b)',
    re.I,
)

# Object types that create concept candidates when they appear as headings
# or titled blocks.
_CONCEPT_SOURCE_TYPES: set[ObjectType] = {
    "heading",
    "definition",
    "concept",
    "theorem",
    "property",
}

# Object types that get linked to their enclosing concept.
_LINKABLE_TYPES: set[ObjectType] = {
    "definition",
    "concept",
    "formula",
    "property",
    "theorem",
    "proof",
    "worked_example",
    "example_question",
    "example_solution",
    "calculation_step",
    "final_answer",
    "exercise",
    "exercise_question",
    "exercise_answer",
    "in_text_question",
    "important_note",
    "warning",
    "summary",
    "table",
    "figure",
    "diagram",
    "caption",
    "paragraph",
}

# Minimum length for a heading/title to be considered a concept candidate.
_MIN_CONCEPT_NAME_LEN = 3

# Map from object type to the concept field that collects its IDs.
_TYPE_TO_FIELD: dict[ObjectType, str] = {
    "definition": "definition_ids",
    "formula": "formula_ids",
    "property": "property_ids",
    "theorem": "theorem_ids",
    "proof": "proof_ids",
    "worked_example": "example_ids",
    "example_question": "example_ids",
    "example_solution": "example_ids",
    "calculation_step": "example_ids",
    "final_answer": "example_ids",
    "exercise": "exercise_ids",
    "exercise_question": "exercise_ids",
    "exercise_answer": "exercise_ids",
    "in_text_question": "exercise_ids",
    "figure": "figure_ids",
    "diagram": "figure_ids",
    "table": "table_ids",
}


def _make_concept_id(subject: str, chapter: str, name: str) -> str:
    """Deterministic concept ID from subject + chapter + normalized name."""
    payload = f"concept|{subject}|{chapter}|{name}"
    return "concept." + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _structural_parent_norm(
    chapter: str,
    concept_norm: str,
    section: str,
    subsection: str,
    all_canonical: dict[str, dict[str, tuple[str, str, list[str]]]],
) -> str | None:
    """Use existing section metadata as a fallback parent signal."""
    chapter_canonical = all_canonical.get(chapter, {})
    candidates = (section, subsection)
    if concept_norm.endswith("law"):
        candidates = (subsection, section)

    for candidate in candidates:
        parent_norm = normalize_concept_name(candidate)
        if parent_norm and parent_norm != concept_norm and parent_norm in chapter_canonical:
            return parent_norm
    return None


def _infer_candidate_chapter(obj: EducationalObject, chapter_by_position: list[tuple[int, int, str]]) -> str:
    """Map selected Unknown Chapter headings to the nearest later known chapter."""
    if obj.chapter != "Unknown Chapter":
        return obj.chapter

    if obj.type != "heading":
        return obj.chapter

    for page, reading_order, chapter in chapter_by_position:
        if chapter == "Unknown Chapter":
            continue
        if (page, reading_order) >= (obj.page, obj.reading_order) and (page - obj.page) <= 1:
            return chapter
    return obj.chapter


def _break_parent_cycles(concepts: dict[str, Concept]) -> None:
    """Guarantee the concept parent graph is a forest (no cycles).

    Parent inference is heuristic (substring / structural fallback) and can
    produce cycles such as A -> B -> C -> A.  Downstream reasoning treats the
    parent graph as a DAG, so any cycle is a correctness bug.  We walk each
    concept's ancestry and, the first time we revisit a node, sever the edge
    that closed the loop by clearing the offending ``parent_id``.  Detaching
    to the root (rather than reassigning) keeps the operation deterministic
    and free of arbitrary tie-breaks.
    """
    for start_id in sorted(concepts):
        seen: set[str] = set()
        current: str | None = start_id
        while current is not None:
            if current in seen:
                # ``current`` is the node whose parent pointer closes a cycle.
                concepts[current].parent_id = None
                break
            seen.add(current)
            parent_id = concepts[current].parent_id
            if parent_id is None or parent_id not in concepts:
                break
            current = parent_id


def _prune_dangling_parents(concepts: dict[str, Concept]) -> None:
    """Clear parent pointers that reference a concept not in the index.

    Concepts can be dropped later (e.g. by ``ConceptFilter``) while their
    former children still point at them.  A ``parent_id`` that resolves to
    nothing is a broken reference, so we null it out.
    """
    valid_ids = set(concepts)
    for concept in concepts.values():
        if concept.parent_id is not None and concept.parent_id not in valid_ids:
            concept.parent_id = None


def _rebuild_sub_concepts(concepts: dict[str, Concept]) -> None:
    """Recompute ``sub_concept_ids`` from ``parent_id`` deterministically.

    This is the single source of truth for the child lists: it stays in sync
    with whatever ``parent_id`` values survived cycle-breaking and dangling
    cleanup, and it emits children in sorted order for reproducibility.
    """
    children: dict[str, list[str]] = {cid: [] for cid in concepts}
    for cid in sorted(concepts):
        parent_id = concepts[cid].parent_id
        if parent_id is not None and parent_id in children:
            children[parent_id].append(cid)
    for cid, concept in concepts.items():
        concept.sub_concept_ids = children[cid]


class ConceptBuilder:
    """Discovers concepts and links objects from a compiled Educational IR."""

    def __init__(self) -> None:
        self._resolver = ConceptResolver()

    def build(self, ir: EducationalIR) -> ConceptIndex:
        """Run concept discovery and linking on the IR.

        Steps:
          1. Walk every object to discover concept candidates.
          2. Resolve and deduplicate via ConceptResolver.
          3. Build scope-based object-to-concept links.
          4. Assemble Concept models with grouped object IDs.
          5. Return a ConceptIndex.
        """
        book = ir.book
        objects = list(book.objects)
        chapter_by_position = [
            (obj.page, obj.reading_order, obj.chapter)
            for obj in sorted(objects, key=lambda item: (item.page, item.reading_order))
        ]

        # Each candidate is (normalized_name, display_name, chapter, section,
        # subsection, page, reading_order, source_type).
        raw_candidates: list[tuple[str, str, str, str, str, int, int, str]] = []

        for obj in objects:
            candidate_chapter = _infer_candidate_chapter(obj, chapter_by_position)
            names = self._extract_concept_names(obj)
            for name in names:
                canon_norm, canon_disp, aliases = self._resolver.resolve(name, candidate_chapter)
                
                # If a concept is extracted from a paragraph, it must be a named law or explicitly parsed concept.
                # Treat it as a definition so it isn't penalized by the filter.
                assigned_type = "definition" if obj.type == "paragraph" else obj.type

                if canon_norm and len(canon_norm) >= _MIN_CONCEPT_NAME_LEN:
                    raw_candidates.append(
                        (canon_norm, canon_disp, candidate_chapter, obj.section, obj.subsection, obj.page, obj.reading_order, assigned_type)
                    )

        # Authority ranking for source types
        type_auth = {
            "heading": 3,
            "definition": 2,
            "theorem": 2,
            "property": 2,
            "concept": 2,
        }

        # Deduplicate candidates: keep earliest occurrence per (chapter, norm),
        # but ALWAYS prefer higher-authority sources (e.g. headings over paragraphs)
        seen: dict[tuple[str, str], tuple[str, str, str, str, int, int, str]] = {}
        for norm, disp, chapter, section, subsection, page, ro, obj_type in raw_candidates:
            key = (chapter, norm)
            new_auth = type_auth.get(obj_type, 1)
            
            if key not in seen:
                seen[key] = (disp, section, subsection, page, ro, obj_type)
            else:
                current_auth = type_auth.get(seen[key][5], 1)
                # If we find a higher authority source, update the anchor location and type
                if new_auth > current_auth:
                    seen[key] = (disp, section, subsection, page, ro, obj_type)

        # --- Phase 2: Build Concept objects. -------------------------------
        concepts: dict[str, Concept] = {}
        # Ordered list of (reading_order, page, chapter, concept_id) for
        # reading-order-based scoping: each concept "owns" objects from its
        # position until the next concept starts within the same chapter.
        concept_anchors: list[tuple[int, int, str, str]] = []

        all_canonical = self._resolver.all_canonical()
        hierarchy = self._resolver.find_parents()

        for (chapter, norm), (disp, section, subsection, page, ro, obj_type) in seen.items():
            concept_id = _make_concept_id(book.subject, chapter, norm)
            aliases_list: list[str] = []
            if chapter in all_canonical and norm in all_canonical[chapter]:
                _, _, aliases_list = all_canonical[chapter][norm]

            parent_norm = hierarchy.get(chapter, {}).get(norm)
            if not parent_norm:
                parent_norm = _structural_parent_norm(chapter, norm, section, subsection, all_canonical)
            parent_id = _make_concept_id(book.subject, chapter, parent_norm) if parent_norm else None

            concept = Concept(
                id=concept_id,
                name=disp,
                aliases=aliases_list,
                parent_id=parent_id,
                subject=book.subject,
                book=book.title,
                chapter=chapter,
                metadata={"page_start": page, "reading_order_start": ro, "source_type": obj_type},
            )
            concepts[concept_id] = concept
            concept_anchors.append((ro, page, chapter, concept_id))

        # Enforce parent-graph integrity before deriving child lists:
        #   1. drop parents that don't resolve to a surviving concept,
        #   2. break any cycles so the graph is a forest,
        #   3. rebuild sub_concept_ids deterministically from parent_id.
        _prune_dangling_parents(concepts)
        _break_parent_cycles(concepts)
        _rebuild_sub_concepts(concepts)

        # Sort anchors by reading order so we can do nearest-preceding lookup.
        concept_anchors.sort(key=lambda a: (a[1], a[0]))

        # Build per-chapter sorted anchor lists for efficient lookup.
        chapter_anchors: dict[str, list[tuple[int, int, str]]] = {}
        for ro, page, chapter, cid in concept_anchors:
            chapter_anchors.setdefault(chapter, []).append((ro, page, cid))

        logger.info("Discovered %d concepts for %s", len(concepts), book.title)

        # --- Phase 3: Link objects to concepts. ----------------------------
        # Each object is assigned to the nearest preceding concept in reading
        # order within the same chapter.
        references: list[ConceptReference] = []
        linked_object_ids: set[str] = set()

        for obj in sorted(objects, key=lambda o: (o.page, o.reading_order)):
            if obj.type not in _LINKABLE_TYPES:
                continue

            concept_id = self._resolve_object_concept(obj, chapter_anchors, concepts)
            if not concept_id or concept_id not in concepts:
                continue

            # Detect definition-like paragraphs and reclassify them
            effective_type = obj.type
            if obj.type == "paragraph" and obj.text and _DEFINITION_PATTERNS.search(obj.text):
                effective_type = "definition"

            reason = self._link_reason(obj, concepts[concept_id])
            ref = ConceptReference(
                concept_id=concept_id,
                object_id=obj.id,
                object_type=effective_type,
                link_reason=reason,
            )
            references.append(ref)
            linked_object_ids.add(obj.id)

            # Populate the typed ID list on the concept.
            field = _TYPE_TO_FIELD.get(effective_type)
            if field:
                getattr(concepts[concept_id], field).append(obj.id)

        # Objects that couldn't be assigned.
        all_ids = {obj.id for obj in objects}
        unlinked = sorted(all_ids - linked_object_ids)

        # --- Phase 4: Populate descriptions from linked definitions. -------
        obj_map = {obj.id: obj for obj in objects}
        for concept in concepts.values():
            if concept.definition_ids:
                first_def = obj_map.get(concept.definition_ids[0])
                if first_def:
                    concept.description = first_def.text[:500]

        # --- Phase 5: Confidence scoring. ----------------------------------
        for concept in concepts.values():
            linked_count = (
                len(concept.definition_ids)
                + len(concept.formula_ids)
                + len(concept.property_ids)
                + len(concept.theorem_ids)
                + len(concept.proof_ids)
                + len(concept.example_ids)
                + len(concept.exercise_ids)
                + len(concept.figure_ids)
                + len(concept.table_ids)
            )
            # More linked objects → higher confidence (capped at 1.0).
            concept.confidence = min(1.0, 0.3 + linked_count * 0.07)

        logger.info(
            "Linked %d objects to concepts, %d unlinked",
            len(linked_object_ids),
            len(unlinked),
        )

        # --- Phase 6: Infer related concepts. --------------------------------
        # Concepts in the same section or with shared definitions are related.
        self._infer_related_concepts(concepts, references)

        # --- Phase 7: Fix misattributed definitions. -------------------------
        # Some definitions are linked to the wrong concept due to PDF structure.
        # Re-link definitions that are clearly about a different concept.
        self._fix_misattributed_definitions(concepts, obj_map)

        # --- Phase 8: Add content-based aliases. ----------------------------
        # Add aliases to concepts based on keywords found in their content.
        # This improves retrieval by matching queries that mention topics
        # covered by the concept but not in its name.
        self._add_content_aliases(concepts, obj_map)

        return ConceptIndex(
            book_id=book.id,
            concepts=list(concepts.values()),
            references=references,
            unlinked_object_ids=unlinked,
        )

    def _infer_related_concepts(self, concepts: dict[str, Concept], references: list[ConceptReference]) -> None:
        """Infer related concepts from document structure and shared content.

        Two concepts are related if:
        1. They share the same section (e.g., both in "Magnetic Properties")
        2. They share definitions or examples
        3. They are siblings under the same parent
        """
        # Build concept-to-section mapping
        concept_sections: dict[str, set[str]] = {}
        for ref in references:
            concept_id = ref.concept_id
            if concept_id in concepts:
                # Get section from the concept's metadata
                section = concepts[concept_id].metadata.get("section", "")
                if section:
                    concept_sections.setdefault(concept_id, set()).add(section)

        # Group concepts by section
        section_concepts: dict[str, list[str]] = {}
        for cid, sections in concept_sections.items():
            for section in sections:
                section_concepts.setdefault(section, []).append(cid)

        # Add related concepts for concepts in the same section
        for section, cids in section_concepts.items():
            if len(cids) > 1:
                for cid in cids:
                    for other_cid in cids:
                        if cid != other_cid and other_cid not in concepts[cid].related_concepts:
                            concepts[cid].related_concepts.append(other_cid)

        # Add siblings as related concepts
        for cid, concept in concepts.items():
            if concept.parent_id:
                parent = concepts.get(concept.parent_id)
                if parent:
                    for sibling_id in parent.sub_concept_ids:
                        if sibling_id != cid and sibling_id not in concept.related_concepts:
                            concept.related_concepts.append(sibling_id)

    def _extract_concept_names(self, obj: EducationalObject) -> list[str]:
        """Extract zero or more concept name candidates from an object."""
        if obj.type == "heading" and obj.title:
            return self._expand_heading_candidates(obj.title)
        if obj.type == "paragraph":
            named_law = self._extract_named_law(obj, obj.title or obj.text)
            return [named_law] if named_law else []
        if obj.type == "calculation_step":
            named_definition = self._extract_named_definition(obj.title or obj.text)
            return [named_definition] if named_definition else []
        if obj.type in ("definition", "theorem", "property", "concept"):
            # Try to extract the named entity after the type keyword.
            # e.g. "Definition: Electric Field" → "Electric Field"
            text = obj.title or obj.text
            named_definition = self._extract_named_definition(text)
            if named_definition:
                return [named_definition]

            for prefix in ("Definition", "Define", "Theorem", "Property", "Concept", "Key Concept"):
                if text.lower().startswith(prefix.lower()):
                    remainder = text[len(prefix):].lstrip(" :.-–—")
                    if _NUMBERED_DEFINITION_RE.match(text):
                        continue
                    if remainder and len(remainder) >= _MIN_CONCEPT_NAME_LEN:
                        # Take first line only.
                        return self._expand_heading_candidates(remainder.split("\n")[0].strip()[:80])

            named_law = self._extract_named_law(obj, text)
            if named_law:
                return [named_law]
            
            # For standalone concepts that don't use a prefix, just return the text
            if obj.type == "concept" and text:
                return self._expand_heading_candidates(text.split("\n")[0].strip()[:80])
                
            return []
        return []

    def _expand_heading_candidates(self, text: str) -> list[str]:
        """Split composite headings into individually evaluable concept candidates."""
        primary = text.strip()
        if not primary:
            return []

        normalized_primary = normalize_concept_name(primary)
        if "," in primary or primary.endswith("."):
            return [primary]

        candidates = [primary]
        if not any(keyword in normalized_primary.split() for keyword in _COMPOSITE_HEADING_KEYWORDS):
            return candidates

        parts = [part.strip() for part in _COMPOSITE_HEADING_SPLIT_RE.split(primary) if part.strip()]
        if len(parts) > 1 and all(len(part) >= _MIN_CONCEPT_NAME_LEN for part in parts):
            if any(normalize_concept_name(part) in _COMPOSITE_HEADING_KEYWORDS for part in parts):
                return [primary]

            candidates.extend(parts)
        return candidates

    def _extract_named_definition(self, text: str) -> str:
        """Recover concept names embedded in definition prose."""
        first_line = text.split("\n", 1)[0].strip()
        relation_match = _RELATION_NAME_RE.search(first_line)
        if relation_match:
            return relation_match.group(1).strip()

        function_match = _FUNCTION_NAME_RE.search(first_line)
        if function_match:
            return _FUNCTION_NAME_SUFFIX_RE.sub("", function_match.group(1)).strip()

        return ""

    def _extract_named_law(self, obj: EducationalObject, text: str) -> str:
        """Recover a named-law concept from prose (e.g. '... known as Henry's law').

        Subject-agnostic: the ``known as <Name> law`` pattern appears across
        Physics, Chemistry, and Mathematics, so it is applied uniformly rather
        than gated on a specific subject or subsection.
        """
        first_line = text.split("\n", 1)[0].strip()
        match = _NAMED_LAW_RE.search(first_line)
        if not match:
            return ""
        return match.group(1).strip().replace("’", "'")

    def _resolve_object_concept(
        self,
        obj: EducationalObject,
        chapter_anchors: dict[str, list[tuple[int, int, str]]],
        concepts: dict[str, Concept] | None = None,
    ) -> str | None:
        """Find the nearest preceding concept for this object by reading order.

        Each concept anchor is (reading_order, page, concept_id).  We find the
        last anchor whose (page, reading_order) <= the object's position.
        Priority: exact section name match > nearest preceding.
        """
        anchors = chapter_anchors.get(obj.chapter)
        if not anchors:
            return None

        # First, try to find a concept whose name exactly matches the section
        if concepts and obj.section:
            obj_section_lower = obj.section.lower().strip()
            for ro, page, cid in reversed(anchors):
                if (page, ro) <= (obj.page, obj.reading_order):
                    concept = concepts.get(cid)
                    if concept:
                        concept_lower = concept.name.lower().strip()
                        # Exact match or section starts with concept name
                        if concept_lower == obj_section_lower or obj_section_lower.startswith(concept_lower):
                            return cid
                        # Check if concept is a child of the section's parent
                        # (e.g., "Diamagnetism" is a child of "Magnetic Properties of Materials")
                        if concept.parent_id:
                            parent = concepts.get(concept.parent_id)
                            if parent:
                                parent_lower = parent.name.lower().strip()
                                if obj_section_lower.startswith(parent_lower) or parent_lower.startswith(obj_section_lower):
                                    return cid

        # Fallback: nearest preceding concept by page/reading_order
        obj_key = (obj.page, obj.reading_order)
        best: str | None = None
        for ro, page, cid in anchors:
            if (page, ro) <= obj_key:
                best = cid
            else:
                break
        return best

    def _link_reason(self, obj: EducationalObject, concept: Concept) -> str:
        """Determine why this object was linked to this concept."""
        norm_name = normalize_concept_name(concept.name)
        obj_text = (obj.title or obj.text[:120]).lower()
        if norm_name and norm_name in obj_text:
            return "title_match"
        if obj.type in _CONCEPT_SOURCE_TYPES:
            return "heading_match"
        return "section_scope"

    def _fix_misattributed_definitions(
        self, concepts: dict[str, Concept], obj_map: dict[str, EducationalObject]
    ) -> None:
        """Fix definitions that are linked to the wrong concept.

        Some definitions are linked to the wrong concept due to PDF structure
        (reading-order-based linking). This method detects definitions that are
        clearly about a different concept and re-links them.

        Patterns include:
        - "X is called/defined/said to be Y"
        - "X consists of Y"
        - "X of Y" (when X is a concept name)
        - "X linked with Y"
        - "X in an Y"
        - Content that starts with a different concept's name
        """
        # Build concept name -> concept map (case-insensitive)
        name_to_concept: dict[str, Concept] = {}
        for concept in concepts.values():
            name_to_concept[concept.name.lower()] = concept

        fixes = 0
        for concept in list(concepts.values()):
            # Check each definition in this concept
            defs_to_move: list[tuple[int, str]] = []  # (index, target_concept_name)

            for i, def_id in enumerate(concept.definition_ids):
                obj = obj_map.get(def_id)
                if not obj or not obj.text:
                    continue

                text = obj.text.lower().strip()

                # Multiple patterns to catch different phrasings
                patterns = [
                    # Standard definition patterns
                    r'^([^,]+?)\s+is\s+(?:called|defined|said\s+to\s+be)\s+',
                    r'^the\s+([^,]+?)\s+is\s+(?:called|defined|said\s+to\s+be)\s+',
                    # "X consists of Y"
                    r'^([^,]+?)\s+consists\s+of\s+',
                    # "X of Y" where X is a concept
                    r'^([^,]+?)\s+of\s+(?:a|an|the)\s+',
                    # "X linked with Y"
                    r'^([^,]+?)\s+linked\s+with\s+',
                    # "X in an Y"
                    r'^([^,]+?)\s+in\s+(?:an|a|the)\s+',
                    # "Having defined X" or "Having X"
                    r'^having\s+(?:defined\s+)?([^,]+?)\s',
                    # "We are investigating X"
                    r'^we\s+are\s+investigating\s+',
                    # "The conductivity of X"
                    r'^the\s+([^,]+?)\s+of\s+',
                ]

                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        defined_term = match.group(1).strip() if match.lastindex else ""

                        # Check if this term matches a DIFFERENT concept name
                        for other_name, other_concept in name_to_concept.items():
                            if other_concept.id == concept.id:
                                continue
                            if other_concept.chapter != concept.chapter:
                                continue

                            # The defined term should match the other concept
                            # Check both directions: term in concept name OR concept name in term
                            if (other_name in defined_term or defined_term in other_name or
                                other_name in text[:100]) and len(other_name) > 3:
                                defs_to_move.append((i, other_name))
                                break

            # Move the misattributed definitions
            for idx, target_name in reversed(defs_to_move):
                target_concept = name_to_concept.get(target_name)
                if target_concept and idx < len(concept.definition_ids):
                    def_id = concept.definition_ids.pop(idx)
                    target_concept.definition_ids.append(def_id)
                    fixes += 1
                    logger.info(
                        "Fixed misattributed definition: %s -> %s",
                        concept.name, target_concept.name,
                    )

            # Also check example objects for misattributed content
            examples_to_move: list[tuple[int, str]] = []
            for i, example_id in enumerate(concept.example_ids):
                obj = obj_map.get(example_id)
                if not obj or not obj.text:
                    continue

                text = obj.text.lower().strip()
                if len(text) < 50:  # Skip very short examples
                    continue

                # Pattern: content that is clearly a definition of another concept
                # Check if the content mentions a DIFFERENT concept name
                for other_name, other_concept in name_to_concept.items():
                    if other_concept.id == concept.id:
                        continue
                    if other_concept.chapter != concept.chapter:
                        continue

                    # Check if the content mentions the other concept name
                    if other_name in text and len(other_name) > 3:
                        # Additional check: look for definition patterns
                        definition_patterns = [
                            r'(?:are|is)\s+called\s+',
                            r'(?:are|is)\s+defined\s+as\s+',
                            r'(?:are|is)\s+said\s+to\s+be\s+',
                            r'is\s+called\s+',
                            r'refers\s+to\s+',
                        ]
                        for pattern in definition_patterns:
                            if re.search(pattern, text):
                                examples_to_move.append((i, other_name))
                                break
                        break

            # Move the misattributed examples
            for idx, target_name in reversed(examples_to_move):
                target_concept = name_to_concept.get(target_name)
                if target_concept and idx < len(concept.example_ids):
                    example_id = concept.example_ids.pop(idx)
                    target_concept.example_ids.append(example_id)
                    fixes += 1
                    logger.info(
                        "Fixed misattributed example: %s -> %s",
                        concept.name, target_concept.name,
                    )

        if fixes:
            logger.info("Fixed %d misattributed definitions/examples", fixes)

    def _add_content_aliases(
        self, concepts: dict[str, Concept], obj_map: dict[str, EducationalObject]
    ) -> None:
        """Add aliases to concepts based on keywords in their content.

        This improves retrieval by matching queries that mention topics
        covered by the concept but not in its name. Only adds aliases
        when the keyword appears frequently in the content (not just once).
        """
        # Mapping of content keywords to alias suggestions
        # Only add alias if keyword appears 3+ times in content
        content_keyword_aliases = {
            # Physics - Optics
            'young': ['young double slit', "young's double slit experiment"],
            'double slit': ['double slit', 'young double slit'],
            'fringe width': ['fringe width'],
            'interference fringes': ['interference fringes'],
            'diffraction': ['diffraction'],
            'polarization': ['polarization', 'polarisation'],

            # Physics - Electromagnetism
            "gauss's law": ["gauss's law"],
            "coulomb's law": ["coulomb's law"],
            "faraday's law": ["faraday's law"],
            "lenz's law": ["lenz's law"],
            "ampere's law": ["ampere's law"],
            'lorentz force': ['lorentz force'],
            "ohm's law": ["ohm's law"],
            "kirchhoff's laws": ["kirchhoff's laws"],
            'hall effect': ['hall effect'],

            # Physics - Mechanics
            "newton's laws": ["newton's laws"],
            'conservation of energy': ['conservation of energy'],
            'conservation of momentum': ['conservation of momentum'],
            'centripetal force': ['centripetal force'],
            'projectile motion': ['projectile motion'],

            # Chemistry
            'organic chemistry': ['organic chemistry'],
            'chemical reaction': ['chemical reaction'],
            'chemical equilibrium': ['chemical equilibrium'],
            'electrochemistry': ['electrochemistry'],
            'thermodynamics': ['thermodynamics'],
            'chemical kinetics': ['chemical kinetics'],

            # Mathematics
            'matrix multiplication': ['matrix multiplication'],
            'matrix addition': ['matrix addition'],
            'matrix inverse': ['matrix inverse'],
            'determinant': ['determinant'],
            'integration': ['integration', 'integral'],
            'differentiation': ['differentiation', 'derivative'],
            'partial fractions': ['partial fractions'],
            'probability': ['probability'],
            'vectors': ['vectors'],
        }

        aliases_added = 0
        for concept in concepts.values():
            # Collect all content text for this concept
            content_texts = []
            for def_id in concept.definition_ids:
                obj = obj_map.get(def_id)
                if obj and obj.text:
                    content_texts.append(obj.text.lower())
            for ex_id in concept.example_ids:
                obj = obj_map.get(ex_id)
                if obj and obj.text:
                    content_texts.append(obj.text.lower())

            if not content_texts:
                continue

            all_content = ' '.join(content_texts)
            concept_name_lower = concept.name.lower()

            # Find matching keywords and add aliases
            # Only add if keyword appears 2+ times (indicates it's a main topic)
            new_aliases = []
            for keyword, aliases in content_keyword_aliases.items():
                count = all_content.count(keyword)
                if count >= 2 and keyword not in concept_name_lower:
                    for alias in aliases:
                        if alias not in concept.aliases and alias != concept.name.lower():
                            new_aliases.append(alias)

            # Add new aliases (limit to 5 to avoid bloating)
            for alias in new_aliases[:5]:
                concept.aliases.append(alias)
                aliases_added += 1

        if aliases_added:
            logger.info("Added %d content-based aliases", aliases_added)
