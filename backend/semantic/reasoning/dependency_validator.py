from collections import defaultdict
from backend.semantic.concepts.concept_models import ConceptIndex
from backend.semantic.relationships.relationship_models import RelationshipIndex
from backend.semantic.reasoning.reasoning_models import ReasoningValidationReport


class DependencyValidator:
    """Validates the relationship graph for cycles and broken chains."""

    def validate(self, concept_index: ConceptIndex, rel_index: RelationshipIndex) -> ReasoningValidationReport:
        valid_cids = {c.id for c in concept_index.concepts}
        
        broken_chains = []
        adj: dict[str, list[str]] = defaultdict(list)
        
        for rel in rel_index.relationships:
            if rel.relationship_type == "depends_on":
                if rel.target_id not in valid_cids:
                    broken_chains.append(f"{rel.source_id} -> {rel.target_id} (missing target)")
                else:
                    adj[rel.source_id].append(rel.target_id)
            elif rel.relationship_type == "prerequisite_of":
                if rel.source_id not in valid_cids:
                    broken_chains.append(f"{rel.source_id} (missing source) -> {rel.target_id}")
                else:
                    adj[rel.target_id].append(rel.source_id)

        cycles = self._find_cycles(adj, valid_cids)

        orphan_concepts = []
        # Iterate in sorted order so the report is byte-stable across runs.
        for cid in sorted(valid_cids):
            # An orphan might have no prerequisites AND not be a prerequisite of anything.
            # But the ConceptValidator already tracks unlinked concepts in a different way.
            # Here we just check if it's completely disconnected in the relationship graph.
            is_connected = False
            for rel in rel_index.relationships:
                if rel.source_id == cid or rel.target_id == cid:
                    is_connected = True
                    break
            if not is_connected:
                orphan_concepts.append(cid)

        return ReasoningValidationReport(
            cycles_detected=cycles,
            orphan_concepts=orphan_concepts,
            broken_chains=broken_chains
        )

    def _find_cycles(self, adj: dict[str, list[str]], nodes: set[str]) -> list[list[str]]:
        # Use DFS with coloring to find cycles
        # 0 = unvisited, 1 = visiting, 2 = visited
        color: dict[str, int] = {node: 0 for node in nodes}
        parent: dict[str, str | None] = {node: None for node in nodes}
        cycles = []

        def dfs(u: str) -> None:
            color[u] = 1
            for v in adj.get(u, []):
                if v not in color:
                    continue  # target might not be in nodes if broken chain
                if color[v] == 0:
                    parent[v] = u
                    dfs(v)
                elif color[v] == 1:
                    # Found a cycle
                    cycle = [v]
                    curr = u
                    while curr != v and curr is not None:
                        cycle.append(curr)
                        curr = parent.get(curr)
                    cycle.reverse()
                    cycles.append(cycle)
            color[u] = 2

        # Visit in sorted order so cycle discovery (and its output) is stable.
        for node in sorted(nodes):
            if color[node] == 0:
                dfs(node)

        return cycles
