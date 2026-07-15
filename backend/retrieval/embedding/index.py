"""EmbeddingIndex: the canonical, versioned, on-disk store of embeddings.

Vectors are derived from the Knowledge Index and written to immutable,
content-addressed version directories with a provenance manifest. Vector stores
(local / Qdrant) are *caches* hydrated from here — never the source of truth. The
whole thing is rebuildable from ``knowledge_index.json``.

Layout::

    <root>/<provider>/<model>/index.json          # {"current": ver, "versions": [...]}
    <root>/<provider>/<model>/<version>/manifest.json
    <root>/<provider>/<model>/<version>/vectors.jsonl
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from backend.compiler.constants import IR_VERSION, compute_checksum
from backend.retrieval.embedding.builder import (
    EmbeddingBuilder,
    document_checksum,
    document_text,
)
from backend.retrieval.embedding.provenance import EmbeddingManifest, EmbeddingProvenance
from backend.retrieval.embedding.provider import EmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex

logger = logging.getLogger(__name__)

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(text: str) -> str:
    return _UNSAFE.sub("_", text).strip("_") or "model"


def _knowledge_index_checksum(documents: list[KnowledgeDocument]) -> str:
    """Provider-independent checksum identifying the Knowledge Index content."""
    parts = [
        f"{doc.concept_id}={document_text(doc)}"
        for doc in sorted(documents, key=lambda d: d.concept_id)
    ]
    return compute_checksum(*parts)


class BuildResult(BaseModel):
    """Outcome of an EmbeddingIndex build (for logging / tests)."""

    manifest: EmbeddingManifest
    embedded: int   # documents actually embedded this run
    reused: int     # documents reused from a prior version (incremental)
    created: bool    # False if this content version already existed (no-op write)


class EmbeddingIndex:
    """Reads/writes versioned embedding artifacts for one compiled book dir."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # --- paths -------------------------------------------------------------
    def _model_dir(self, provider_id: str, model_id: str) -> Path:
        return self.root / _slug(provider_id) / _slug(model_id)

    def _pointer_path(self, provider_id: str, model_id: str) -> Path:
        return self._model_dir(provider_id, model_id) / "index.json"

    def _version_dir(self, provider_id: str, model_id: str, version: str) -> Path:
        return self._model_dir(provider_id, model_id) / version

    # --- build -------------------------------------------------------------
    def build(
        self,
        knowledge_index: KnowledgeIndex,
        provider: EmbeddingProvider,
        builder: EmbeddingBuilder,
    ) -> BuildResult:
        """Build (or reuse) the embedding artifact for this KI + provider."""
        documents = knowledge_index.documents
        ki_checksum = _knowledge_index_checksum(documents)
        version = compute_checksum(
            ki_checksum, provider.provider_id, provider.model_id, provider.dimension
        )[:12]
        version_dir = self._version_dir(provider.provider_id, provider.model_id, version)

        per_doc = {doc.concept_id: document_checksum(doc, provider) for doc in documents}
        content_checksum = compute_checksum(
            *[f"{cid}={ck}" for cid, ck in sorted(per_doc.items())]
        )

        if version_dir.exists():
            # Content-addressed and immutable: identical content already built.
            manifest = self._read_manifest(version_dir)
            self._set_current(provider.provider_id, provider.model_id, version)
            logger.info("Embedding artifact already current (version %s)", version)
            return BuildResult(manifest=manifest, embedded=0, reused=len(documents), created=False)

        # Incremental: reuse vectors from the prior current version by checksum.
        reuse: dict[str, list[float]] = {}
        prior = self._load_current_optional(provider.provider_id, provider.model_id)
        if prior is not None:
            prior_manifest, prior_vectors = prior
            for doc in documents:
                cid = doc.concept_id
                if prior_manifest.per_document_checksums.get(cid) == per_doc[cid] and cid in prior_vectors:
                    reuse[cid] = prior_vectors[cid]

        to_embed = [doc for doc in documents if doc.concept_id not in reuse]
        new_vectors = builder.vectors(to_embed, provider)
        vectors = {**reuse, **new_vectors}

        provenance = EmbeddingProvenance(
            compiler_version=IR_VERSION,
            knowledge_index_checksum=ki_checksum,
            book_id=knowledge_index.book_id,
            provider=provider.provider_id,
            model_id=provider.model_id,
            dimension=provider.dimension,
            content_checksum=content_checksum,
            document_count=len(documents),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        manifest = EmbeddingManifest(
            provenance=provenance, version=version, per_document_checksums=per_doc
        )
        self._write(version_dir, manifest, vectors)
        self._set_current(provider.provider_id, provider.model_id, version)
        logger.info(
            "Built embedding artifact version %s (%d embedded, %d reused)",
            version, len(to_embed), len(reuse),
        )
        return BuildResult(
            manifest=manifest, embedded=len(to_embed), reused=len(reuse), created=True
        )

    # --- load --------------------------------------------------------------
    def load(
        self, provider_id: str, model_id: str, version: str = "current"
    ) -> tuple[EmbeddingManifest, dict[str, list[float]]]:
        if version == "current":
            version = self._current_version(provider_id, model_id)
        version_dir = self._version_dir(provider_id, model_id, version)
        if not version_dir.exists():
            raise FileNotFoundError(f"Embedding artifact not found: {version_dir}")
        return self._read_manifest(version_dir), self._read_vectors(version_dir)

    def _load_current_optional(
        self, provider_id: str, model_id: str
    ) -> tuple[EmbeddingManifest, dict[str, list[float]]] | None:
        pointer = self._pointer_path(provider_id, model_id)
        if not pointer.exists():
            return None
        current = json.loads(pointer.read_text()).get("current")
        if not current:
            return None
        version_dir = self._version_dir(provider_id, model_id, current)
        if not version_dir.exists():
            return None
        return self._read_manifest(version_dir), self._read_vectors(version_dir)

    # --- persistence helpers ----------------------------------------------
    def _write(
        self, version_dir: Path, manifest: EmbeddingManifest, vectors: dict[str, list[float]]
    ) -> None:
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        lines = [
            json.dumps({"id": cid, "vector": vectors[cid]})
            for cid in sorted(vectors)  # deterministic order
        ]
        (version_dir / "vectors.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""))

    def _read_manifest(self, version_dir: Path) -> EmbeddingManifest:
        return EmbeddingManifest.model_validate_json((version_dir / "manifest.json").read_text())

    def _read_vectors(self, version_dir: Path) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        text = (version_dir / "vectors.jsonl").read_text()
        for line in text.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            out[record["id"]] = record["vector"]
        return out

    def _current_version(self, provider_id: str, model_id: str) -> str:
        pointer = self._pointer_path(provider_id, model_id)
        if not pointer.exists():
            raise FileNotFoundError(f"No embeddings built for {provider_id}/{model_id}")
        current = json.loads(pointer.read_text()).get("current")
        if not current:
            raise FileNotFoundError(f"No current embedding version for {provider_id}/{model_id}")
        return current

    def _set_current(self, provider_id: str, model_id: str, version: str) -> None:
        pointer = self._pointer_path(provider_id, model_id)
        pointer.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(pointer.read_text()) if pointer.exists() else {"versions": []}
        versions = data.get("versions", [])
        if version not in versions:
            versions.append(version)
        pointer.write_text(json.dumps({"current": version, "versions": versions}, indent=2))
