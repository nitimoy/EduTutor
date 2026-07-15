"""Adapter for the Docling document understanding parser."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.compiler.config import ParserConfig
from backend.compiler.models import (
    Book,
    Chapter,
    EducationalObject,
    FormulaData,
    ImageAsset,
    ObjectType,
    ParserOutput,
    Section,
    Subject,
    SubSection,
    TableData,
)
from backend.compiler.parser.base import Parser, register_parser
from backend.compiler.parser.classification import (
    ParseState,
    apply_semantic_links,
    classify_block,
    make_id,
)

logger = logging.getLogger(__name__)


@register_parser("docling")
class DoclingParser(Parser):
    """Parser adapter for Docling (https://github.com/DS4SD/docling).

    If docling is not installed, the parser reports itself unavailable and
    returns an empty output with an error message.
    """

    name = "docling"

    @property
    def version(self) -> str:
        try:
            import docling  # noqa: F401
            return getattr(docling, "__version__", "unknown")
        except Exception:
            return "unknown"

    def is_available(self) -> bool:
        try:
            import docling  # noqa: F401
            return True
        except Exception:
            return False

    def parse(
        self,
        pdf_path: Path,
        subject: Subject,
        book_title: str,
        part: str | None = None,
    ) -> ParserOutput:
        logger.info("Docling parsing %s", pdf_path)
        if not self.is_available():
            return ParserOutput(
                parser_name=self.name,
                errors=["docling package is not installed"],
            )

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.document import ConversionResult
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result: ConversionResult = converter.convert(str(pdf_path))
        doc = result.document

        book = Book(
            id=make_id("book", subject, book_title, part or ""),
            title=book_title,
            subject=subject,
            part=part,
            source_pdf=str(pdf_path),
            page_count=len(doc.pages) if doc.pages else 0,
        )

        objects: list[EducationalObject] = []
        formulas: list[FormulaData] = []
        tables: list[TableData] = []
        figures: list[ImageAsset] = []

        chapters: list[Chapter] = []
        current_chapter = Chapter(id=make_id("chapter", book.id, "unknown"), title="Unknown Chapter")
        current_section = Section(id=make_id("section", current_chapter.id, "unknown"), parent=current_chapter.id)
        current_subsection = SubSection(id=make_id("subsection", current_section.id, "unknown"), parent=current_section.id)
        chapters.append(current_chapter)
        current_chapter.sections.append(current_section)
        current_section.subsections.append(current_subsection)

        state = ParseState()
        reading_order = 0
        for item, level in doc.iterate_items():
            label = item.label if hasattr(item, "label") else "text"
            text = item.text if hasattr(item, "text") else str(item)
            if not text:
                continue

            obj_type: ObjectType = "paragraph"
            if label in ("section_header", "page_header"):
                obj_type = "heading"
                if level == 1:
                    current_chapter = Chapter(id=make_id("chapter", book.id, text), title=text)
                    chapters.append(current_chapter)
                    current_section = Section(id=make_id("section", current_chapter.id, "root"), parent=current_chapter.id)
                    current_chapter.sections.append(current_section)
                    current_subsection = SubSection(
                        id=make_id("subsection", current_section.id, "root"), parent=current_section.id
                    )
                    current_section.subsections.append(current_subsection)
                elif level == 2:
                    current_section = Section(
                        id=make_id("section", current_chapter.id, text), title=text, parent=current_chapter.id
                    )
                    current_chapter.sections.append(current_section)
                    current_subsection = SubSection(
                        id=make_id("subsection", current_section.id, "root"), parent=current_section.id
                    )
                    current_section.subsections.append(current_subsection)
                elif level >= 3:
                    current_subsection = SubSection(
                        id=make_id("subsection", current_section.id, text), title=text, parent=current_section.id
                    )
                    current_section.subsections.append(current_subsection)
                state.reset_context()
            elif label == "formula":
                obj_type = "formula"
            elif label == "table":
                obj_type = "table"
            elif label in ("picture", "figure"):
                obj_type = "figure"
            elif label == "caption":
                obj_type = "caption"
            elif label == "footnote":
                obj_type = "footnote"
            else:
                # Use shared classification for non-specialized text
                obj_type = classify_block(text, "paragraph", state)

            obj_id = make_id("obj", book.id, reading_order)
            obj = EducationalObject(
                id=obj_id,
                type=obj_type,
                subject=subject,
                book=book_title,
                chapter=current_chapter.title,
                section=current_section.title,
                subsection=current_subsection.title,
                reading_order=reading_order,
                title=text[:80] if obj_type == "heading" else "",
                text=text,
                latex=[text] if obj_type == "formula" else [],
                parent_id=current_subsection.id,
                confidence=0.88 if obj_type != "paragraph" else 0.72,
            )
            current_subsection.objects.append(obj)
            apply_semantic_links(obj, state)
            objects.append(obj)
            reading_order += 1

            if obj_type == "formula":
                formulas.append(
                    FormulaData(
                        id=make_id("formula", obj_id),
                        page=0,
                        latex=text,
                        text=text,
                        confidence=0.85,
                        linked_paragraph_id=obj_id,
                    )
                )

        book.objects = objects
        book.chapters = chapters
        self._stamp_provenance(objects)

        return ParserOutput(
            parser_name=self.name,
            book=book,
            objects=objects,
            formulas=formulas,
            tables=tables,
            figures=figures,
            raw={"docling_labels": list({getattr(item, "label", "text") for item, _ in doc.iterate_items()})},
        )
