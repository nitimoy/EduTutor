"""Chapter index builder - maps chapters to topics for chapter-based queries.

Builds a chapter index from concept_index.json that allows:
- Looking up what topics are in a specific chapter
- Finding which chapter a topic belongs to
- Handling queries like "what can we learn from chapter 13 of math"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class ChapterIndex:
    """Maps chapters to topics for efficient chapter-based queries."""

    def __init__(self):
        self._chapters: dict[str, dict] = {}  # "subject:chapter" -> {concepts, subject, book}
        self._concept_to_chapter: dict[str, str] = {}  # concept_id -> "subject:chapter"

    def build(self, compiled_dir: str = "data/compiled") -> int:
        """Build chapter index from compiled data."""
        compiled = Path(compiled_dir)
        total_chapters = 0

        for subject_dir in sorted(compiled.iterdir()):
            if not subject_dir.is_dir():
                continue
            subject = subject_dir.name

            for book_dir in sorted(subject_dir.iterdir()):
                if not book_dir.is_dir():
                    continue

                ci_path = book_dir / "concept_index.json"
                if not ci_path.exists():
                    continue

                ci_data = json.loads(ci_path.read_text())

                # Group concepts by chapter
                chapter_concepts: dict[str, list[dict]] = {}
                for concept in ci_data.get("concepts", []):
                    chapter = concept.get("chapter", "Unknown")
                    if chapter not in chapter_concepts:
                        chapter_concepts[chapter] = []
                    chapter_concepts[chapter].append({
                        "id": concept["id"],
                        "name": concept["name"],
                        "description": concept.get("description", "")[:200],
                    })

                # Store chapter data
                for chapter, concepts in chapter_concepts.items():
                    key = f"{subject}:{chapter}"
                    self._chapters[key] = {
                        "subject": subject,
                        "chapter": chapter,
                        "book": book_dir.name,
                        "concept_count": len(concepts),
                        "concepts": [c["name"] for c in concepts],
                        "concept_ids": [c["id"] for c in concepts],
                    }

                    # Map concepts to chapters
                    for concept in ci_data.get("concepts", []):
                        if concept.get("chapter") == chapter:
                            self._concept_to_chapter[concept["id"]] = key

                    total_chapters += 1

        return total_chapters

    def get_chapters(self, subject: Optional[str] = None) -> list[dict]:
        """Get all chapters, optionally filtered by subject."""
        chapters = []
        for key, data in self._chapters.items():
            if subject and data["subject"] != subject:
                continue
            chapters.append({
                "subject": data["subject"],
                "chapter": data["chapter"],
                "book": data["book"],
                "concept_count": data["concept_count"],
                "topics": data["concepts"][:10],  # First 10 topics
            })
        return sorted(chapters, key=lambda x: (x["subject"], x["chapter"]))

    def get_chapter_topics(self, subject: str, chapter: str) -> Optional[dict]:
        """Get all topics in a specific chapter."""
        key = f"{subject}:{chapter}"
        data = self._chapters.get(key)
        if not data:
            # Try partial match
            for k, v in self._chapters.items():
                if v["subject"] == subject and chapter.lower() in v["chapter"].lower():
                    data = v
                    break
        return data

    def get_chapter_by_number(self, subject: str, chapter_num: int) -> Optional[dict]:
        """Get chapter by number (e.g., chapter 13)."""
        # Try different formats: "Chapter 13", "13", etc.
        patterns = [
            f"Chapter {chapter_num}",
            str(chapter_num),
        ]
        for pattern in patterns:
            data = self.get_chapter_topics(subject, pattern)
            if data:
                return data
        return None

    def find_chapter_for_concept(self, concept_id: str) -> Optional[str]:
        """Find which chapter a concept belongs to."""
        return self._concept_to_chapter.get(concept_id)

    def search_chapters(self, query: str) -> list[dict]:
        """Search for chapters matching a query."""
        results = []
        query_lower = query.lower()

        for key, data in self._chapters.items():
            # Check if query matches chapter name or topics
            if (query_lower in data["chapter"].lower() or
                any(query_lower in topic.lower() for topic in data["concepts"])):
                results.append({
                    "subject": data["subject"],
                    "chapter": data["chapter"],
                    "book": data["book"],
                    "concept_count": data["concept_count"],
                    "topics": data["concepts"][:10],
                })

        return results


# Global instance
_chapter_index: Optional[ChapterIndex] = None


def get_chapter_index() -> ChapterIndex:
    """Get or create the global chapter index."""
    global _chapter_index
    if _chapter_index is None:
        _chapter_index = ChapterIndex()
        _chapter_index.build()
    return _chapter_index
