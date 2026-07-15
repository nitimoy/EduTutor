"""Validation stage for the Educational IR."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.compiler.models import EducationalIR, EducationalObject

logger = logging.getLogger(__name__)


class ObjectIssue(BaseModel):
    """A single validation issue on an educational object."""

    object_id: str
    object_type: str
    field: str
    message: str
    severity: str  # "error", "warning", "review"


class ValidationReport(BaseModel):
    """Result of validating an Educational IR."""

    book_id: str
    total_objects: int = 0
    valid_objects: int = 0
    flagged_objects: int = 0
    issues: list[ObjectIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Validator:
    """Validate Educational IR and flag low-confidence objects for review."""

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.confidence_threshold = confidence_threshold

    def validate(self, ir: EducationalIR) -> ValidationReport:
        """Validate the IR and return a report."""
        report = ValidationReport(book_id=ir.book.id)
        objects = self._all_objects(ir)
        report.total_objects = len(objects)

        for obj in objects:
            issues = self._validate_object(obj)
            if issues:
                report.flagged_objects += 1
                report.issues.extend(issues)
            else:
                report.valid_objects += 1

        report.metadata = {
            "formula_count": len(ir.formulas),
            "table_count": len(ir.tables),
            "figure_count": len(ir.figures),
            "chapter_count": len(ir.book.chapters),
        }
        logger.info(
            "Validation complete: %s valid, %s flagged",
            report.valid_objects,
            report.flagged_objects,
        )
        return report

    def _all_objects(self, ir: EducationalIR) -> list[EducationalObject]:
        """Return every object in the book.

        `book.objects` is the canonical flat list produced by the parser/merge
        stages; `chapter.objects` / `section.objects` / `subsection.objects`
        are a containment view over the *same* object instances (for
        hierarchy-aware traversal), so they are not summed here to avoid
        double-counting.
        """
        return list(ir.book.objects)

    def _validate_object(self, obj: EducationalObject) -> list[ObjectIssue]:
        """Return issues for a single object."""
        issues: list[ObjectIssue] = []

        if obj.confidence < self.confidence_threshold:
            issues.append(
                ObjectIssue(
                    object_id=obj.id,
                    object_type=obj.type,
                    field="confidence",
                    message=f"Confidence {obj.confidence:.2f} below threshold {self.confidence_threshold}",
                    severity="review",
                )
            )

        if not obj.text.strip() and obj.type not in ("figure", "diagram"):
            issues.append(
                ObjectIssue(
                    object_id=obj.id,
                    object_type=obj.type,
                    field="text",
                    message="Object has empty text",
                    severity="warning",
                )
            )

        if obj.type in ("definition", "theorem", "property") and len(obj.text) < 10:
            issues.append(
                ObjectIssue(
                    object_id=obj.id,
                    object_type=obj.type,
                    field="text",
                    message="Key concept object is suspiciously short",
                    severity="review",
                )
            )

        if obj.page < 1:
            issues.append(
                ObjectIssue(
                    object_id=obj.id,
                    object_type=obj.type,
                    field="page",
                    message="Object has no page number",
                    severity="warning",
                )
            )

        return issues
