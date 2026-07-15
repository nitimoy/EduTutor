"""Context Organizer — select and order the retrieved knowledge for teaching.

Takes the ranked retrieval results (and an optional :class:`KnowledgeRepository` for
recovering proof/exercise/theorem/property objects) and produces an
:class:`OrganizedContext`: the primary concept, the supporting concepts, and one
:class:`SectionSpec` per compiler-backed :class:`SectionKind`.

It only **selects and orders** existing objects — it never rewrites their text (OCR
noise in the source is a known data-quality issue, out of scope here) and never
synthesizes content. A field with no object → ``EMPTY``; a recover-eligible kind with no
repository → ``UNSUPPORTED_BY_INDEX``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.retrieval.strategies.base import SearchResult
from backend.tutor.models import (
    SOURCE_CONCEPT,
    SOURCE_DEFINITION,
    SOURCE_EXAMPLE,
    SOURCE_FORMULA,
    SOURCE_NEXT,
    SOURCE_OBJECT,
    SOURCE_PREREQUISITE,
    SOURCE_RELATED,
    ItemRef,
    SectionKind,
    SectionSpec,
    SectionStatus,
)
from backend.tutor.repository import KnowledgeRepository

# Recovered object kinds folded into MAIN_EXPLANATION (supporting statements).
_MAIN_RECOVER_KINDS: tuple[str, ...] = ("theorem", "property")


class OrganizedContext(BaseModel):
    """The selected, ordered teaching material before strategy/citation/composition."""

    primary_concept_id: Optional[str] = None
    primary_concept_name: str = ""
    supporting_concept_ids: list[str] = Field(default_factory=list)
    sections: dict[SectionKind, SectionSpec] = Field(default_factory=dict)

    def section(self, kind: SectionKind) -> SectionSpec:
        """Return the section for ``kind`` (an empty one if the organizer built none)."""
        return self.sections.get(kind, SectionSpec(kind=kind, status=SectionStatus.EMPTY))

    def is_supported(self, kind: SectionKind) -> bool:
        return self.section(kind).status == SectionStatus.PRESENT


def _name_refs(names: list[str], source_field: str) -> list[ItemRef]:
    """Build item refs for a list of graph names (concept id resolved later)."""
    return [
        ItemRef(concept_id=None, concept_name=name, source_field=source_field,
                locator=str(i), text=name)
        for i, name in enumerate(names)
    ]


def _status(items: list[ItemRef]) -> SectionStatus:
    return SectionStatus.PRESENT if items else SectionStatus.EMPTY


def organize(
    results: list[SearchResult],
    repository: Optional[KnowledgeRepository] = None,
) -> OrganizedContext:
    """Organize retrieved documents into per-kind sections. Deterministic."""
    if not results:
        return OrganizedContext()

    primary = results[0].document
    supporting = [r.document for r in results[1:]]
    ctx = OrganizedContext(
        primary_concept_id=primary.concept_id,
        primary_concept_name=primary.name,
        supporting_concept_ids=[d.concept_id for d in supporting],
    )
    sections: dict[SectionKind, SectionSpec] = {}

    # --- prerequisites / related / next: resolved graph names -----------------
    prereq_refs = _name_refs(primary.prerequisites, SOURCE_PREREQUISITE)
    sections[SectionKind.PREREQUISITES] = SectionSpec(
        kind=SectionKind.PREREQUISITES, status=_status(prereq_refs), item_refs=prereq_refs)

    related_refs = _name_refs(primary.related_concepts, SOURCE_RELATED)
    sections[SectionKind.RELATED_CONCEPTS] = SectionSpec(
        kind=SectionKind.RELATED_CONCEPTS, status=_status(related_refs), item_refs=related_refs)

    next_refs = _name_refs(primary.next_topics, SOURCE_NEXT)
    sections[SectionKind.NEXT_TOPICS] = SectionSpec(
        kind=SectionKind.NEXT_TOPICS, status=_status(next_refs), item_refs=next_refs)

    # --- main explanation: definitions (+ recovered theorem/property) ---------
    # For broad queries with multiple supporting concepts, include their
    # definitions too so the LLM can produce a multi-concept overview.
    main_refs: list[ItemRef] = [
        ItemRef(concept_id=primary.concept_id, concept_name=primary.name,
                source_field=SOURCE_DEFINITION, locator=str(i), text=text)
        for i, text in enumerate(primary.definition_texts)
    ]
    # Include supporting concepts' definitions for multi-concept coverage
    for doc in supporting:
        for i, text in enumerate(doc.definition_texts):
            main_refs.append(ItemRef(
                concept_id=doc.concept_id, concept_name=doc.name,
                source_field=SOURCE_DEFINITION, locator=str(i), text=text))
    if repository is not None:
        for obj in repository.recover_objects(primary.concept_id, _MAIN_RECOVER_KINDS):
            main_refs.append(ItemRef(
                concept_id=primary.concept_id, concept_name=primary.name,
                source_field=SOURCE_OBJECT, locator=obj.object_id, object_type=obj.type,
                text=obj.text, latex=obj.latex))
    sections[SectionKind.MAIN_EXPLANATION] = SectionSpec(
        kind=SectionKind.MAIN_EXPLANATION, status=_status(main_refs), item_refs=main_refs)

    # --- formulas -------------------------------------------------------------
    formula_refs = [
        ItemRef(concept_id=primary.concept_id, concept_name=primary.name,
                source_field=SOURCE_FORMULA, locator=str(i), text=latex, latex=[latex])
        for i, latex in enumerate(primary.formula_latex)
    ]
    sections[SectionKind.FORMULA] = SectionSpec(
        kind=SectionKind.FORMULA, status=_status(formula_refs), item_refs=formula_refs)

    # --- worked examples (index example_texts) — limited to avoid dumping all) ---
    # Keep at most 2 examples to prevent the LLM from reading out the entire textbook.
    MAX_EXAMPLES = 2
    example_refs = [
        ItemRef(concept_id=primary.concept_id, concept_name=primary.name,
                source_field=SOURCE_EXAMPLE, locator=str(i), text=text)
        for i, text in enumerate(primary.example_texts[:MAX_EXAMPLES])
    ]
    sections[SectionKind.WORKED_EXAMPLE] = SectionSpec(
        kind=SectionKind.WORKED_EXAMPLE, status=_status(example_refs), item_refs=example_refs)

    # --- proof / exercise: recovered IR objects (repo-gated) ------------------
    sections[SectionKind.PROOF] = _recovered_section(
        SectionKind.PROOF, "proof", primary.concept_id, primary.name, repository)
    sections[SectionKind.EXERCISE] = _recovered_section(
        SectionKind.EXERCISE, "exercise", primary.concept_id, primary.name, repository)

    # --- comparison: the retrieved concepts' own definitions ------------------
    comparison_refs: list[ItemRef] = []
    seen_concepts: set[str] = set()  # Track seen concept IDs and names to avoid duplicates
    
    for doc in [primary] + supporting:
        # Skip duplicate concepts (same ID or alias of each other)
        doc_key = doc.concept_id or doc.name.lower()
        doc_name_lower = doc.name.lower()
        
        # Check if this concept is an alias of an already-seen concept
        is_duplicate = False
        if doc.concept_id in seen_concepts:
            is_duplicate = True
        for alias in doc.aliases:
            alias_lower = alias.lower()
            if alias_lower in seen_concepts:
                is_duplicate = True
                break
        
        if is_duplicate:
            continue
            
        seen_concepts.add(doc_key)
        seen_concepts.add(doc_name_lower)
        for alias in doc.aliases:
            seen_concepts.add(alias.lower())
        
        head = doc.definition_texts[0] if doc.definition_texts else doc.name
        comparison_refs.append(ItemRef(
            concept_id=doc.concept_id, concept_name=doc.name,
            source_field=SOURCE_DEFINITION if doc.definition_texts else SOURCE_CONCEPT,
            locator="0" if doc.definition_texts else doc.concept_id, text=head))
    
    # A comparison needs at least two distinct concepts to contrast.
    comparison_status = (
        SectionStatus.PRESENT if len(comparison_refs) >= 2 else SectionStatus.EMPTY)
    sections[SectionKind.COMPARISON] = SectionSpec(
        kind=SectionKind.COMPARISON, status=comparison_status, item_refs=comparison_refs)

    # --- summary: structured recap (name + difficulty), no new prose ----------
    recap = primary.name + (f" ({primary.difficulty})" if primary.difficulty else "")
    summary_refs = [ItemRef(
        concept_id=primary.concept_id, concept_name=primary.name,
        source_field=SOURCE_CONCEPT, locator=primary.concept_id, text=recap)]
    sections[SectionKind.SUMMARY] = SectionSpec(
        kind=SectionKind.SUMMARY, status=SectionStatus.PRESENT, item_refs=summary_refs)

    ctx.sections = sections
    return ctx


def _recovered_section(
    kind: SectionKind,
    recover_kind: str,
    concept_id: str,
    concept_name: str,
    repository: Optional[KnowledgeRepository],
) -> SectionSpec:
    """Build a proof/exercise section from recovered IR objects.

    No repository → ``UNSUPPORTED_BY_INDEX`` (the content exists in the compiler but is
    not reachable without a recovery backend). Repository but no such objects → ``EMPTY``.
    """
    if repository is None:
        return SectionSpec(
            kind=kind, status=SectionStatus.UNSUPPORTED_BY_INDEX,
            note=f"{recover_kind} objects are not carried in the Knowledge Index; "
                 f"provide a KnowledgeRepository to recover them")
    refs = [
        ItemRef(concept_id=concept_id, concept_name=concept_name,
                source_field=SOURCE_OBJECT, locator=obj.object_id, object_type=obj.type,
                text=obj.text, latex=obj.latex)
        for obj in repository.recover_objects(concept_id, (recover_kind,))
    ]
    return SectionSpec(kind=kind, status=_status(refs), item_refs=refs)
