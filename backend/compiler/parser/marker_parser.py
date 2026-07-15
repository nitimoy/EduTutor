"""Adapter for the Marker PDF-to-Markdown parser."""

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


@register_parser("marker")
class MarkerParser(Parser):
    """Parser adapter for Marker (https://github.com/VikParuchuri/marker).

    If marker is not installed, the parser reports itself unavailable and
    returns an empty output with an error message.
    """

    name = "marker"

    @property
    def version(self) -> str:
        try:
            import marker  # noqa: F401
            return getattr(marker, "__version__", "unknown")
        except Exception:
            return "unknown"

    def is_available(self) -> bool:
        try:
            import marker  # noqa: F401
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
        logger.info("Marker parsing %s", pdf_path)
        if not self.is_available():
            return ParserOutput(
                parser_name=self.name,
                errors=["marker package is not installed"],
            )

        # Marker produces markdown per PDF. We import lazily to avoid hard dependency.
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        model_dict = create_model_dict()
        converter = PdfConverter(artifact_dict=model_dict)
        rendered = converter(str(pdf_path))
        markdown = rendered.markdown

        book = Book(
            id=make_id("book", subject, book_title, part or ""),
            title=book_title,
            subject=subject,
            part=part,
            source_pdf=str(pdf_path),
            page_count=0,
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
        for line in markdown.splitlines():
            line = line.strip()
            if not line:
                continue

            obj_type: ObjectType = "paragraph"
            if line.startswith("# "):
                obj_type = "heading"
                current_chapter = Chapter(id=make_id("chapter", book.id, line), title=line.lstrip("# ").strip())
                chapters.append(current_chapter)
                current_section = Section(id=make_id("section", current_chapter.id, "root"), parent=current_chapter.id)
                current_chapter.sections.append(current_section)
                current_subsection = SubSection(id=make_id("subsection", current_section.id, "root"), parent=current_section.id)
                current_section.subsections.append(current_subsection)
                state.reset_context()
            elif line.startswith("## "):
                obj_type = "heading"
                current_section = Section(
                    id=make_id("section", current_chapter.id, line),
                    title=line.lstrip("# ").strip(),
                    parent=current_chapter.id,
                )
                current_chapter.sections.append(current_section)
                current_subsection = SubSection(id=make_id("subsection", current_section.id, "root"), parent=current_section.id)
                current_section.subsections.append(current_subsection)
                state.reset_context()
            elif line.startswith("### "):
                obj_type = "heading"
                current_subsection = SubSection(
                    id=make_id("subsection", current_section.id, line),
                    title=line.lstrip("# ").strip(),
                    parent=current_section.id,
                )
                current_section.subsections.append(current_subsection)
                state.reset_context()
            elif line.startswith("$") and line.endswith("$"):
                obj_type = "formula"
            else:
                # Use shared classification for non-specialized text
                obj_type = classify_block(line, "paragraph", state)

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
                title=line[:80] if obj_type == "heading" else "",
                text=line,
                latex=[line] if obj_type == "formula" else [],
                parent_id=current_subsection.id,
                confidence=0.9 if obj_type != "paragraph" else 0.75,
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
                        latex=line,
                        text=line,
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
            raw={"markdown_length": len(markdown)},
        )
