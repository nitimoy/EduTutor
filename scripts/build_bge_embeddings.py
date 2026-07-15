"""Phase 1 & 2: enable BGE-M3, verify the provider, and build real embedding
indexes for Mathematics / Physics / Chemistry with statistics.

Requires the optional embedding extras:
    pip install -r backend/requirements-embeddings.txt

Usage: PYTHONPATH=. python scripts/build_bge_embeddings.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from backend.retrieval.embedding.builder import EmbeddingBuilder
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.index.models import KnowledgeIndex

SUBJECTS = {
    "mathematics": "data/compiled/mathematics/mathematics_part_1",
    "physics": "data/compiled/physics/physics_part_1",
    "chemistry": "data/compiled/chemistry/chemistry_part_1",
}


def main() -> int:
    from backend.retrieval.embedding.bge_m3 import BGEM3EmbeddingProvider

    print("Loading BGE-M3 (first run downloads the model)...")
    provider = BGEM3EmbeddingProvider()
    print(f"provider={provider.provider_id} model={provider.model_id} dim={provider.dimension}")

    # Phase 1 provider smoke checks (query embedding shape + determinism).
    q1 = provider.embed_query("what is an electric dipole")
    q2 = provider.embed_query("what is an electric dipole")
    assert len(q1) == provider.dimension, "query embedding wrong dimension"
    assert q1 == q2, "query embedding not deterministic across calls"
    print(f"[PASS] query embedding: dim={len(q1)}, deterministic")

    stats = {}
    for subject, cdir in SUBJECTS.items():
        index_path = Path(cdir) / "knowledge_index.json"
        root = Path(cdir) / "embeddings"
        ki = KnowledgeIndex.model_validate_json(index_path.read_text())
        idx = EmbeddingIndex(root)
        builder = EmbeddingBuilder()

        t0 = time.perf_counter()
        r1 = idx.build(ki, provider, builder)  # Phase 1: embedding generation
        gen_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        r2 = idx.build(ki, provider, builder)  # Phase 1: incremental / cache
        rebuild_s = time.perf_counter() - t0
        cache_hit = r2.reused / max(1, r2.reused + r2.embedded)

        manifest, vectors = idx.load(provider.provider_id, provider.model_id)
        assert set(vectors) == {d.concept_id for d in ki.documents}, "missing embeddings"
        assert all(len(v) == provider.dimension for v in vectors.values()), "dim mismatch"

        vdir = idx._version_dir(provider.provider_id, provider.model_id, manifest.version)
        index_size = sum(f.stat().st_size for f in vdir.glob("*") if f.is_file())

        stats[subject] = {
            "document_count": len(ki.documents),
            "embedding_dimension": provider.dimension,
            "build_time_s": round(gen_s, 3),
            "rebuild_time_s": round(rebuild_s, 3),
            "cache_hit_rate": round(cache_hit, 4),
            "index_size_bytes": index_size,
            "version": manifest.version,
        }
        print(f"[PASS] {subject}: {len(ki.documents)} docs embedded, dim={provider.dimension}, "
              f"gen={gen_s:.1f}s rebuild={rebuild_s:.2f}s cache_hit={cache_hit:.2f} idx={index_size}B")
        assert r2.embedded == 0 and r2.created is False, "incremental rebuild re-embedded"

    out = Path("data/evaluation/reports/bge_embedding_stats.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote embedding stats to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
