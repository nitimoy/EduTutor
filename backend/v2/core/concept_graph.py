"""Simple concept graph for educational relationships."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class ConceptGraph:
    """Simple graph for concept relationships (prerequisites, related, etc.)."""

    def __init__(self):
        self._concepts: dict[str, dict] = {}
        self._edges: list[dict] = []
        self._adjacency: dict[str, list[tuple[str, str]]] = {}  # concept_id -> [(relation_type, target_id)]

    def build_from_compiled(self, compiled_dir: str | Path) -> int:
        """Build graph from compiled NCERT data."""
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
                    self._concepts[cid] = {
                        "name": concept.get("name", ""),
                        "subject": concept.get("subject", ""),
                        "chapter": concept.get("chapter", ""),
                    }

                    # Add parent-child edges
                    if concept.get("parent_id"):
                        self._add_edge(concept["parent_id"], cid, "parent_of")
                        edge_count += 1

                    # Add related concept edges
                    for related_id in concept.get("related_concepts", []):
                        self._add_edge(cid, related_id, "related_to")
                        edge_count += 1

                # Load relationships from relationships.json
                rels_path = book_dir / "relationships.json"
                if rels_path.exists():
                    rels_data = json.loads(rels_path.read_text())
                    for rel in rels_data:
                        source_id = rel.get("source_id", "")
                        target_id = rel.get("target_id", "")
                        rel_type = rel.get("relationship_type", "related_to")

                        # Only add if both concepts exist in our graph
                        if source_id in self._concepts and target_id in self._concepts:
                            self._add_edge(source_id, target_id, rel_type)
                            edge_count += 1

        return edge_count

    def _add_edge(self, source: str, target: str, edge_type: str):
        """Add an edge to the graph."""
        self._edges.append({
            "source": source,
            "target": target,
            "type": edge_type,
        })
        self._adjacency.setdefault(source, []).append((edge_type, target))
        self._adjacency.setdefault(target, []).append((edge_type, source))

    def get_prerequisites(self, concept_id: str) -> list[dict]:
        """Get prerequisites for a concept (parent_of and depends_on)."""
        prereqs = []
        for edge_type, target_id in self._adjacency.get(concept_id, []):
            if edge_type in ("parent_of", "depends_on") and target_id in self._concepts:
                prereqs.append({"id": target_id, **self._concepts[target_id]})
        return prereqs

    def get_related(self, concept_id: str) -> list[dict]:
        """Get related concepts."""
        related = []
        for edge_type, target_id in self._adjacency.get(concept_id, []):
            if edge_type == "related_to" and target_id in self._concepts:
                related.append({"id": target_id, **self._concepts[target_id]})
        return related

    def get_all_dependencies(self, concept_id: str, max_depth: int = 5) -> list[dict]:
        """Get all transitive dependencies for a concept (BFS)."""
        visited = {concept_id}
        queue = [concept_id]
        dependencies = []

        for _ in range(max_depth):
            next_queue = []
            for node_id in queue:
                for edge_type, neighbor_id in self._adjacency.get(node_id, []):
                    if edge_type in ("parent_of", "depends_on") and neighbor_id not in visited:
                        if neighbor_id in self._concepts:
                            dependencies.append({"id": neighbor_id, **self._concepts[neighbor_id]})
                            visited.add(neighbor_id)
                            next_queue.append(neighbor_id)
            queue = next_queue

        return dependencies

    def get_learning_path(self, start_concept: str, end_concept: str, max_depth: int = 5) -> list[dict]:
        """Find a learning path from one concept to another."""
        path_ids = self.find_path(start_concept, end_concept, max_depth)
        if not path_ids:
            return []
        return [{"id": cid, **self._concepts[cid]} for cid in path_ids if cid in self._concepts]

    def find_path(self, start: str, end: str, max_depth: int = 3) -> Optional[list[str]]:
        """Find path between two concepts (BFS)."""
        if start == end:
            return [start]

        visited = {start}
        queue = [(start, [start])]

        for _ in range(max_depth):
            next_queue = []
            for node, path in queue:
                for edge in self._edges:
                    neighbor = edge["target"] if edge["source"] == node else edge["source"]
                    if neighbor not in visited and neighbor in self._concepts:
                        new_path = path + [neighbor]
                        if neighbor == end:
                            return new_path
                        visited.add(neighbor)
                        next_queue.append((neighbor, new_path))
            queue = next_queue

        return None

    def get_concept_info(self, concept_id: str) -> Optional[dict]:
        """Get concept information."""
        return self._concepts.get(concept_id)

    def search_concepts(self, query: str) -> list[dict]:
        """Search concepts by name."""
        query_lower = query.lower()
        results = []
        for cid, info in self._concepts.items():
            if query_lower in info["name"].lower():
                results.append({"id": cid, **info})
        return results
