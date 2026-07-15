"""Qdrant-backed vector store (production backend).

``qdrant-client`` is optional and imported lazily inside ``__init__`` — importing
this module never requires it. Concept ids (strings) are mapped to deterministic
UUID point ids; the original concept id is kept in the payload. Retrieval never
sees Qdrant-specific types — only ``VectorHit``/``VectorRecord``.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from backend.retrieval.vectorstore.base import VectorHit, VectorRecord, VectorStore

_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _point_id(concept_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, concept_id))


class QdrantVectorStore(VectorStore):
    """VectorStore backed by a Qdrant collection (cosine distance)."""

    def __init__(
        self,
        dimension: int,
        url: str = "http://localhost:6333",
        collection: str = "knowledge_index",
        recreate: bool = True,
    ) -> None:
        try:
            from qdrant_client import QdrantClient  # optional
            from qdrant_client.http import models as qmodels
        except ImportError as exc:  # pragma: no cover - exercised only without dep
            raise ImportError(
                "QdrantVectorStore requires the 'qdrant-client' package. Install it "
                "and run a Qdrant instance, or use the default LocalVectorStore."
            ) from exc
        self._qmodels = qmodels
        self._collection = collection
        self._client = QdrantClient(url=url)
        exists = self._client.collection_exists(collection)
        if recreate or not exists:
            self._client.recreate_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(
                    size=dimension, distance=qmodels.Distance.COSINE
                ),
            )

    def add(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        points = [
            self._qmodels.PointStruct(
                id=_point_id(record.id),
                vector=record.vector,
                payload={**record.payload, "concept_id": record.id},
            )
            for record in records
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def update(self, records: list[VectorRecord]) -> None:
        self.add(records)

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=self._qmodels.PointIdsList(
                points=[_point_id(_id) for _id in ids]
            ),
        )

    def search(
        self,
        vector: list[float],
        top_k: int,
        payload_filter: Optional[dict[str, Any]] = None,
    ) -> list[VectorHit]:
        if top_k <= 0:
            return []
        query_filter = None
        if payload_filter:
            query_filter = self._qmodels.Filter(
                must=[
                    self._qmodels.FieldCondition(
                        key=key, match=self._qmodels.MatchValue(value=value)
                    )
                    for key, value in payload_filter.items()
                ]
            )
        results = self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        hits = [
            VectorHit(
                id=str(point.payload.get("concept_id")),
                score=round(float(point.score), 6),
                payload=dict(point.payload or {}),
            )
            for point in results
        ]
        # Contract: stable ordering — re-sort by (score desc, id asc).
        hits.sort(key=lambda h: (-h.score, h.id))
        return hits
