"""Neo4j-based knowledge graph for concept relationships."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class ConceptNode:
    """A concept node in the knowledge graph."""
    id: str
    name: str
    subject: str
    chapter: str
    definition: str = ""
    examples: list[str] = None
    section: str = ""
    page: int = 0


class Neo4jKnowledgeGraph:
    """Neo4j-backed knowledge graph for concept relationships."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    def build_from_compiled(self, compiled_dir: str | Path) -> int:
        """Build knowledge graph from compiled NCERT data."""
        compiled_dir = Path(compiled_dir)
        edge_count = 0

        with self.driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")

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
                        name = concept.get("name", "")
                        subject = concept.get("subject", "")
                        chapter = concept.get("chapter", "")

                        # Create concept node
                        session.run(
                            """
                            MERGE (c:Concept {id: $id})
                            SET c.name = $name, c.subject = $subject, c.chapter = $chapter
                            """,
                            id=cid, name=name, subject=subject, chapter=chapter,
                        )

                        # Add parent-child relationships
                        if concept.get("parent_id"):
                            session.run(
                                """
                                MATCH (child:Concept {id: $child_id})
                                MATCH (parent:Concept {id: $parent_id})
                                MERGE (child)-[:CHILD_OF]->(parent)
                                """,
                                child_id=cid, parent_id=concept["parent_id"],
                            )
                            edge_count += 1

                        # Add related concept relationships
                        for related_id in concept.get("related_concepts", []):
                            session.run(
                                """
                                MATCH (a:Concept {id: $a_id})
                                MATCH (b:Concept {id: $b_id})
                                MERGE (a)-[:RELATED_TO]->(b)
                                """,
                                a_id=cid, b_id=related_id,
                            )
                            edge_count += 1

        return edge_count

    def search_concepts(self, query_text: str, top_k: int = 5) -> list[dict]:
        """Search concepts by name."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept)
                WHERE c.name CONTAINS $query_text OR $query_text CONTAINS c.name
                RETURN c.id, c.name, c.subject, c.chapter
                LIMIT $limit
                """,
                query_text=query_text, limit=top_k,
            )
            return [dict(record) for record in result]

    def get_concept(self, concept_id: str) -> Optional[dict]:
        """Get a concept by ID."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (c:Concept {id: $id}) RETURN c",
                id=concept_id,
            )
            record = result.single()
            return dict(record["c"]) if record else None

    def get_children(self, concept_id: str) -> list[dict]:
        """Get child concepts."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept {id: $id})-[:CHILD_OF]->(child:Concept)
                RETURN child.id, child.name, child.subject, child.chapter
                """,
                id=concept_id,
            )
            return [dict(record) for record in result]

    def get_related(self, concept_id: str) -> list[dict]:
        """Get related concepts."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept {id: $id})-[:RELATED_TO]->(related:Concept)
                RETURN related.id, related.name, related.subject, related.chapter
                """,
                id=concept_id,
            )
            return [dict(record) for record in result]

    def find_path(self, start_id: str, end_id: str, max_depth: int = 3) -> Optional[list[str]]:
        """Find path between two concepts."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = shortestPath(
                    (start:Concept {id: $start_id})-[*]-(end:Concept {id: $end_id})
                )
                RETURN [n IN nodes(path) | n.id] AS path_ids
                LIMIT 1
                """,
                start_id=start_id, end_id=end_id,
            )
            record = result.single()
            return record["path_ids"] if record else None

    def stats(self) -> dict:
        """Get graph statistics."""
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS nodes")
            nodes = result.single()["nodes"]

            result = session.run("MATCH ()-[r]->() RETURN count(r) AS relationships")
            relationships = result.single()["relationships"]

            result = session.run("MATCH (c:Concept) RETURN DISTINCT c.subject AS subject")
            subjects = [record["subject"] for record in result]

            return {
                "nodes": nodes,
                "relationships": relationships,
                "subjects": subjects,
            }

    def close(self):
        """Close the driver."""
        if self._driver:
            self._driver.close()
