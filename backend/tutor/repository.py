"""Knowledge recovery behind a storage-agnostic interface.

The retrieval ``KnowledgeDocument`` carries only definitions, formulas, and examples.
Proofs, exercises, theorems, and properties exist at the Concept/IR level but are not
flattened into the retrieval index. The Tutor Brain recovers them *after* retrieval —
but only through the :class:`KnowledgeRepository` abstraction, so future storage
backends (SQLite, Postgres, an API) can be swapped in without any brain change.

:class:`CompiledArtifactRepository` is the initial concrete backend: it loads the frozen
compiled JSON artifacts (``concept_index.json`` + ``educational_ir.json``) read-only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from backend.compiler.models.educational_ir import EducationalIR, EducationalObject
from backend.semantic.concepts.concept_models import Concept, ConceptIndex

# Recoverable object kinds → the ``Concept`` id-list attribute that references them.
# Only compiler-produced object kinds; nothing synthesized.
_KIND_TO_ID_FIELD: dict[str, str] = {
    "definition": "definition_ids",
    "formula": "formula_ids",
    "example": "example_ids",
    "proof": "proof_ids",
    "exercise": "exercise_ids",
    "theorem": "theorem_ids",
    "property": "property_ids",
}


class RecoveredObject(BaseModel):
    """A compiler-produced educational object recovered by concept id."""

    object_id: str
    type: str
    title: str = ""
    text: str = ""
    latex: list[str] = Field(default_factory=list)


class KnowledgeRepository(ABC):
    """Storage-agnostic access to compiler-produced objects not in the retrieval index.

    The Tutor Brain depends only on this interface. Implementations must be
    deterministic and read-only with respect to the underlying store.
    """

    @abstractmethod
    def get_concept(self, concept_id: str) -> Concept | None:
        """Return the canonical concept for ``concept_id``, or ``None``."""

    @abstractmethod
    def recover_objects(self, concept_id: str, kinds: tuple[str, ...]) -> list[RecoveredObject]:
        """Recover objects of the given ``kinds`` (e.g. ``("proof", "exercise")``).

        Returns them in the concept's declared id order; unknown concept or missing
        objects yield an empty list / are skipped. Never raises for a missing id.
        """


class CompiledArtifactRepository(KnowledgeRepository):
    """Read-only :class:`KnowledgeRepository` over the compiled JSON artifacts."""

    def __init__(self, concept_index: ConceptIndex, ir: EducationalIR) -> None:
        self._concept_by_id: dict[str, Concept] = {c.id: c for c in concept_index.concepts}
        self._object_by_id: dict[str, EducationalObject] = {
            obj.id: obj for obj in ir.book.objects
        }

    @classmethod
    def from_compiled_dir(cls, path: str | Path) -> "CompiledArtifactRepository":
        """Load ``concept_index.json`` + ``educational_ir.json`` from a compiled dir or root."""
        base = Path(path)
        
        all_concepts = []
        all_objects = []
        
        if (base / "concept_index.json").exists():
            dirs = [base]
        else:
            dirs = [p.parent for p in base.rglob("concept_index.json")]
            
        for d in dirs:
            c_idx = ConceptIndex.model_validate_json(
                (d / "concept_index.json").read_text(encoding="utf-8")
            )
            ir_idx = EducationalIR.model_validate_json(
                (d / "educational_ir.json").read_text(encoding="utf-8")
            )
            all_concepts.extend(c_idx.concepts)
            all_objects.extend(ir_idx.book.objects)
            
        instance = cls.__new__(cls)
        instance._concept_by_id = {c.id: c for c in all_concepts}
        instance._object_by_id = {obj.id: obj for obj in all_objects}
        return instance

    def get_concept(self, concept_id: str) -> Concept | None:
        return self._concept_by_id.get(concept_id)

    def recover_objects(self, concept_id: str, kinds: tuple[str, ...]) -> list[RecoveredObject]:
        concept = self._concept_by_id.get(concept_id)
        if concept is None:
            return []
        recovered: list[RecoveredObject] = []
        for kind in kinds:
            id_field = _KIND_TO_ID_FIELD.get(kind)
            if id_field is None:
                continue
            for object_id in getattr(concept, id_field, []):
                obj = self._object_by_id.get(object_id)
                if obj is None:
                    continue
                recovered.append(
                    RecoveredObject(
                        object_id=obj.id,
                        type=obj.type,
                        title=obj.title,
                        text=obj.text,
                        latex=list(obj.latex),
                    )
                )
        return recovered
