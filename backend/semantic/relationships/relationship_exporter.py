import json
import logging
import sqlite3
from pathlib import Path

from backend.semantic.relationships.relationship_models import RelationshipIndex

logger = logging.getLogger(__name__)


class RelationshipJsonExporter:
    """Exports RelationshipIndex to JSON."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, index: RelationshipIndex) -> dict[str, Path]:
        """Write index to relationships.json"""
        paths = {}
        
        rel_path = self.output_dir / "relationships.json"
        rel_data = [r.model_dump() for r in index.relationships]
        rel_path.write_text(json.dumps(rel_data, indent=2, ensure_ascii=False))
        paths["relationships"] = rel_path
        
        logger.info("Wrote relationships to %s", rel_path)
        return paths


class RelationshipSQLiteExporter:
    """Exports RelationshipIndex to SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, index: RelationshipIndex) -> None:
        """Write relationships to SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            self._ensure_schema(conn)
            self._insert_relationships(conn, index)
        logger.info("Wrote relationships to SQLite %s", self.db_path)

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence TEXT,
                inference_method TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id, relationship_type)
            );
            """
        )

    def _insert_relationships(self, conn: sqlite3.Connection, index: RelationshipIndex) -> None:
        for rel in index.relationships:
            conn.execute(
                """
                INSERT OR REPLACE INTO relationships
                (source_id, target_id, relationship_type, confidence, evidence, inference_method)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    rel.source_id,
                    rel.target_id,
                    rel.relationship_type,
                    rel.confidence,
                    rel.evidence,
                    rel.inference_method,
                ),
            )
