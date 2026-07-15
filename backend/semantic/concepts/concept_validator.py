"""Validation for the Canonical Concept Layer."""

from __future__ import annotations

import logging

from backend.compiler.models import EducationalIR
from backend.semantic.concepts.concept_models import (
    ConceptIndex,
    ConceptValidationIssue,
    ConceptValidationReport,
)

logger = logging.getLogger(__name__)


class ConceptValidator:
    """Validates concept discovery results against the Educational IR."""

    def validate(self, index: ConceptIndex, ir: EducationalIR) -> ConceptValidationReport:
        """Validate the concept index and return a report."""
        report = ConceptValidationReport(book_id=index.book_id)
        report.total_concepts = len(index.concepts)

        obj_map = {obj.id: obj for obj in ir.book.objects}

        # Track which definitions, formulas, and examples are linked.
        linked_definitions: set[str] = set()
        linked_formulas: set[str] = set()
        linked_examples: set[str] = set()

        for concept in index.concepts:
            issues: list[ConceptValidationIssue] = []

            # Check orphan concepts (no linked objects at all).
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
            if linked_count == 0:
                report.orphan_concepts += 1
                issues.append(
                    ConceptValidationIssue(
                        concept_id=concept.id,
                        field="linked_objects",
                        message=f"Concept '{concept.name}' has no linked educational objects",
                        severity="warning",
                    )
                )

            # Check empty name.
            if not concept.name.strip():
                issues.append(
                    ConceptValidationIssue(
                        concept_id=concept.id,
                        field="name",
                        message="Concept has empty name",
                        severity="error",
                    )
                )

            linked_definitions.update(concept.definition_ids)
            linked_formulas.update(concept.formula_ids)
            linked_examples.update(concept.example_ids)

            if issues:
                report.issues.extend(issues)
            else:
                report.valid_concepts += 1

        # Check for unlinked key objects.
        for obj in ir.book.objects:
            if obj.type == "definition" and obj.id not in linked_definitions:
                report.unlinked_definitions += 1
                report.issues.append(
                    ConceptValidationIssue(
                        concept_id="",
                        field="definition",
                        message=f"Definition '{obj.id}' is not linked to any concept",
                        severity="review",
                    )
                )
            if obj.type == "formula" and obj.id not in linked_formulas:
                report.unlinked_formulas += 1
            if obj.type == "worked_example" and obj.id not in linked_examples:
                report.unlinked_examples += 1

        logger.info(
            "Concept validation: %d valid, %d orphan, %d unlinked defs",
            report.valid_concepts,
            report.orphan_concepts,
            report.unlinked_definitions,
        )
        return report
