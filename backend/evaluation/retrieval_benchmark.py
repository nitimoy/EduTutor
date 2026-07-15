"""Side-by-side retrieval benchmark, owned by the evaluation layer.

Runs the deterministic BM25F strategy and the Dense strategy through the frozen
``RetrievalEvaluationEngine`` on identical datasets and reports metric, latency,
embedding-generation, artifact-size, and memory comparisons. This module only
*consumes* the frozen evaluation engine; it does not modify it.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import yaml

from backend.evaluation.retrieval_engine import RetrievalEvaluationEngine
from backend.evaluation.retrieval_models import (
    RetrievalEvaluationReport,
    RetrievalQueryDataset,
)
from backend.retrieval.embedding.builder import EmbeddingBuilder
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import EmbeddingProvider, HashingEmbeddingProvider
from backend.retrieval.index.models import KnowledgeIndex
from backend.retrieval.strategies.base import RetrievalStrategy
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.retrieval.strategies.dense import DenseRetrievalStrategy
from backend.retrieval.vectorstore.local import LocalVectorStore

_METRICS = [
    "overall_mrr",
    "overall_recall_at_1",
    "overall_recall_at_3",
    "overall_recall_at_5",
    "overall_precision_at_3",
    "overall_precision_at_5",
    "overall_ndcg_at_5",
]


def _metrics_dict(report: RetrievalEvaluationReport) -> dict[str, float]:
    return {m: round(getattr(report, m), 6) for m in _METRICS}


def _avg_latency_ms(strategy: RetrievalStrategy, queries: list[str]) -> float:
    if not queries:
        return 0.0
    start = time.perf_counter()
    for q in queries:
        strategy.search(q, top_k=5)
    elapsed = time.perf_counter() - start
    return round(1000.0 * elapsed / len(queries), 4)


def _artifact_size_bytes(embeddings_root: Path, provider: EmbeddingProvider) -> int:
    idx = EmbeddingIndex(embeddings_root)
    try:
        manifest, _ = idx.load(provider.provider_id, provider.model_id)
    except FileNotFoundError:
        return 0
    version_dir = idx._version_dir(provider.provider_id, provider.model_id, manifest.version)
    return sum(p.stat().st_size for p in version_dir.glob("*") if p.is_file())


def run_comparison(
    compiled_dir: Path,
    dataset_path: Path,
    provider: EmbeddingProvider,
) -> dict[str, Any]:
    """Benchmark BM25F vs Dense on one dataset; return a structured report."""
    compiled_dir = Path(compiled_dir)
    index_path = compiled_dir / "knowledge_index.json"
    embeddings_root = compiled_dir / "embeddings"

    dataset = RetrievalQueryDataset.model_validate(
        yaml.safe_load(Path(dataset_path).read_text())
    )
    queries = [q.query for q in dataset.queries]
    knowledge_index = KnowledgeIndex.model_validate_json(index_path.read_text())

    # Ensure embeddings exist (incremental; cheap if already built) and measure a
    # clean embedding-generation time for the whole corpus.
    builder = EmbeddingBuilder()
    EmbeddingIndex(embeddings_root).build(knowledge_index, provider, builder)
    embed_start = time.perf_counter()
    builder.vectors(knowledge_index.documents, provider)
    embed_seconds = round(time.perf_counter() - embed_start, 4)

    bm25f = BM25FRetrievalStrategy(index_path)
    dense = DenseRetrievalStrategy.build(
        index_path, embeddings_root, provider, LocalVectorStore()
    )

    doc_count = len(knowledge_index.documents)
    report: dict[str, Any] = {
        "dataset": str(dataset_path),
        "query_count": len(queries),
        "document_count": doc_count,
        "strategies": {
            "bm25f": {
                "metadata": bm25f.metadata().model_dump(),
                "metrics": _metrics_dict(RetrievalEvaluationEngine(bm25f).evaluate(dataset)),
                "latency_ms_per_query": _avg_latency_ms(bm25f, queries),
            },
            "dense": {
                "metadata": dense.metadata().model_dump(),
                "metrics": _metrics_dict(RetrievalEvaluationEngine(dense).evaluate(dataset)),
                "latency_ms_per_query": _avg_latency_ms(dense, queries),
                "embedding_generation_seconds": embed_seconds,
                "artifact_size_bytes": _artifact_size_bytes(embeddings_root, provider),
                "estimated_vector_memory_bytes": doc_count * provider.dimension * 8,
            },
        },
    }
    return report


def to_markdown(report: dict[str, Any]) -> str:
    b = report["strategies"]["bm25f"]
    d = report["strategies"]["dense"]
    lines = [
        f"# Retrieval Comparison — {report['dataset']}",
        "",
        f"Queries: {report['query_count']}  ·  Documents: {report['document_count']}",
        "",
        "| Metric | BM25F | Dense |",
        "|---|---|---|",
    ]
    for m in _METRICS:
        label = m.replace("overall_", "")
        lines.append(f"| {label} | {b['metrics'][m]:.3f} | {d['metrics'][m]:.3f} |")
    lines += [
        f"| latency ms/query | {b['latency_ms_per_query']:.3f} | {d['latency_ms_per_query']:.3f} |",
        "",
        f"Dense provider: `{d['metadata']['provider']}` model `{d['metadata']['model_id']}` "
        f"dim {d['metadata']['dimension']}",
        f"Embedding generation: {d['embedding_generation_seconds']:.4f}s  ·  "
        f"artifact {d['artifact_size_bytes']} bytes  ·  "
        f"~vector memory {d['estimated_vector_memory_bytes']} bytes",
        "",
        "> Note: the default `hashing` provider validates the retrieval "
        "infrastructure, not retrieval quality. BM25F is the quality baseline; use "
        "the `bge-m3` provider for a real dense-quality comparison.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare BM25F vs Dense retrieval")
    parser.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")
    parser.add_argument("--dataset", type=Path, required=True, help="Retrieval query YAML")
    parser.add_argument("--provider", default="hashing", choices=["hashing", "bge-m3"])
    parser.add_argument("--dimension", type=int, default=256, help="Hashing provider dim")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON report here")
    args = parser.parse_args(argv)

    if args.provider == "hashing":
        provider: EmbeddingProvider = HashingEmbeddingProvider(dimension=args.dimension)
    else:
        from backend.retrieval.embedding.bge_m3 import BGEM3EmbeddingProvider

        provider = BGEM3EmbeddingProvider()

    report = run_comparison(args.compiled, args.dataset, provider)
    print(to_markdown(report))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"\nWrote JSON report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
