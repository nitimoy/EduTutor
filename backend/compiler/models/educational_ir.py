"""Pydantic models for the Educational Intermediate Representation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ObjectType = Literal[
    "heading",
    "paragraph",
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
    "sidebar",
    "footnote",
    "reference",
]

Subject = Literal["mathematics", "physics", "chemistry"]


class BoundingBox(BaseModel):
    """Normalized or absolute page coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float
    page: int


class ImageAsset(BaseModel):
    """Reference to an extracted image asset."""

    id: str
    page: int
    path: str | None = None
    bounding_box: BoundingBox | None = None
    caption: str = ""
    linked_object_ids: list[str] = Field(default_factory=list)


class TableCell(BaseModel):
    """Single cell in a table."""

    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1


class TableData(BaseModel):
    """Structured table representation."""

    id: str
    page: int
    rows: int
    cols: int
    cells: list[TableCell]
    caption: str = ""
    bounding_box: BoundingBox | None = None
    linked_object_ids: list[str] = Field(default_factory=list)


class FormulaData(BaseModel):
    """Formula extracted from the document."""

    id: str
    page: int
    latex: str = ""
    text: str = ""
    bounding_box: BoundingBox | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    linked_paragraph_id: str | None = None
    linked_example_id: str | None = None


class Reference(BaseModel):
    """Cross-reference to another object, figure, or external source."""

    target_id: str
    target_type: ObjectType | Literal["figure", "table", "formula", "external"]
    label: str = ""


class EducationalObject(BaseModel):
    """Base unit of the Educational IR."""

    id: str
    type: ObjectType
    subject: Subject
    book: str
    chapter: str = ""
    section: str = ""
    subsection: str = ""
    page: int = 0
    reading_order: int = 0
    title: str = ""
    text: str = ""
    latex: list[str] = Field(default_factory=list)
    images: list[ImageAsset] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)

    # Structural / sequential relationships.
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    previous_id: str | None = None
    next_id: str | None = None

    # Semantic relationships. Populated in later enrichment phases;
    # kept on the schema now so downstream consumers never need a migration.
    prerequisites: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    explains: list[str] = Field(default_factory=list)
    used_by: list[str] = Field(default_factory=list)
    related_to: list[str] = Field(default_factory=list)
    previous_topics: list[str] = Field(default_factory=list)
    next_topics: list[str] = Field(default_factory=list)

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    coordinates: BoundingBox | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Provenance / processing metadata.
    parser_name: str = ""
    parser_version: str = ""
    checksum: str = ""
    ir_version: str = ""


class SubSection(BaseModel):
    """A subsection inside a section."""

    id: str
    title: str = ""
    number: str = ""
    page_start: int = 0
    page_end: int = 0
    objects: list[EducationalObject] = Field(default_factory=list)
    children: list[SubSection] = Field(default_factory=list)
    parent: str | None = None


class Section(BaseModel):
    """A section inside a chapter."""

    id: str
    title: str = ""
    number: str = ""
    page_start: int = 0
    page_end: int = 0
    subsections: list[SubSection] = Field(default_factory=list)
    objects: list[EducationalObject] = Field(default_factory=list)
    parent: str | None = None


class Chapter(BaseModel):
    """A chapter inside a book."""

    id: str
    title: str = ""
    number: str = ""
    page_start: int = 0
    page_end: int = 0
    sections: list[Section] = Field(default_factory=list)
    objects: list[EducationalObject] = Field(default_factory=list)
    parent: str | None = None


class Book(BaseModel):
    """A single textbook."""

    id: str
    title: str
    subject: Subject
    part: str | None = None
    source_pdf: str
    page_count: int = 0
    chapters: list[Chapter] = Field(default_factory=list)
    objects: list[EducationalObject] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EducationalIR(BaseModel):
    """Top-level compiled representation for one book."""

    book: Book
    formulas: list[FormulaData] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    figures: list[ImageAsset] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "1.0.0"


class ParserOutput(BaseModel):
    """Structured output produced by a single parser."""

    parser_name: str
    book: Book | None = None
    objects: list[EducationalObject] = Field(default_factory=list)
    formulas: list[FormulaData] = Field(default_factory=list)
    tables: list[TableData] = Field(default_factory=list)
    figures: list[ImageAsset] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class ParseResult(BaseModel):
    """Combined result from all parsers for one PDF."""

    source_pdf: str
    subject: Subject
    book_title: str
    outputs: dict[str, ParserOutput] = Field(default_factory=dict)
    merged_ir: EducationalIR | None = None
