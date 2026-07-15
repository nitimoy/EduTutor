"""Exporter for the Knowledge Index."""

import json
import logging
import sqlite3
from pathlib import Path

from backend.retrieval.index.models import KnowledgeIndex

logger = logging.getLogger(__name__)


class KnowledgeIndexExporter:
    """Writes the knowledge index to disk and SQLite."""

    def export_json(self, index: KnowledgeIndex, output_dir: Path) -> None:
        """Export index to JSON."""
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / "knowledge_index.json"
        
        with open(out_file, "w") as f:
            json.dump(index.model_dump(), f, indent=2)
            
        logger.info(f"Wrote Knowledge Index to {out_file}")

    def export_sqlite(self, index: KnowledgeIndex, db_path: Path) -> None:
        """Export index to SQLite database for robust querying."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create knowledge_index table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_index (
                concept_id TEXT PRIMARY KEY,
                book_id TEXT,
                name TEXT,
                aliases TEXT,
                subject TEXT,
                chapter TEXT,
                definition_texts TEXT,
                formula_latex TEXT,
                example_texts TEXT,
                prerequisites TEXT,
                next_topics TEXT,
                related_concepts TEXT,
                difficulty TEXT,
                teaching_sequence_index INTEGER
            )
        """)

        # Clear existing entries for this book
        cursor.execute("DELETE FROM knowledge_index WHERE book_id = ?", (index.book_id,))

        for doc in index.documents:
            cursor.execute("""
                INSERT INTO knowledge_index (
                    concept_id, book_id, name, aliases, subject, chapter,
                    definition_texts, formula_latex, example_texts,
                    prerequisites, next_topics, related_concepts,
                    difficulty, teaching_sequence_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc.concept_id,
                index.book_id,
                doc.name,
                json.dumps(doc.aliases),
                doc.subject,
                doc.chapter,
                json.dumps(doc.definition_texts),
                json.dumps(doc.formula_latex),
                json.dumps(doc.example_texts),
                json.dumps(doc.prerequisites),
                json.dumps(doc.next_topics),
                json.dumps(doc.related_concepts),
                doc.difficulty,
                doc.teaching_sequence_index,
            ))

        conn.commit()
        conn.close()
        logger.info(f"Wrote Knowledge Index to SQLite {db_path}")
