"""Pydantic models for the Knowledge Retrieval Index."""

from __future__ import annotations

from pydantic import BaseModel, Field

class KnowledgeDocument(BaseModel):
    """A flattened, search-optimized representation of a concept."""

    concept_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    subject: str
    chapter: str

    # Educational Content (Flattened from IR objects)
    definition_texts: list[str] = Field(default_factory=list)
    formula_latex: list[str] = Field(default_factory=list)
    example_texts: list[str] = Field(default_factory=list)

    # Context (Resolved names for easy display/search)
    prerequisites: list[str] = Field(default_factory=list)
    next_topics: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)

    # Metadata
    difficulty: str = ""
    teaching_sequence_index: int = 0
    page_start: int | None = None
    book: str | None = None


class KnowledgeIndex(BaseModel):
    """The full retrieval index for a given book."""
    
    book_id: str
    documents: list[KnowledgeDocument] = Field(default_factory=list)
