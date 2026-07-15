from collections import defaultdict
from backend.semantic.relationships.relationship_models import RelationshipIndex


class PrerequisiteEngine:
    """Computes transitive prerequisites for concepts."""

    def __init__(self) -> None:
        self.adj: dict[str, list[str]] = defaultdict(list)

    def compute(self, concept_ids: list[str], rel_index: RelationshipIndex) -> dict[str, list[str]]:
        """Returns mapping from concept_id to list of all transitive prerequisite concept_ids."""
        self.adj.clear()

        # Build adjacency list: child -> list of parents (prerequisites)
        for rel in rel_index.relationships:
            if rel.relationship_type == "depends_on":
                self.adj[rel.source_id].append(rel.target_id)
            elif rel.relationship_type == "prerequisite_of":
                self.adj[rel.target_id].append(rel.source_id)

        result: dict[str, list[str]] = {}
        for cid in concept_ids:
            result[cid] = self._find_transitive_prereqs(cid)
            
        return result

    def _find_transitive_prereqs(self, start_id: str) -> list[str]:
        visited: set[str] = set()
        queue = [start_id]
        
        while queue:
            curr = queue.pop(0)
            for prereq in self.adj.get(curr, []):
                if prereq not in visited:
                    visited.add(prereq)
                    queue.append(prereq)
                    
        return sorted(list(visited))
