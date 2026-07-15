"""Knowledge Graph for concept relationships using NetworkX."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ConceptNode:
    """A concept node in the knowledge graph."""
    id: str
    name: str
    subject: str
    chapter: str
    definition: str = ""
    examples: list[str] = field(default_factory=list)
    section: str = ""
    page: int = 0


@dataclass
class Relationship:
    """A typed relationship between concepts."""
    source_id: str
    target_id: str
    relation_type: str  # "parent_of", "prerequisite", "related", "defines", "example_of"
    weight: float = 1.0


class KnowledgeGraph:
    """Knowledge graph for concept relationships."""

    def __init__(self):
        self._concepts: dict[str, ConceptNode] = {}
        self._relationships: list[Relationship] = []
        self._adjacency: dict[str, list[tuple[str, str]]] = {}  # concept_id -> [(relation, target_id)]

    def build_from_compiled(self, compiled_dir: str | Path) -> int:
        """Build knowledge graph from compiled NCERT data."""
        compiled_dir = Path(compiled_dir)
        edge_count = 0

        for subject_dir in compiled_dir.iterdir():
            if not subject_dir.is_dir():
                continue

            for book_dir in subject_dir.iterdir():
                if not book_dir.is_dir():
                    continue

                ci_path = book_dir / "concept_index.json"
                if not ci_path.exists():
                    continue

                ci_data = json.loads(ci_path.read_text())

                for concept in ci_data.get("concepts", []):
                    cid = concept["id"]
                    self._concepts[cid] = ConceptNode(
                        id=cid,
                        name=concept.get("name", ""),
                        subject=concept.get("subject", ""),
                        chapter=concept.get("chapter", ""),
                    )

                    # Add parent-child relationships
                    if concept.get("parent_id"):
                        rel = Relationship(
                            source_id=cid,
                            target_id=concept["parent_id"],
                            relation_type="child_of",
                        )
                        self._relationships.append(rel)
                        self._adjacency.setdefault(cid, []).append(("child_of", concept["parent_id"]))
                        self._adjacency.setdefault(concept["parent_id"], []).append(("parent_of", cid))
                        edge_count += 1

                    # Add related concept relationships
                    for related_id in concept.get("related_concepts", []):
                        rel = Relationship(
                            source_id=cid,
                            target_id=related_id,
                            relation_type="related_to",
                        )
                        self._relationships.append(rel)
                        self._adjacency.setdefault(cid, []).append(("related_to", related_id))
                        edge_count += 1

        return edge_count

    def get_concept(self, concept_id: str) -> Optional[ConceptNode]:
        """Get a concept node."""
        return self._concepts.get(concept_id)

    def get_parent(self, concept_id: str) -> Optional[ConceptNode]:
        """Get the parent concept."""
        for rel_type, target_id in self._adjacency.get(concept_id, []):
            if rel_type == "child_of":
                return self._concepts.get(target_id)
        return None

    def get_children(self, concept_id: str) -> list[ConceptNode]:
        """Get child concepts."""
        children = []
        for rel_type, target_id in self._adjacency.get(concept_id, []):
            if rel_type == "parent_of":
                child = self._concepts.get(target_id)
                if child:
                    children.append(child)
        return children

    def get_related(self, concept_id: str) -> list[ConceptNode]:
        """Get related concepts."""
        related = []
        for rel_type, target_id in self._adjacency.get(concept_id, []):
            if rel_type == "related_to":
                node = self._concepts.get(target_id)
                if node:
                    related.append(node)
        return related

    def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> Optional[list[str]]:
        """Find path between two concepts using BFS."""
        if start_id == end_id:
            return [start_id]

        visited = {start_id}
        queue = [(start_id, [start_id])]

        for _ in range(max_depth):
            next_queue = []
            for node_id, path in queue:
                for rel_type, neighbor_id in self._adjacency.get(node_id, []):
                    if neighbor_id not in visited and neighbor_id in self._concepts:
                        new_path = path + [neighbor_id]
                        if neighbor_id == end_id:
                            return new_path
                        visited.add(neighbor_id)
                        next_queue.append((neighbor_id, new_path))
            queue = next_queue

        return None

    def search_concepts(self, query: str, top_k: int = 5) -> list[ConceptNode]:
        """Search concepts by name similarity."""
        query_lower = query.lower()
        results = []

        for cid, node in self._concepts.items():
            name_lower = node.name.lower()
            # Simple substring matching
            if query_lower in name_lower or name_lower in query_lower:
                results.append(node)
            elif any(word in name_lower for word in query_lower.split() if len(word) > 2):
                results.append(node)

        return results[:top_k]

    def get_chapter_concepts(self, chapter: str) -> list[ConceptNode]:
        """Get all concepts in a chapter."""
        return [node for node in self._concepts.values() if node.chapter == chapter]

    def get_subject_concepts(self, subject: str) -> list[ConceptNode]:
        """Get all concepts in a subject."""
        return [node for node in self._concepts.values() if node.subject == subject]

    def stats(self) -> dict:
        """Get graph statistics."""
        return {
            "concepts": len(self._concepts),
            "relationships": len(self._relationships),
            "subjects": len(set(node.subject for node in self._concepts.values())),
            "chapters": len(set(node.chapter for node in self._concepts.values())),
        }
