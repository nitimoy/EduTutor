import json
import logging
import sqlite3
from pathlib import Path

from backend.semantic.reasoning.reasoning_models import ReasoningIndex

logger = logging.getLogger(__name__)


class ReasoningJsonExporter:
    """Exports ReasoningIndex to JSON."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, index: ReasoningIndex) -> dict[str, Path]:
        paths = {}
        
        out_path = self.output_dir / "reasoning.json"
        out_path.write_text(json.dumps(index.model_dump(), indent=2, ensure_ascii=False))
        paths["reasoning"] = out_path
        
        logger.info("Wrote reasoning to %s", out_path)
        return paths


class ReasoningSQLiteExporter:
    """Exports ReasoningIndex to SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, index: ReasoningIndex) -> None:
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_schema(conn)
            self._insert_data(conn, index)
        logger.info("Wrote reasoning to SQLite %s", self.db_path)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reasoning_metrics (
                concept_id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                is_coverage_complete BOOLEAN NOT NULL,
                prerequisite_count INTEGER NOT NULL,
                skills_json TEXT NOT NULL,
                outcomes_json TEXT NOT NULL,
                teaching_sequence_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reasoning_validation (
                book_id TEXT PRIMARY KEY,
                cycles_json TEXT,
                broken_chains_json TEXT,
                orphan_concepts_json TEXT
            );
            """
        )

    def _insert_data(self, conn: sqlite3.Connection, index: ReasoningIndex) -> None:
        for cr in index.concept_reasoning.values():
            conn.execute(
                """
                INSERT OR REPLACE INTO reasoning_metrics
                (concept_id, book_id, difficulty, is_coverage_complete, prerequisite_count, skills_json, outcomes_json, teaching_sequence_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cr.concept_id,
                    index.book_id,
                    cr.difficulty,
                    cr.coverage.is_complete,
                    len(cr.required_prerequisites),
                    json.dumps([s.model_dump() for s in cr.skills_developed]),
                    json.dumps(cr.learning_outcomes.model_dump() if cr.learning_outcomes else {}),
                    json.dumps(cr.teaching_sequence),
                )
            )

        conn.execute(
            """
            INSERT OR REPLACE INTO reasoning_validation
            (book_id, cycles_json, broken_chains_json, orphan_concepts_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                index.book_id,
                json.dumps(index.validation_report.cycles_detected),
                json.dumps(index.validation_report.broken_chains),
                json.dumps(index.validation_report.orphan_concepts),
            )
        )
