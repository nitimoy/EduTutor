"""Vector store interface shared by the local and Qdrant backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel, Field


class VectorRecord(BaseModel):
    """A vector plus its id and filterable payload."""

    id: str
    vector: list[float]
    payload: dict[str, Any] = Field(default_factory=dict)


class VectorHit(BaseModel):
    """A search hit: id, similarity score, and payload."""

    id: str
    score: float
    payload: dict[str, Any] = Field(default_factory=dict)


class VectorStore(ABC):
    """Query cache over embedding vectors.

    Implementations MUST return hits sorted by score descending with a stable
    secondary key (id ascending) so results are deterministic.
    """

    @abstractmethod
    def add(self, records: list[VectorRecord]) -> None:
        """Insert records (upsert by id)."""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """Remove records by id."""

    @abstractmethod
    def update(self, records: list[VectorRecord]) -> None:
        """Replace records by id (upsert)."""

    @abstractmethod
    def search(
        self,
        vector: list[float],
        top_k: int,
        payload_filter: Optional[dict[str, Any]] = None,
    ) -> list[VectorHit]:
        """Return up to top_k nearest records, optionally filtered by payload.

        ``payload_filter`` maps payload keys to a required value (equality). It is
        applied to the candidate set before top_k truncation.
        """
