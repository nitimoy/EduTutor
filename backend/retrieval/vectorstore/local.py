"""In-memory, dependency-free vector store (default backend).

Pure-Python cosine similarity with deterministic tie-breaking. Suitable for the
Chapter-scale corpora here; also the store used by unit tests and CI.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from backend.retrieval.vectorstore.base import VectorHit, VectorRecord, VectorStore


def _cosine(a: list[float], b: list[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class LocalVectorStore(VectorStore):
    """A simple exact-cosine store keyed by id."""

    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}

    def add(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._records[record.id] = record

    def delete(self, ids: list[str]) -> None:
        for _id in ids:
            self._records.pop(_id, None)

    def update(self, records: list[VectorRecord]) -> None:
        self.add(records)

    def search(
        self,
        vector: list[float],
        top_k: int,
        payload_filter: Optional[dict[str, Any]] = None,
    ) -> list[VectorHit]:
        if top_k <= 0:
            return []
        scored: list[tuple[float, str, VectorRecord]] = []
        for record in self._records.values():
            if payload_filter and not _matches(record.payload, payload_filter):
                continue
            score = _cosine(vector, record.vector)
            scored.append((score, record.id, record))
        # Deterministic: score desc, then id asc.
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [
            VectorHit(id=rec.id, score=round(score, 6), payload=rec.payload)
            for score, _, rec in scored[:top_k]
        ]

    # --- persistence (a cache snapshot; rebuildable from the EmbeddingIndex) ---
    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"records": [r.model_dump() for r in self._records.values()]}
        path.write_text(json.dumps(payload))

    @classmethod
    def load(cls, path: Path) -> "LocalVectorStore":
        store = cls()
        data = json.loads(Path(path).read_text())
        store.add([VectorRecord.model_validate(r) for r in data.get("records", [])])
        return store


def _matches(payload: dict[str, Any], payload_filter: dict[str, Any]) -> bool:
    return all(payload.get(key) == value for key, value in payload_filter.items())
