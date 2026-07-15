"""Export Educational IR metadata and processing state to SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.compiler.models import EducationalIR

logger = logging.getLogger(__name__)


class SQLiteExporter:
    """Persist IR metadata, parser versions, and cache to SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                part TEXT,
                source_pdf TEXT NOT NULL,
                page_count INTEGER,
                metadata TEXT,
                generated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS objects (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                type TEXT NOT NULL,
                subject TEXT NOT NULL,
                chapter TEXT,
                section TEXT,
                subsection TEXT,
                page INTEGER,
                reading_order INTEGER,
                title TEXT,
                text TEXT,
                latex TEXT,
                confidence REAL,
                coordinates TEXT,
                metadata TEXT,
                parent_id TEXT,
                children_ids TEXT,
                previous_id TEXT,
                next_id TEXT,
                semantic_relations TEXT,
                parser_name TEXT,
                parser_version TEXT,
                checksum TEXT,
                ir_version TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS formulas (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                page INTEGER,
                latex TEXT,
                text TEXT,
                confidence REAL,
                linked_paragraph_id TEXT,
                linked_example_id TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS tables (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                page INTEGER,
                rows INTEGER,
                cols INTEGER,
                cells TEXT,
                caption TEXT,
                confidence REAL,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS figures (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                page INTEGER,
                path TEXT,
                caption TEXT,
                bounding_box TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS processing_state (
                book_id TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS parser_versions (
                parser_name TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                last_used TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );
            """
        )

    def export(self, ir: EducationalIR, stage: str = "exported") -> None:
        """Write IR to SQLite."""
        with self._connect() as conn:
            self._ensure_schema(conn)
            self._insert_book(conn, ir)
            self._insert_objects(conn, ir)
            self._insert_formulas(conn, ir)
            self._insert_tables(conn, ir)
            self._insert_figures(conn, ir)
            self._upsert_parser_versions(conn, ir)
            self._upsert_state(conn, ir.book.id, stage, "success")
        logger.info("Wrote IR to SQLite %s", self.db_path)

    def _insert_book(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO books
            (id, title, subject, part, source_pdf, page_count, metadata, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ir.book.id,
                ir.book.title,
                ir.book.subject,
                ir.book.part,
                ir.book.source_pdf,
                ir.book.page_count,
                json.dumps(ir.book.metadata),
                ir.generated_at.isoformat(),
            ),
        )

    def _insert_objects(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        for obj in ir.book.objects:
            semantic_relations = {
                "prerequisites": obj.prerequisites,
                "depends_on": obj.depends_on,
                "explains": obj.explains,
                "used_by": obj.used_by,
                "related_to": obj.related_to,
                "previous_topics": obj.previous_topics,
                "next_topics": obj.next_topics,
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO objects
                (id, book_id, type, subject, chapter, section, subsection, page,
                 reading_order, title, text, latex, confidence, coordinates, metadata,
                 parent_id, children_ids, previous_id, next_id, semantic_relations,
                 parser_name, parser_version, checksum, ir_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    obj.id,
                    ir.book.id,
                    obj.type,
                    obj.subject,
                    obj.chapter,
                    obj.section,
                    obj.subsection,
                    obj.page,
                    obj.reading_order,
                    obj.title,
                    obj.text,
                    json.dumps(obj.latex),
                    obj.confidence,
                    obj.coordinates.model_dump_json() if obj.coordinates else None,
                    json.dumps(obj.metadata),
                    obj.parent_id,
                    json.dumps(obj.children_ids),
                    obj.previous_id,
                    obj.next_id,
                    json.dumps(semantic_relations),
                    obj.parser_name,
                    obj.parser_version,
                    obj.checksum,
                    obj.ir_version,
                ),
            )

    def _insert_formulas(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        for formula in ir.formulas:
            conn.execute(
                """
                INSERT OR REPLACE INTO formulas
                (id, book_id, page, latex, text, confidence, linked_paragraph_id, linked_example_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    formula.id,
                    ir.book.id,
                    formula.page,
                    formula.latex,
                    formula.text,
                    formula.confidence,
                    formula.linked_paragraph_id,
                    formula.linked_example_id,
                ),
            )

    def _insert_tables(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        for table in ir.tables:
            conn.execute(
                """
                INSERT OR REPLACE INTO tables
                (id, book_id, page, rows, cols, cells, caption, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    table.id,
                    ir.book.id,
                    table.page,
                    table.rows,
                    table.cols,
                    json.dumps([c.model_dump() for c in table.cells]),
                    table.caption,
                    table.confidence,
                ),
            )

    def _insert_figures(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        for figure in ir.figures:
            conn.execute(
                """
                INSERT OR REPLACE INTO figures
                (id, book_id, page, path, caption, bounding_box)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    figure.id,
                    ir.book.id,
                    figure.page,
                    figure.path,
                    figure.caption,
                    figure.bounding_box.model_dump_json() if figure.bounding_box else None,
                ),
            )

    def _upsert_parser_versions(self, conn: sqlite3.Connection, ir: EducationalIR) -> None:
        """Record which parser versions produced this IR, for reproducibility."""
        seen: set[tuple[str, str]] = set()
        now = datetime.now(timezone.utc).isoformat()
        for obj in ir.book.objects:
            if not obj.parser_name or (obj.parser_name, obj.parser_version) in seen:
                continue
            seen.add((obj.parser_name, obj.parser_version))
            conn.execute(
                """
                INSERT OR REPLACE INTO parser_versions (parser_name, version, last_used)
                VALUES (?, ?, ?)
                """,
                (obj.parser_name, obj.parser_version, now),
            )

    def _upsert_state(
        self,
        conn: sqlite3.Connection,
        book_id: str,
        stage: str,
        status: str,
        message: str = "",
    ) -> None:
        conn.execute(
            """
            INSERT OR REPLACE INTO processing_state
            (book_id, stage, status, updated_at, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                book_id,
                stage,
                status,
                datetime.now(timezone.utc).isoformat(),
                message,
            ),
        )
