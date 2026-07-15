"""Data models for the evaluation framework gold standards."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GoldConcept(BaseModel):
    """A concept expected to be extracted by the compiler."""
    name: str
    aliases: list[str] = Field(default_factory=list)
    parent_name: str | None = None
    required_formulas: list[str] = Field(default_factory=list)
    required_figures: list[str] = Field(default_factory=list)
    required_proofs: list[str] = Field(default_factory=list)


class GoldRelationship(BaseModel):
    """An educational relationship expected to be inferred by the compiler."""
    source: str
    target: str
    relationship_type: Literal[
        "depends_on",
        "prerequisite_of",
        "explains",
        "used_by",
        "tested_by",
        "illustrated_by",
        "derived_from",
        "related_to",
    ]


class GoldStandard(BaseModel):
    """The gold standard annotation for a specific chapter in a book."""
    version: str = "1.0.0"
    book_id: str
    chapter: str
    concepts: list[GoldConcept] = Field(default_factory=list)
    relationships: list[GoldRelationship] = Field(default_factory=list)
    learning_path: list[str] = Field(default_factory=list)
