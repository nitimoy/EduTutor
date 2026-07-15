"""Dense embedding retrieval strategy.

Operates only on the Knowledge Index: query text is embedded with the same
provider used to build the vectors, the vector store (a cache hydrated from the
canonical EmbeddingIndex) returns nearest documents, and results are mapped back
to KnowledgeDocuments. Deterministic; conforms to the Retrieval Strategy Contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.retrieval.api.search import SearchResult
from backend.retrieval.embedding.index import EmbeddingIndex
from backend.retrieval.embedding.provider import EmbeddingProvider
from backend.retrieval.index.models import KnowledgeDocument, KnowledgeIndex
from backend.retrieval.strategies.base import (
    RetrievalContext,
    RetrievalStrategy,
    StrategyMetadata,
    query_has_content,
)
from backend.retrieval.vectorstore.base import VectorRecord, VectorStore


class DenseRetrievalStrategy(RetrievalStrategy):
    """Vector-similarity retrieval over embedded KnowledgeDocuments."""

    def __init__(
        self,
        documents_by_id: dict[str, KnowledgeDocument],
        provider: EmbeddingProvider,
        store: VectorStore,
    ) -> None:
        self._docs = documents_by_id
        self._provider = provider
        self._store = store

    @classmethod
    def build(
        cls,
        index_path: Path,
        embeddings_root: Path,
        provider: EmbeddingProvider,
        store: VectorStore,
    ) -> "DenseRetrievalStrategy":
        """Load documents + canonical vectors and hydrate ``store`` (a cache)."""
        ki = KnowledgeIndex.model_validate_json(Path(index_path).read_text())
        docs = {doc.concept_id: doc for doc in ki.documents}
        _, vectors = EmbeddingIndex(embeddings_root).load(
            provider.provider_id, provider.model_id
        )
        records = [
            VectorRecord(
                id=cid,
                vector=vector,
                payload={
                    "concept_id": cid,
                    "subject": docs[cid].subject,
                    "chapter": docs[cid].chapter,
                },
            )
            for cid, vector in vectors.items()
            if cid in docs
        ]
        store.add(records)
        return cls(docs, provider, store)

    def search(
        self,
        query: str,
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[SearchResult]:
        if top_k <= 0 or not query_has_content(query):
            return []
        return self._search_vector(self._provider.embed_query(query), top_k, context)

    def batch_search(
        self,
        queries: list[str],
        top_k: int = 5,
        context: Optional[RetrievalContext] = None,
    ) -> list[list[SearchResult]]:
        # Batched query embedding — same results as per-query search, faster.
        vectors = self._provider.embed_documents(queries)
        out: list[list[SearchResult]] = []
        for query, vector in zip(queries, vectors):
            if top_k <= 0 or not query_has_content(query):
                out.append([])
            else:
                out.append(self._search_vector(vector, top_k, context))
        return out

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name="dense",
            kind="dense",
            deterministic=True,
            provider=self._provider.provider_id,
            model_id=self._provider.model_id,
            dimension=self._provider.dimension,
        )

    def _search_vector(
        self, vector: list[float], top_k: int, context: Optional[RetrievalContext]
    ) -> list[SearchResult]:
        if context is None or context.is_empty():
            hits = self._store.search(vector, top_k)
            return [
                SearchResult(score=hit.score, document=self._docs[hit.id])
                for hit in hits
                if hit.id in self._docs
            ]

        # Push equality filters to the store (efficient for Qdrant), over-fetch,
        # then finalize with the full context filter (covers concept_ids) before
        # truncating — so a filtered search still returns up to top_k results.
        payload_filter: dict[str, str] = {}
        if context.subject is not None:
            payload_filter["subject"] = context.subject
        if context.chapter is not None:
            payload_filter["chapter"] = context.chapter
        pool = min(len(self._docs), max(top_k * 5, 50))
        hits = self._store.search(vector, pool, payload_filter=payload_filter or None)
        results = [
            SearchResult(score=hit.score, document=self._docs[hit.id])
            for hit in hits
            if hit.id in self._docs
        ]
        return self._apply_context(results, context)[:top_k]
