"""PyMuPDF-based parser for layout, text, images, tables, and metadata."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import fitz

from backend.compiler.config import ParserConfig
from backend.compiler.models import (
    BoundingBox,
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
    TableCell,
)
from backend.compiler.parser.base import ParserBase, register_parser
from backend.compiler.parser.classification import (
    ParseState,
    apply_semantic_links,
    classify_block,
    extract_latex_fragments,
    make_id,
)

logger = logging.getLogger(__name__)

_FOOTNOTE_POSITION_RATIO = 0.9  # Blocks starting below 90% of the page height.
_FOOTNOTE_MAX_LEN = 200

_MAX_CHAPTER_NUMBER = 30

def _bbox_from_rect(rect: fitz.Rect, page: int) -> BoundingBox:
    return BoundingBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1, page=page)


def _clean_ocr_text(text: str) -> str:
    """Clean up common OCR artifacts like stuttering n-grams and drop caps."""
    # Fix drop caps (e.g. 'E LECTRIC C HARGES' -> 'ELECTRIC CHARGES')
    text = re.sub(r'\b([A-Z])\s+([A-Z]+)\b', r'\1\2', text)
    
    # Iteratively collapse adjacent identical n-grams (OCR stuttering).
    tokens = [t for t in text.split() if t]
    if not tokens:
        return ""
    changed = True
    while changed:
        changed = False
        for n in range(1, len(tokens) // 2 + 1):
            for i in range(len(tokens) - 2 * n + 1):
                if tokens[i:i + n] == tokens[i + n:i + 2 * n]:
                    del tokens[i:i + n]
                    changed = True
                    break
            if changed:
                break
    return " ".join(tokens)


@register_parser("pymupdf")
class PyMuPDFParser(ParserBase):
    """Parser using PyMuPDF to extract text, images, tables, and metadata."""

    name = "pymupdf"

    def __init__(self, config: ParserConfig | None = None) -> None:
        super().__init__(config)
        self.extract_images: bool = bool(self.config.extra_args.get("extract_images", True))

    @property
    def version(self) -> str:
        return getattr(fitz, "__version__", "unknown")

    def is_available(self) -> bool:
        try:
            import fitz  # noqa: F401
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
        logger.info("PyMuPDF parsing %s", pdf_path)
        doc = fitz.open(pdf_path)
        page_count = len(doc)

        book = Book(
            id=make_id("book", subject, book_title, part or ""),
            title=book_title,
            subject=subject,
            part=part,
            source_pdf=str(pdf_path),
            page_count=page_count,
            metadata=dict(doc.metadata),
        )

        objects: list[EducationalObject] = []
        formulas: list[FormulaData] = []
        tables: list[TableData] = []
        figures: list[ImageAsset] = []

        chapters: list[Chapter] = []
        chapter_map: dict[str, Chapter] = {}
        current_chapter = Chapter(id=make_id("chapter", book.id, "unknown"), title="Unknown Chapter")
        current_section = Section(id=make_id("section", current_chapter.id, "unknown"), parent=current_chapter.id)
        current_subsection = SubSection(id=make_id("subsection", current_section.id, "unknown"), parent=current_section.id)
        chapters.append(current_chapter)
        current_chapter.sections.append(current_section)
        current_section.subsections.append(current_subsection)

        state = ParseState()
        reading_order = 0

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_num = page_idx + 1
            page_height = page.rect.height

            # --- Text blocks first: they drive hierarchy and give us caption /
            # paragraph candidates that images and tables on this page can link
            # against below. Dict-mode extraction (vs. plain "blocks") gives us
            # font-weight info, which is what actually distinguishes a real
            # heading from a numbered formula/list line that happens to start
            # with a digit. ---
            blocks = self._extract_text_blocks(page)

            page_objects: list[EducationalObject] = []
            prev_type: ObjectType = "paragraph"
            for x0, y0, x1, y1, text, block_no, is_bold in blocks:
                if not text or len(text) < 2:
                    continue

                obj_type = classify_block(text, prev_type, state)
                if obj_type == "heading" and not is_bold:
                    # Font-weight says this isn't really a heading (e.g. a
                    # numbered formula line) -- fall back to a normal paragraph.
                    obj_type = "paragraph"
                elif is_bold and obj_type == "paragraph" and len(text) < 80:
                    # Short bold text that doesn't fit standard heading patterns
                    # is likely a standalone concept or sub-heading.
                    obj_type = "concept"
                if (
                    obj_type == "paragraph"
                    and y0 >= page_height * _FOOTNOTE_POSITION_RATIO
                    and len(text) <= _FOOTNOTE_MAX_LEN
                ):
                    obj_type = "footnote"
                prev_type = obj_type

                if obj_type == "heading":
                    current_chapter, current_section, current_subsection = self._update_hierarchy(
                        chapters,
                        chapter_map,
                        current_chapter,
                        current_section,
                        current_subsection,
                        text,
                        page_num,
                        subject,
                    )

                obj_id = make_id("obj", book.id, page_num, reading_order)
                latex = extract_latex_fragments(text)

                obj = EducationalObject(
                    id=obj_id,
                    type=obj_type,
                    subject=subject,
                    book=book_title,
                    chapter=current_chapter.title,
                    section=current_section.title,
                    subsection=current_subsection.title,
                    page=page_num,
                    reading_order=reading_order,
                    title=text[:80] if obj_type == "heading" else "",
                    text=text,
                    latex=latex,
                    parent_id=current_subsection.id,
                    coordinates=_bbox_from_rect(fitz.Rect(x0, y0, x1, y1), page_num),
                    confidence=0.85 if obj_type != "paragraph" else 0.7,
                    metadata={"block_no": block_no, "is_bold": is_bold},
                )
                current_subsection.objects.append(obj)
                apply_semantic_links(obj, state)
                objects.append(obj)
                page_objects.append(obj)
                reading_order += 1

                if latex:
                    for idx, frag in enumerate(latex):
                        formulas.append(
                            FormulaData(
                                id=make_id("formula", obj_id, idx),
                                page=page_num,
                                latex=frag,
                                text=frag,
                                confidence=0.6,
                                linked_paragraph_id=obj_id,
                            )
                        )

            # --- Tables: extract, then attach as inline objects linked to captions. ---
            for table in self._extract_tables(page, page_num, book.id):
                caption_obj = self._nearest_caption(page_objects, table.bounding_box, "table")
                if caption_obj:
                    table.caption = caption_obj.text
                    table.linked_object_ids.append(caption_obj.id)
                tables.append(table)

                obj_id = make_id("obj", book.id, page_num, reading_order)
                obj = EducationalObject(
                    id=obj_id,
                    type="table",
                    subject=subject,
                    book=book_title,
                    chapter=current_chapter.title,
                    section=current_section.title,
                    subsection=current_subsection.title,
                    page=page_num,
                    reading_order=reading_order,
                    text=table.caption,
                    tables=[table],
                    parent_id=current_subsection.id,
                    coordinates=table.bounding_box,
                    confidence=table.confidence,
                )
                current_subsection.objects.append(obj)
                objects.append(obj)
                reading_order += 1
                if caption_obj:
                    caption_obj.parent_id = obj.id
                    obj.children_ids.append(caption_obj.id)

            # --- Images: extract, link to nearest caption + explaining paragraph. ---
            if self.extract_images:
                for img_index, img in enumerate(page.get_images(full=True)):
                    xref = img[0]
                    rects = page.get_image_rects(xref)
                    bbox = (
                        _bbox_from_rect(rects[0], page_num)
                        if rects
                        else BoundingBox(x0=0, y0=0, x1=page.rect.width, y1=page.rect.height, page=page_num)
                    )

                    figure_id = make_id("figure", book.id, page_num, img_index)
                    figure_type: ObjectType = "figure"
                    caption_obj = self._nearest_caption(page_objects, bbox, "figure")
                    caption_text = caption_obj.text if caption_obj else ""
                    if "diagram" in caption_text.lower():
                        figure_type = "diagram"

                    image_asset = ImageAsset(id=figure_id, page=page_num, path=None, bounding_box=bbox, caption=caption_text)

                    explaining_obj = self._nearest_paragraph(page_objects, bbox)
                    if caption_obj:
                        image_asset.linked_object_ids.append(caption_obj.id)
                    if explaining_obj:
                        image_asset.linked_object_ids.append(explaining_obj.id)
                        explaining_obj.images.append(image_asset)

                    figures.append(image_asset)

                    obj_id = make_id("obj", book.id, page_num, reading_order)
                    obj = EducationalObject(
                        id=obj_id,
                        type=figure_type,
                        subject=subject,
                        book=book_title,
                        chapter=current_chapter.title,
                        section=current_section.title,
                        subsection=current_subsection.title,
                        page=page_num,
                        reading_order=reading_order,
                        text=caption_text,
                        images=[image_asset],
                        parent_id=current_subsection.id,
                        coordinates=bbox,
                        confidence=0.75,
                    )
                    current_subsection.objects.append(obj)
                    objects.append(obj)
                    reading_order += 1
                    if caption_obj:
                        caption_obj.parent_id = obj.id
                        obj.children_ids.append(caption_obj.id)

        book.objects = objects
        book.chapters = chapters
        self._stamp_provenance(objects)

        doc.close()

        return ParserOutput(
            parser_name=self.name,
            book=book,
            objects=objects,
            formulas=formulas,
            tables=tables,
            figures=figures,
            raw={"page_count": page_count},
        )

    def _update_hierarchy(
        self,
        chapters: list[Chapter],
        chapter_map: dict[str, Chapter],
        chapter: Chapter,
        section: Section,
        subsection: SubSection,
        text: str,
        page_num: int,
        subject: Subject,
    ) -> tuple[Chapter, Section, SubSection]:
        """Update chapter/section/subsection based on heading text.

        Every container created here is immediately linked into its parent's
        list, so the resulting tree has no orphaned nodes: `book.chapters` is
        the full, walkable Book -> Chapter -> Section -> SubSection tree, and
        `chapters` accumulates every chapter seen (not just the last one).
        """
        is_unit_marker = False
        if re.match(r"^(?:Unit|Chapter)\s+(?:\d+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)", text, flags=re.IGNORECASE):
            is_unit_marker = True

        text_cleaned = re.sub(r"^(?:Unit|Chapter)\s+", "", text, flags=re.IGNORECASE).strip()
        match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)", text_cleaned)
        
        if not match:
            if is_unit_marker:
                word_to_num = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12"}
                word_match = re.match(r"^([A-Za-z]+|\d+)\s*(.*)", text_cleaned)
                if word_match:
                    num_word, rest = word_match.groups()
                    if num_word.lower() in word_to_num:
                        num = word_to_num[num_word.lower()]
                        match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)", f"{num} {rest}")
                    elif num_word.isdigit():
                        match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)", f"{num_word} {rest}")

            if not match:
                return chapter, section, subsection

        number, title = match.groups()
        normalized_title = title.strip().lower()
        
        if not is_unit_marker:
            # Reject running headers / page-number noise masquerading as headings
            # (e.g. "226 MATHEMATICS", a stray "2 (" from a split formula): a real
            # heading title has some actual words in it and isn't just this
            # book's own subject name repeating on every page.
            if len(re.sub(r"[^A-Za-z]", "", title)) < 3:
                return chapter, section, subsection
            if normalized_title == subject.lower():
                return chapter, section, subsection

        parts = number.split(".")
        # A chapter number this large is never real (NCERT books top out well
        # under 20 chapters); it's almost always a stray page number or a
        # formula fragment that happens to start with digits.
        if int(parts[0]) > _MAX_CHAPTER_NUMBER:
            return chapter, section, subsection

        if len(parts) == 1:
            if number in chapter_map:
                chapter = chapter_map[number]
                if title.strip() and not chapter.title.strip():
                    chapter.title = title.strip()
            else:
                chapter_title = title.strip() or f"Chapter {number}"
                chapter = Chapter(id=make_id("chapter", chapter.id, number), title=chapter_title, number=number, page_start=page_num)
                chapters.append(chapter)
                chapter_map[number] = chapter
            section = Section(id=make_id("section", chapter.id, "root"), parent=chapter.id)
            chapter.sections.append(section)
            subsection = SubSection(id=make_id("subsection", section.id, "root"), parent=section.id)
            section.subsections.append(subsection)
            return chapter, section, subsection

        # A section/subsection whose leading number doesn't match the current
        # chapter means we've crossed into a new chapter without ever seeing
        # an explicit standalone "N Title" heading for it (common in NCERT
        # PDFs, where the chapter number is a large decorative graphic on its
        # own, not text next to the title). Infer the chapter boundary from
        # the section numbering itself instead of losing the structure, and
        # reuse the existing Chapter if this number was already seen (e.g. an
        # answer-key section cycling back through earlier chapter numbers).
        if parts[0] != chapter.number:
            if parts[0] in chapter_map:
                chapter = chapter_map[parts[0]]
            else:
                chapter_title = title.strip() or f"Chapter {parts[0]}"
                chapter = Chapter(
                    id=make_id("chapter", chapter.id, parts[0]), title=chapter_title, number=parts[0], page_start=page_num
                )
                chapter_map[parts[0]] = chapter
                chapters.append(chapter)
        else:
            if title.strip() and not chapter.title.strip():
                chapter.title = title.strip()

        if len(parts) == 2:
            section = Section(
                id=make_id("section", chapter.id, number), title=title, number=number, page_start=page_num, parent=chapter.id
            )
            chapter.sections.append(section)
            subsection = SubSection(id=make_id("subsection", section.id, "root"), parent=section.id)
            section.subsections.append(subsection)
        else:
            subsection = SubSection(
                id=make_id("subsection", section.id, number), title=title, number=number, page_start=page_num, parent=section.id
            )
            section.subsections.append(subsection)

        return chapter, section, subsection

    def _extract_text_blocks(self, page: fitz.Page) -> list[tuple[float, float, float, float, str, int, bool]]:
        """Extract text blocks with font-weight info via dict-mode extraction.

        Plain ``page.get_text("blocks")`` has no style info and, on dense
        textbook layouts, sometimes splits a single formula across multiple
        blocks that begin with a stray digit -- which is indistinguishable
        from a numbered heading by text alone. Dict-mode gives each span's
        bold flag, which is what actually separates real headings (bold) from
        numbered formula/list lines (not bold).
        """
        raw = page.get_text("dict")
        results: list[tuple[float, float, float, float, str, int, bool]] = []
        for block in raw["blocks"]:
            lines = block.get("lines")
            if not lines:
                continue
            
            text = ""
            spans = []
            for line in lines:
                line_spans = line.get("spans", [])
                spans.extend(line_spans)
                line_text = ""
                for s in line_spans:
                    if line_text and not line_text.endswith(" ") and not s["text"].startswith(" "):
                        line_text += " "
                    line_text += s["text"]
                text += line_text + " "
            text = text.strip()
            
            if not text:
                continue
                
            text = _clean_ocr_text(text)
            
            # Determine if this is an inline heading (e.g., "Effect of pressurePressure...")
            inline_heading = None
            if len(spans) > 1:
                first_span = spans[0]
                first_font = first_span.get("font", "").lower()
                first_is_bold = bool(first_span["flags"] & 16) or any(k in first_font for k in ("bold", "demi", "heavy", "black", "tango"))
                
                second_span = spans[1]
                second_font = second_span.get("font", "").lower()
                second_is_bold = bool(second_span["flags"] & 16) or any(k in second_font for k in ("bold", "demi", "heavy", "black", "tango"))
                
                first_text = first_span["text"].strip()
                if first_is_bold and not second_is_bold and 2 < len(first_text) < 60:
                    inline_heading = first_text

            # PDF flags are often unreliable (e.g., Bookman-Demi has flag 4).
            # Fall back to checking font name keywords for semantic boldness.
            bold_chars = 0
            total_chars = 0
            for span in spans:
                span_text = span.get("text", "").strip()
                total_chars += len(span_text)
                
                flags_bold = bool(span["flags"] & 16)
                font_name = span.get("font", "").lower()
                name_bold = any(k in font_name for k in ("bold", "demi", "heavy", "black", "tango"))
                if flags_bold or name_bold:
                    bold_chars += len(span_text)
                    
            is_bold = bold_chars > 0 and (bold_chars / max(1, total_chars)) > 0.5

            x0, y0, x1, y1 = block["bbox"]
            if inline_heading:
                # Emit the inline heading as a separate bold block
                results.append((x0, y0, x1, y1, inline_heading, block.get("number", 0), True))
                # The rest of the block is non-bold
                rest_text = text[len(inline_heading):].strip()
                if rest_text:
                    results.append((x0, y0, x1, y1, rest_text, block.get("number", 0) + 0.1, False))
            else:
                results.append((x0, y0, x1, y1, text, block.get("number", 0), is_bold))
        results.sort(key=lambda b: (b[1], b[0]))
        return results

    def _extract_tables(self, page: fitz.Page, page_num: int, book_id: str) -> list[TableData]:
        """Extract tables using PyMuPDF's built-in table finder if available."""
        tables: list[TableData] = []
        try:
            found = page.find_tables()
            for idx, table in enumerate(found.tables):
                rows = table.extract()
                cells: list[TableCell] = []
                for r_idx, row in enumerate(rows):
                    for c_idx, cell in enumerate(row):
                        cells.append(TableCell(row=r_idx, col=c_idx, text=str(cell) if cell is not None else ""))
                tables.append(
                    TableData(
                        id=make_id("table", book_id, page_num, idx),
                        page=page_num,
                        rows=len(rows),
                        cols=max((len(row) for row in rows), default=0),
                        cells=cells,
                        bounding_box=_bbox_from_rect(table.bbox, page_num),
                        confidence=0.75,
                    )
                )
        except Exception as exc:
            logger.debug("Table extraction failed on page %s: %s", page_num, exc)
        return tables

    def _nearest_caption(
        self, page_objects: list[EducationalObject], bbox: BoundingBox | None, kind: str
    ) -> EducationalObject | None:
        """Find the closest caption-classified block on the same page (by vertical distance)."""
        if bbox is None:
            return None
        candidates = [o for o in page_objects if o.type == "caption"]
        if kind == "table":
            table_candidates = [o for o in candidates if "table" in o.text.lower()]
            candidates = table_candidates or candidates
        if not candidates:
            return None
        return min(candidates, key=lambda o: abs((o.coordinates.y0 if o.coordinates else 0.0) - bbox.y0))

    def _nearest_paragraph(
        self, page_objects: list[EducationalObject], bbox: BoundingBox | None
    ) -> EducationalObject | None:
        """Find the nearest ordinary text block that likely explains a figure/table."""
        if bbox is None:
            return None
        candidates = [o for o in page_objects if o.type in ("paragraph", "definition", "concept") and o.coordinates]
        if not candidates:
            return None
        return min(candidates, key=lambda o: abs(o.coordinates.y0 - bbox.y0))
