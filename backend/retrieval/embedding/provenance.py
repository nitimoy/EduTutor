"""Provenance and manifest models for versioned embedding artifacts.

Every embedding artifact directory carries a ``manifest.json`` recording exactly
what it was built from, so artifacts are reproducible, auditable, and safe to
coexist across providers, models, and Knowledge Index versions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingProvenance(BaseModel):
    """Immutable record of what produced an embedding artifact."""

    compiler_version: str          # backend.compiler.constants.IR_VERSION
    knowledge_index_checksum: str  # checksum of the Knowledge Index content
    book_id: str
    provider: str
    model_id: str
    dimension: int
    content_checksum: str          # aggregate over per-document checksums
    document_count: int
    created_at: str                # ISO-8601 UTC timestamp


class EmbeddingManifest(BaseModel):
    """The manifest written alongside vectors in a versioned artifact dir."""

    provenance: EmbeddingProvenance
    version: str                                   # content-addressed version id
    per_document_checksums: dict[str, str] = Field(default_factory=dict)
