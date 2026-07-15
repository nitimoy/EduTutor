"""CLI for building and searching the Knowledge Index and its embeddings."""

import argparse
import json
import logging
from pathlib import Path

from backend.compiler.models import EducationalIR
from backend.semantic.concepts.concept_models import ConceptIndex
from backend.semantic.relationships.relationship_models import RelationshipIndex
from backend.semantic.reasoning.reasoning_models import ReasoningIndex
from backend.retrieval.index.builder import KnowledgeIndexBuilder
from backend.retrieval.index.exporter import KnowledgeIndexExporter
from backend.retrieval.index.models import KnowledgeIndex
from backend.retrieval.api.search import RetrievalAPI
from backend.retrieval.config import (
    DEFAULT_CANDIDATE_K,
    DEFAULT_HASHING_DIMENSION,
    DEFAULT_RRF_K,
)
from backend.retrieval.embedding.builder import EmbeddingBuilder
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import EmbeddingProvider, HashingEmbeddingProvider
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.retrieval.strategies.dense import DenseRetrievalStrategy
from backend.retrieval.vectorstore.base import VectorStore
from backend.retrieval.vectorstore.local import LocalVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build(compiled_dir: Path) -> None:
    """Build the Knowledge Index from compiler outputs."""
    if not compiled_dir.exists():
        logger.error(f"Directory not found: {compiled_dir}")
        return

    # Load IR
    with open(compiled_dir / "educational_ir.json") as f:
        ir = EducationalIR.model_validate_json(f.read())

    # Load Concept Index
    with open(compiled_dir / "concept_index.json") as f:
        concept_index = ConceptIndex.model_validate_json(f.read())

    # Load Relationship Index
    with open(compiled_dir / "relationships.json") as f:
        rel_data = json.load(f)
        if isinstance(rel_data, list):
            rel_index = RelationshipIndex(book_id=ir.book.id, relationships=rel_data)
        else:
            rel_index = RelationshipIndex.model_validate(rel_data)

    # Load Reasoning Index
    with open(compiled_dir / "reasoning.json") as f:
        reasoning_data = json.load(f)
        reasoning_index = ReasoningIndex.model_validate(reasoning_data)

    # Build Index
    builder = KnowledgeIndexBuilder()
    knowledge_index = builder.build(ir, concept_index, rel_index, reasoning_index)

    # Export Index
    exporter = KnowledgeIndexExporter()
    exporter.export_json(knowledge_index, compiled_dir)
    exporter.export_sqlite(knowledge_index, compiled_dir / "knowledge_index.db")


def search(compiled_dir: Path, query: str) -> None:
    """Search the Knowledge Index (deterministic BM25F)."""
    index_path = compiled_dir / "knowledge_index.json"
    if not index_path.exists():
        logger.error(f"Knowledge index not found at {index_path}. Run build first.")
        return

    api = RetrievalAPI(index_path)
    _print_results(query, api.search(query, top_k=5))


# --- embeddings / dense retrieval ------------------------------------------

def _make_provider(name: str, dimension: int, model: str) -> EmbeddingProvider:
    if name == "hashing":
        return HashingEmbeddingProvider(dimension=dimension)
    if name == "bge-m3":
        from backend.retrieval.embedding.bge_m3 import BGEM3EmbeddingProvider

        return BGEM3EmbeddingProvider(model_name=model or "BAAI/bge-m3")
    raise ValueError(f"Unknown embedding provider: {name}")


def _make_store(backend: str, dimension: int, url: str, collection: str) -> VectorStore:
    if backend == "local":
        return LocalVectorStore()
    if backend == "qdrant":
        from backend.retrieval.vectorstore.qdrant import QdrantVectorStore

        return QdrantVectorStore(dimension=dimension, url=url, collection=collection)
    raise ValueError(f"Unknown vector store backend: {backend}")


def build_embeddings(compiled_dir: Path, provider: EmbeddingProvider) -> None:
    """Build (incrementally) the versioned embedding artifact for a book."""
    index_path = compiled_dir / "knowledge_index.json"
    if not index_path.exists():
        logger.error(f"Knowledge index not found at {index_path}. Run build first.")
        return
    knowledge_index = KnowledgeIndex.model_validate_json(index_path.read_text())
    result = EmbeddingIndex(compiled_dir / "embeddings").build(
        knowledge_index, provider, EmbeddingBuilder()
    )
    print(
        f"Embeddings [{provider.provider_id}/{provider.model_id}] "
        f"version={result.manifest.version} embedded={result.embedded} "
        f"reused={result.reused} created={result.created}"
    )


