"""Merge multiple parser outputs into a single Educational IR."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.compiler.constants import IR_VERSION, compute_checksum
from backend.compiler.models import (
    Book,
    Chapter,
    EducationalIR,
    EducationalObject,
    FormulaData,
    ImageAsset,
    ObjectType,
    ParserOutput,
    Section,
    SubSection,
    TableData,
)
from backend.compiler.parser.classification import link_reading_order

logger = logging.getLogger(__name__)


def _make_id(*parts: Any) -> str:
    payload = "|".join(str(p) for p in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


class MergeEngine:
    """Combine outputs from multiple parsers into one canonical Educational IR."""

    def __init__(self, priority: list[str] | None = None) -> None:
        """Initialize with parser priority (highest first)."""
        self.priority = priority or ["marker", "docling", "pymupdf"]

    def merge(self, outputs: dict[str, ParserOutput]) -> EducationalIR:
        """Merge parser outputs into a single EducationalIR."""
        if not outputs:
            raise ValueError("No parser outputs to merge")

        available = [name for name in self.priority if name in outputs]
        if not available:
            available = list(outputs.keys())

        primary_name = available[0]
        logger.info("Merging with primary parser: %s", primary_name)

        book = self._merge_book(outputs, available)
        objects = self._merge_objects(outputs, available, book)
        formulas = self._merge_formulas(outputs, available)
        tables = self._merge_tables(outputs, available)
        figures = self._merge_figures(outputs, available)

        if len(available) == 1:
            # Single contributing parser: its hierarchy (Book -> Chapter ->
            # Section -> SubSection -> Objects) was already built correctly
            # during parsing and shares object identity with `objects`, so
            # trust it as-is instead of flattening + rebuilding from scratch.
            book.chapters = outputs[primary_name].book.chapters
        else:
            book.chapters = self._rebuild_chapters(objects)
        book.objects = objects

        link_reading_order(objects)
        for obj in objects:
            obj.ir_version = IR_VERSION
            obj.checksum = compute_checksum(obj.type, obj.page, obj.text, "".join(obj.latex))

        return EducationalIR(
            book=book,
            formulas=formulas,
            tables=tables,
            figures=figures,
        )

    def _merge_book(
        self, outputs: dict[str, ParserOutput], available: list[str]
    ) -> Book:
        """Pick the richest book metadata across parsers."""
        for name in available:
            if outputs[name].book is not None:
                book = outputs[name].book
                # Enrich with metadata from other parsers.
                for other_name in available:
                    if other_name == name:
                        continue
                    other_book = outputs[other_name].book
                    if other_book and other_book.page_count > book.page_count:
                        book.page_count = other_book.page_count
                return book
        raise ValueError("No parser produced book metadata")

    def _merge_objects(
        self,
        outputs: dict[str, ParserOutput],
        available: list[str],
        book: Book,
    ) -> list[EducationalObject]:
        """Merge objects, preferring higher-confidence parser output."""
        merged: dict[str, EducationalObject] = {}

        for name in available:
            parser_output = outputs[name]
            for obj in parser_output.objects:
                key = self._object_key(obj)
                existing = merged.get(key)
                if existing is None:
                    merged[key] = obj
                elif obj.confidence > existing.confidence:
                    merged[key] = obj
                else:
                    # Merge non-conflicting enrichment (order-stable dedup).
                    existing.latex = list(dict.fromkeys(existing.latex + obj.latex))
                    if obj.coordinates and not existing.coordinates:
                        existing.coordinates = obj.coordinates

        return list(merged.values())

    def _merge_formulas(
        self, outputs: dict[str, ParserOutput], available: list[str]
    ) -> list[FormulaData]:
        """Deduplicate formulas by content."""
        seen: set[str] = set()
        formulas: list[FormulaData] = []
        for name in available:
            for formula in outputs[name].formulas:
                key = hashlib.sha1(formula.latex.encode("utf-8")).hexdigest()[:16]
                if key in seen:
                    continue
                seen.add(key)
                formulas.append(formula)
        return formulas

    def _merge_tables(
        self, outputs: dict[str, ParserOutput], available: list[str]
    ) -> list[TableData]:
        """Deduplicate tables by id (each parser assigns a unique, deterministic id)."""
        seen: set[str] = set()
        tables: list[TableData] = []
        for name in available:
            for table in outputs[name].tables:
                if table.id in seen:
                    continue
                seen.add(table.id)
                tables.append(table)
        return tables

    def _merge_figures(
        self, outputs: dict[str, ParserOutput], available: list[str]
    ) -> list[ImageAsset]:
        """Deduplicate figures by id (each parser assigns a unique, deterministic id)."""
        seen: set[str] = set()
        figures: list[ImageAsset] = []
        for name in available:
            for figure in outputs[name].figures:
                if figure.id in seen:
                    continue
                seen.add(figure.id)
                figures.append(figure)
        return figures

    def _object_key(self, obj: EducationalObject) -> str:
        """Create a merge key for an educational object."""
        return hashlib.sha1(
            f"{obj.type}|{obj.page}|{obj.reading_order}|{obj.text[:120]}".encode("utf-8")
        ).hexdigest()[:16]

    def _rebuild_chapters(self, objects: list[EducationalObject]) -> list[Chapter]:
        """Rebuild chapter/section/subsection tree from flat headings."""
        chapters: list[Chapter] = []
        chapter_map: dict[str, Chapter] = {}
        section_map: dict[str, Section] = {}

        for obj in sorted(objects, key=lambda o: (o.page, o.reading_order)):
            if obj.type != "heading":
                continue

            title = obj.title or obj.text
            chapter_title = obj.chapter
            section_title = obj.section
            subsection_title = obj.subsection

            if chapter_title and chapter_title not in chapter_map:
                chapter = Chapter(
                    id=_make_id("chapter", obj.book, chapter_title),
                    title=chapter_title,
                    page_start=obj.page,
                )
                chapter_map[chapter_title] = chapter
                chapters.append(chapter)

            chapter = chapter_map.get(chapter_title)
            if chapter and section_title and section_title not in section_map:
                section = Section(
                    id=_make_id("section", chapter.id, section_title),
                    title=section_title,
                    page_start=obj.page,
                    parent=chapter.id,
                )
                section_map[section_title] = section
                chapter.sections.append(section)

            section = section_map.get(section_title)
            if section and subsection_title:
                subsection = SubSection(
                    id=_make_id("subsection", section.id, subsection_title),
                    title=subsection_title,
                    page_start=obj.page,
                    parent=section.id,
                )
                section.subsections.append(subsection)

        return chapters
