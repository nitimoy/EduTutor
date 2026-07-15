"""Pydantic models for the Canonical Concept Layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from backend.compiler.models import ObjectType, Subject


class Concept(BaseModel):
    """A canonical educational concept that groups related objects."""

    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    subject: Subject
    book: str
    chapter: str
    description: str = ""
    definition_ids: list[str] = Field(default_factory=list)
    formula_ids: list[str] = Field(default_factory=list)
    property_ids: list[str] = Field(default_factory=list)
    theorem_ids: list[str] = Field(default_factory=list)
    proof_ids: list[str] = Field(default_factory=list)
    example_ids: list[str] = Field(default_factory=list)
    exercise_ids: list[str] = Field(default_factory=list)
    figure_ids: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    sub_concept_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ConceptReference(BaseModel):
    """A link between a concept and an educational object."""

    concept_id: str
    object_id: str
    object_type: ObjectType
    link_reason: str  # "heading_match", "section_scope", "title_match"


class ConceptValidationIssue(BaseModel):
    """A single issue found during concept validation."""

    concept_id: str
    field: str
    message: str
    severity: str  # "error", "warning", "review"


class ConceptValidationReport(BaseModel):
    """Result of validating the concept layer."""

    book_id: str
    total_concepts: int = 0
    valid_concepts: int = 0
    orphan_concepts: int = 0
    unlinked_definitions: int = 0
    unlinked_formulas: int = 0
    unlinked_examples: int = 0
    issues: list[ConceptValidationIssue] = Field(default_factory=list)


class ConceptIndex(BaseModel):
    """Top-level index mapping concepts to educational objects for one book."""

    book_id: str
    concepts: list[Concept] = Field(default_factory=list)
    references: list[ConceptReference] = Field(default_factory=list)
    unlinked_object_ids: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
