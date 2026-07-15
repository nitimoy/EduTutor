"""Citation Builder — resolve every planned item back to a compiler-produced object.

Turns each :class:`ItemRef` in a :class:`TeachingPlan` into a :class:`Citation`. Content
items already know their owning concept id; graph-name items (prerequisites / related /
next topics) carry only a name, which is resolved to a concept id via a name→id map built
from the retrieved documents. A name with no match yields a citation with
``concept_id=None`` — an honest "unresolved", never a fabricated id.

Guarantee upheld here: every non-null ``concept_id`` and every recovered ``object_id``
comes straight from the plan's own refs (which the organizer took from real
documents/objects); this builder never invents an identifier.
"""

from __future__ import annotations

from backend.retrieval.strategies.base import SearchResult
from backend.semantic.concepts.concept_resolver import normalize_concept_name
from backend.tutor.models import Citation, ItemRef, TeachingPlan


class CitationBuilder:
    """Resolve plan item refs to citations using a name→concept-id map."""

    def __init__(self, name_to_id: dict[str, str], id_to_meta: dict[str, tuple[str, str]]) -> None:
        self._name_to_id = name_to_id
        self._id_to_meta = id_to_meta

    @classmethod
    def from_results(cls, results: list[SearchResult]) -> "CitationBuilder":
        """Build the name→id map from retrieved documents' names and aliases."""
        name_to_id: dict[str, str] = {}
        id_to_meta: dict[str, tuple[str, str]] = {}
        for r in results:
            doc = r.document
            id_to_meta[doc.concept_id] = (doc.subject, doc.chapter)
            for label in [doc.name, *doc.aliases]:
                key = normalize_concept_name(label)
                if key:
                    name_to_id.setdefault(key, doc.concept_id)
        return cls(name_to_id, id_to_meta)

    def _citation_for(self, ref: ItemRef) -> Citation:
        concept_id = ref.concept_id
        if concept_id is None:
            concept_id = self._name_to_id.get(normalize_concept_name(ref.concept_name))
            
        subject, chapter = "", ""
        if concept_id and concept_id in self._id_to_meta:
            subject, chapter = self._id_to_meta[concept_id]
            
        return Citation(
            concept_id=concept_id,
            concept_name=ref.concept_name,
            source_field=ref.source_field,
            locator=ref.locator,
            object_type=ref.object_type,
            subject=subject,
            chapter=chapter,
        )

    def resolve(self, teaching_plan: TeachingPlan) -> list[list[Citation]]:
        """Return citations per section, aligned to ``teaching_plan.sections``."""
        return [
            [self._citation_for(ref) for ref in section.item_refs]
            for section in teaching_plan.sections
        ]