def search_dense(
    compiled_dir: Path, query: str, provider: EmbeddingProvider, store: VectorStore
) -> None:
    """Search using dense embeddings (hydrating the store from the artifact)."""
    index_path = compiled_dir / "knowledge_index.json"
    try:
        strategy = DenseRetrievalStrategy.build(
            index_path, compiled_dir / "embeddings", provider, store
        )
    except FileNotFoundError:
        logger.error("No embeddings found. Run build-embeddings first.")
        return
    _print_results(query, strategy.search(query, top_k=5))


def search_hybrid(
    compiled_dir: Path,
    query: str,
    provider: EmbeddingProvider,
    store: VectorStore,
    k: int,
    candidate_k: int,
) -> None:
    """Search using RRF fusion of BM25F + Dense."""
    index_path = compiled_dir / "knowledge_index.json"
    if not index_path.exists():
        logger.error(f"Knowledge index not found at {index_path}. Run build first.")
        return
    try:
        dense = DenseRetrievalStrategy.build(
            index_path, compiled_dir / "embeddings", provider, store
        )
    except FileNotFoundError:
        logger.error("No embeddings found. Run build-embeddings first.")
        return
    from backend.retrieval.strategies.hybrid import HybridRetrievalStrategy

    hybrid = HybridRetrievalStrategy(
        [BM25FRetrievalStrategy(index_path), dense], k=k, candidate_k=candidate_k
    )
    _print_results(query, hybrid.search(query, top_k=5))


def _print_results(query: str, results) -> None:
    print(f"\nSearch Results for: '{query}'")
    print("=" * 40)
    if not results:
        print("No results found.")
        return
    for i, res in enumerate(results, 1):
        doc = res.document
        print(f"{i}. {doc.name} (Score: {res.score})")
        print(f"   Aliases: {', '.join(doc.aliases) if doc.aliases else 'None'}")
        if doc.definition_texts:
            print(f"   Definition: {doc.definition_texts[0][:100]}...")
        print("-" * 40)


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge Index CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the Knowledge Index")
    build_parser.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")

    search_parser = subparsers.add_parser("search", help="Search (BM25F)")
    search_parser.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")
    search_parser.add_argument("--query", type=str, required=True, help="Query string")

    be = subparsers.add_parser("build-embeddings", help="Build the embedding artifact")
    be.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")
    be.add_argument("--provider", default="hashing", choices=["hashing", "bge-m3"])
    be.add_argument("--dimension", type=int, default=DEFAULT_HASHING_DIMENSION)
    be.add_argument("--model", default="", help="Model id (bge-m3 backend)")

    sd = subparsers.add_parser("search-dense", help="Search (dense embeddings)")
    sd.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")
    sd.add_argument("--query", type=str, required=True, help="Query string")
    sd.add_argument("--provider", default="hashing", choices=["hashing", "bge-m3"])
    sd.add_argument("--dimension", type=int, default=DEFAULT_HASHING_DIMENSION)
    sd.add_argument("--model", default="", help="Model id (bge-m3 backend)")
    sd.add_argument("--store", default="local", choices=["local", "qdrant"])
    sd.add_argument("--qdrant-url", default="http://localhost:6333")
    sd.add_argument("--collection", default="knowledge_index")

    sh = subparsers.add_parser("search-hybrid", help="Search (RRF of BM25F + Dense)")
    sh.add_argument("--compiled", type=Path, required=True, help="Compiled book dir")
    sh.add_argument("--query", type=str, required=True, help="Query string")
    sh.add_argument("--provider", default="hashing", choices=["hashing", "bge-m3"])
    sh.add_argument("--dimension", type=int, default=DEFAULT_HASHING_DIMENSION)
    sh.add_argument("--model", default="", help="Model id (bge-m3 backend)")
    sh.add_argument("--store", default="local", choices=["local", "qdrant"])
    sh.add_argument("--qdrant-url", default="http://localhost:6333")
    sh.add_argument("--collection", default="knowledge_index")
    sh.add_argument("--rrf-k", type=int, default=DEFAULT_RRF_K, help="RRF damping constant")
    sh.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K,
                    help="Depth pulled from each component before fusion")

    args = parser.parse_args()

    if args.command == "build":
        build(args.compiled)
    elif args.command == "search":
        search(args.compiled, args.query)
    elif args.command == "build-embeddings":
        build_embeddings(args.compiled, _make_provider(args.provider, args.dimension, args.model))
    elif args.command == "search-dense":
        provider = _make_provider(args.provider, args.dimension, args.model)
        store = _make_store(args.store, provider.dimension, args.qdrant_url, args.collection)
        search_dense(args.compiled, args.query, provider, store)
    elif args.command == "search-hybrid":
        provider = _make_provider(args.provider, args.dimension, args.model)
        store = _make_store(args.store, provider.dimension, args.qdrant_url, args.collection)
        search_hybrid(args.compiled, args.query, provider, store, args.rrf_k, args.candidate_k)


if __name__ == "__main__":
    main()
