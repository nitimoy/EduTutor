"""Load existing BGE-M3 embeddings into Qdrant (local mode)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


COLLECTION_NAME = "edututor_knowledge"
VECTOR_DIMENSION = 1024
_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _point_id(concept_id: str) -> str:
    """Convert concept_id to deterministic UUID for Qdrant."""
    return str(uuid.uuid5(_NAMESPACE, concept_id))


def load_embeddings_into_qdrant(
    compiled_dir: str = "data/compiled",
    qdrant_path: str = "data/v2/qdrant_full",
) -> dict:
    """Load all BGE-M3 embeddings from compiled data into Qdrant.

    Returns stats about the loaded data.
    """
    compiled = Path(compiled_dir)
    client = QdrantClient(path=qdrant_path)

    # Create or recreate collection
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if COLLECTION_NAME in collection_names:
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_DIMENSION,
            distance=qmodels.Distance.COSINE,
        ),
    )

    total_vectors = 0
    all_points = []

    for subject_dir in sorted(compiled.iterdir()):
        if not subject_dir.is_dir():
            continue

        for book_dir in sorted(subject_dir.iterdir()):
            if not book_dir.is_dir():
                continue

            # Load concept index for metadata
            ci_path = book_dir / "concept_index.json"
            if not ci_path.exists():
                continue

            ci_data = json.loads(ci_path.read_text())
            concept_meta = {}
            for concept in ci_data.get("concepts", []):
                metadata = concept.get("metadata", {})
                concept_meta[concept["id"]] = {
                    "name": concept.get("name", ""),
                    "subject": concept.get("subject", ""),
                    "chapter": concept.get("chapter", ""),
                    "book": book_dir.name,
                    "page_start": metadata.get("page_start"),
                }

            # Load embeddings
            emb_dir = book_dir / "embeddings" / "bge-m3" / "BAAI_bge-m3"
            if not emb_dir.exists():
                continue

            index_path = emb_dir / "index.json"
            if not index_path.exists():
                continue

            index_data = json.loads(index_path.read_text())
            current_version = index_data.get("current", "")

            vectors_path = emb_dir / current_version / "vectors.jsonl"
            if not vectors_path.exists():
                continue

            # Read vectors
            with open(vectors_path) as f:
                for line in f:
                    entry = json.loads(line.strip())
                    concept_id = entry["id"]
                    vector = entry["vector"]

                    # Get metadata
                    meta = concept_meta.get(concept_id, {})

                    point = qmodels.PointStruct(
                        id=_point_id(concept_id),
                        vector=vector,
                        payload={
                            "concept_id": concept_id,
                            "name": meta.get("name", ""),
                            "subject": meta.get("subject", ""),
                            "chapter": meta.get("chapter", ""),
                            "book": meta.get("book", ""),
                            "page_start": meta.get("page_start"),
                        },
                    )
                    all_points.append(point)
                    total_vectors += 1

    # Batch upsert (Qdrant handles batching internally)
    if all_points:
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(all_points), batch_size):
            batch = all_points[i : i + batch_size]
            client.upsert(collection_name=COLLECTION_NAME, points=batch)

    stats = {
        "total_vectors": total_vectors,
        "collection": COLLECTION_NAME,
        "qdrant_path": qdrant_path,
        "dimension": VECTOR_DIMENSION,
    }

    print(f"Loaded {total_vectors} vectors into Qdrant at {qdrant_path}")
    return stats


def get_qdrant_client(qdrant_path: str = "data/v2/qdrant_full") -> QdrantClient:
    """Get a Qdrant client for the local collection."""
    return QdrantClient(path=qdrant_path)


def search_qdrant(
    query_vector: list[float],
    top_k: int = 10,
    qdrant_path: str = "data/v2/qdrant_full",
    subject_filter: Optional[str] = None,
) -> list[dict]:
    """Search Qdrant for similar vectors."""
    client = get_qdrant_client(qdrant_path)

    search_filter = None
    if subject_filter:
        search_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="subject",
                    match=qmodels.MatchValue(value=subject_filter),
                )
            ]
        )

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True,
    )

    return [
        {
            "concept_id": point.payload.get("concept_id", ""),
            "name": point.payload.get("name", ""),
            "subject": point.payload.get("subject", ""),
            "chapter": point.payload.get("chapter", ""),
            "score": float(point.score),
        }
        for point in results
    ]


if __name__ == "__main__":
    stats = load_embeddings_into_qdrant()
    print(json.dumps(stats, indent=2))
