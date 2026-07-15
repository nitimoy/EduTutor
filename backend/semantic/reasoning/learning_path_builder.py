from backend.compiler.models import EducationalObject
from backend.semantic.concepts.concept_models import ConceptIndex

_PRIORITY = {
    "concept": 1,
    "definition": 2,
    "theorem": 3,
    "property": 4,
    "formula": 5,
    "proof": 6,
    "worked_example": 7,
    "example": 7,
    "exercise": 8,
    "exercise_question": 8,
}

class LearningPathBuilder:
    """Builds an ordered sequence of objects to teach a concept."""

    def build(self, concept_id: str, objects: list[EducationalObject], concept_index: ConceptIndex) -> list[str]:
        # Find all object IDs linked to this concept
        linked_obj_ids = set()
        for ref in concept_index.references:
            if ref.concept_id == concept_id:
                linked_obj_ids.add(ref.object_id)

        # Filter the IR objects
        linked_objs = [o for o in objects if o.id in linked_obj_ids]

        # Sort by priority, then by page, then by reading_order
        # Fallback priority is 10 for unknown types
        sorted_objs = sorted(
            linked_objs, 
            key=lambda o: (_PRIORITY.get(o.type, 10), o.page, o.reading_order)
        )

        return [o.id for o in sorted_objs]
