"""Export the Concept Layer to JSON files and SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.semantic.concepts.concept_models import ConceptIndex

logger = logging.getLogger(__name__)


class ConceptJsonExporter:
    """Write concept data to JSON files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, index: ConceptIndex) -> dict[str, Path]:
        """Export concept index to JSON files and return paths."""
        paths: dict[str, Path] = {}

        concepts_path = self.output_dir / "concepts.json"
        concepts_path.write_text(
            json.dumps([c.model_dump() for c in index.concepts], indent=2, default=str),
            encoding="utf-8",
        )
        paths["concepts"] = concepts_path
        logger.info("Wrote %d concepts to %s", len(index.concepts), concepts_path)

        index_path = self.output_dir / "concept_index.json"
        index_path.write_text(
            index.model_dump_json(indent=2),
            encoding="utf-8",
        )
        paths["concept_index"] = index_path

        return paths


class ConceptSQLiteExporter:
    """Persist concept data to SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, index: ConceptIndex) -> None:
        """Write concept data to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_schema(conn)
            self._insert_concepts(conn, index)
            self._insert_links(conn, index)
        logger.info("Wrote concepts to SQLite %s", self.db_path)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS concepts (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                name TEXT NOT NULL,
                aliases TEXT,
                subject TEXT,
                chapter TEXT,
                description TEXT,
                parent_id TEXT,
                sub_concept_ids TEXT,
                definition_ids TEXT,
                formula_ids TEXT,
                property_ids TEXT,
                theorem_ids TEXT,
                proof_ids TEXT,
                example_ids TEXT,
                exercise_ids TEXT,
                figure_ids TEXT,
                table_ids TEXT,
                related_concepts TEXT,
                metadata TEXT,
                confidence REAL,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS concept_links (
                concept_id TEXT NOT NULL,
                object_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                link_reason TEXT,
                PRIMARY KEY (concept_id, object_id),
                FOREIGN KEY (concept_id) REFERENCES concepts(id),
                FOREIGN KEY (object_id) REFERENCES objects(id)
            );
            """
        )

    def _insert_concepts(self, conn: sqlite3.Connection, index: ConceptIndex) -> None:
        for concept in index.concepts:
            conn.execute(
                """
                INSERT OR REPLACE INTO concepts
                (id, book_id, name, aliases, subject, chapter, description,
                 parent_id, sub_concept_ids,
                 definition_ids, formula_ids, property_ids, theorem_ids,
                 proof_ids, example_ids, exercise_ids, figure_ids, table_ids,
                 related_concepts, metadata, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    concept.id,
                    index.book_id,
                    concept.name,
                    json.dumps(concept.aliases),
                    concept.subject,
                    concept.chapter,
                    concept.description,
                    concept.parent_id,
                    json.dumps(concept.sub_concept_ids),
                    json.dumps(concept.definition_ids),
                    json.dumps(concept.formula_ids),
                    json.dumps(concept.property_ids),
                    json.dumps(concept.theorem_ids),
                    json.dumps(concept.proof_ids),
                    json.dumps(concept.example_ids),
                    json.dumps(concept.exercise_ids),
                    json.dumps(concept.figure_ids),
                    json.dumps(concept.table_ids),
                    json.dumps(concept.related_concepts),
                    json.dumps(concept.metadata),
                    concept.confidence,
                ),
            )

    def _insert_links(self, conn: sqlite3.Connection, index: ConceptIndex) -> None:
        for ref in index.references:
            conn.execute(
                """
                INSERT OR REPLACE INTO concept_links
                (concept_id, object_id, object_type, link_reason)
                VALUES (?, ?, ?, ?)
                """,
                (ref.concept_id, ref.object_id, ref.object_type, ref.link_reason),
            )
