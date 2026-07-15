"""Hybrid retriever combining BM25F lexical search with Qdrant vector search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.tutor.profile import ResponseProfiler


class HybridRetriever:
    """Combine BM25F lexical search with Qdrant semantic search.

    Uses Reciprocal Rank Fusion (RRF) to merge results from both retrievers.
    """

    # Shared across all instances — model loads once, stays in memory
    _shared_model = None

    def __init__(
        self,
        compiled_dir: str = "data/compiled",
        qdrant_path: str = "data/v2/qdrant_full",
    ):
        self._compiled_dir = Path(compiled_dir)
        self._qdrant_path = qdrant_path
        self._bm25f = BM25FRetrievalStrategy(self._compiled_dir)
        self._documents: dict[str, dict] = {}
        self._worked_examples: list[dict] = []
        self._qdrant_client = None
        self._build_document_map()
        self._load_worked_examples()

    def _build_document_map(self):
        """Build a map of concept_id to document for quick lookup."""
        for subject_dir in self._compiled_dir.iterdir():
            if not subject_dir.is_dir():
                continue
            for book_dir in subject_dir.iterdir():
                if not book_dir.is_dir():
                    continue
                ci_path = book_dir / "concept_index.json"
                if not ci_path.exists():
                    continue
                ci_data = json.loads(ci_path.read_text())
                for concept in ci_data.get("concepts", []):
                    metadata = concept.get("metadata", {})
                    self._documents[concept["id"]] = {
                        "concept_id": concept["id"],
                        "concept_name": concept.get("name", ""),
                        "subject": concept.get("subject", ""),
                        "chapter": concept.get("chapter", ""),
                        "page_start": metadata.get("page_start"),
                        "book": book_dir.name,
                    }

    def _load_worked_examples(self):
        """Load reassembled worked examples from worked_examples.json files."""
        for subject_dir in self._compiled_dir.iterdir():
            if not subject_dir.is_dir():
                continue
            for book_dir in subject_dir.iterdir():
                if not book_dir.is_dir():
                    continue
                examples_path = book_dir / "worked_examples.json"
                if examples_path.exists():
                    examples = json.loads(examples_path.read_text())
                    for ex in examples:
                        ex["book"] = book_dir.name
                        ex["subject"] = subject_dir.name
                    self._worked_examples.extend(examples)

    def _get_figure_ids(self, concept_id: str, book_name: str) -> list[str]:
        """Get figure IDs associated with a concept.

        Resolves the mapping: concept figure_ids → IR object IDs → image IDs.
        """
        for subject_dir in self._compiled_dir.iterdir():
            if not subject_dir.is_dir():
                continue
            book_dir = subject_dir / book_name
            if not book_dir.exists():
                continue

            # Get concept figure_ids
            ci_path = book_dir / "concept_index.json"
            if not ci_path.exists():
                continue
            ci_data = json.loads(ci_path.read_text())

            concept_fig_ids = []
            for concept in ci_data.get("concepts", []):
                if concept.get("id") == concept_id:
                    concept_fig_ids = concept.get("figure_ids", [])
                    break

            if not concept_fig_ids:
                return []

            # Resolve to image IDs via educational_ir
            ir_path = book_dir / "educational_ir.json"
            if not ir_path.exists():
                return concept_fig_ids  # Fallback to original IDs

            ir_data = json.loads(ir_path.read_text())
            object_map = {obj["id"]: obj for obj in ir_data.get("book", {}).get("objects", [])}

            image_ids = []
            for fig_id in concept_fig_ids:
                obj = object_map.get(fig_id)
                if obj and obj.get("images"):
                    # Get the first image ID from the figure object
                    for img in obj["images"]:
                        if img.get("id"):
                            image_ids.append(img["id"])
                            break
                else:
                    # Fallback to the original figure_id
                    image_ids.append(fig_id)

            return image_ids

    def _get_qdrant_client(self):
        """Lazy-load Qdrant client."""
        if self._qdrant_client is None:
            try:
                from qdrant_client import QdrantClient
                self._qdrant_client = QdrantClient(path=self._qdrant_path)
            except Exception:
                self._qdrant_client = False  # Mark as unavailable
        return self._qdrant_client if self._qdrant_client is not False else None

    def _embed_query(self, query: str) -> Optional[list[float]]:
        """Embed query using BGE-M3 if available, else return None."""
        try:
            if HybridRetriever._shared_model is None:
                from FlagEmbedding import BGEM3FlagModel
                HybridRetriever._shared_model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
            result = HybridRetriever._shared_model.encode_queries([query])
            if isinstance(result, dict):
                return result.get("dense_vecs", result)[0].tolist()
            return result[0].tolist()
        except Exception:
            return None

    def _semantic_search(
        self, query: str, top_k: int = 10, subject_filter: Optional[str] = None
    ) -> list[dict]:
        """Search using Qdrant vector store."""
        client = self._get_qdrant_client()
        if client is None:
            return []

        query_vector = self._embed_query(query)
        if query_vector is None:
            return []

        try:
            from qdrant_client.http import models as qmodels

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

            results = client.query_points(
                collection_name="edututor_knowledge",
                query=query_vector,
                limit=top_k,
                query_filter=search_filter,
            )

            return [
                {
                    "concept_id": point.payload.get("concept_id", ""),
                    "concept_name": point.payload.get("name", ""),
                    "subject": point.payload.get("subject", ""),
                    "chapter": point.payload.get("chapter", ""),
                    "score": float(point.score),
                }
                for point in results.points
            ]
        except Exception:
            return []

    def _rrf_fusion(
        self,
        bm25_results: list[dict],
        semantic_results: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """Merge results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) across all lists.
        k=60 is the standard constant from the original RRF paper.
        """
        concept_scores: dict[str, float] = {}
        concept_data: dict[str, dict] = {}

        # BM25F results
        for rank, result in enumerate(bm25_results):
            cid = result["concept_id"]
            concept_scores[cid] = concept_scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in concept_data:
                concept_data[cid] = result

        # Semantic results
        for rank, result in enumerate(semantic_results):
            cid = result["concept_id"]
            concept_scores[cid] = concept_scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in concept_data:
                concept_data[cid] = result

        # Sort by RRF score
        sorted_ids = sorted(concept_scores.keys(), key=lambda cid: concept_scores[cid], reverse=True)

        return [
            {**concept_data[cid], "rrf_score": concept_scores[cid]}
            for cid in sorted_ids
        ]

    def search(
        self,
        query: str,
        top_k: int = 10,
        subject_filter: Optional[str] = None,
    ) -> list[dict]:
        """Hybrid search combining BM25F with Qdrant semantic search via RRF."""
        # BM25F search (over-fetch for fusion)
        bm25_results_raw = self._bm25f.search(query, top_k * 3)

        # Process BM25F results
        bm25_results = []
        for r in bm25_results_raw:
            concept_name = r.document.name.lower()
            query_lower = query.lower()

            # Boost for exact concept name match
            score = r.score
            if query_lower in concept_name or concept_name in query_lower:
                score *= 2.0

            # Boost for concepts with definitions
            if len(r.document.definition_texts) > 0:
                score *= 1.5

            # Filter definitions to only include real definitions
            real_definitions = []
            for def_text in r.document.definition_texts:
                def_lower = def_text.lower()
                # Include definitions, theorems, and important statements
                if any(pattern in def_lower for pattern in [
                    'is said to be', 'is defined as', 'is called',
                    'is known as', 'refers to', 'means that',
                    'are those which', 'are substances which',
                    'is the branch of', 'is the study of',
                    'deals with', 'involves the',
                    'is the process of', 'is the science of',
                    'let f be', 'let g be', 'then a',
                    'theorem', 'proposition', 'lemma',
                    'formula', 'equation',
                ]):
                    real_definitions.append(def_text)

            # Use real definitions if available, otherwise use examples
            if real_definitions:
                # Take definitions until we have enough content (at least 2000 chars)
                # or hit max count. This ensures we capture comprehensive content.
                selected = []
                total_len = 0
                for rd in real_definitions:
                    selected.append(rd)
                    total_len += len(rd)
                    if len(selected) >= 20:  # Max 20 definitions
                        break
                    if total_len >= 2000:  # Enough content for comprehensive answer
                        break
                text = " ".join(selected)
            elif r.document.definition_texts:
                # Fallback to first non-trivial definition
                for dt in r.document.definition_texts:
                    if len(dt) > 20:  # Skip very short texts like "Theorem 1"
                        text = dt
                        break
            elif r.document.example_texts:
                text = " ".join(r.document.example_texts[:2])
            else:
                text = ""

            # Find the most relevant example text (search within examples)
            example_text = ""
            if r.document.example_texts:
                query_lower = query.lower()
                query_words = set(query_lower.split())

                # Score each example by keyword overlap with query
                scored_examples = []
                for ex in r.document.example_texts:
                    ex_lower = ex.lower()
                    # Count how many query words appear in this example
                    matches = sum(1 for word in query_words if word in ex_lower and len(word) > 2)
                    if matches > 0:
                        scored_examples.append((matches, ex))

                # Sort by match count, take top matches
                scored_examples.sort(key=lambda x: -x[0])

                if scored_examples:
                    # Return the best matching examples (up to 8)
                    example_text = " ".join(ex for _, ex in scored_examples[:8])
                else:
                    # Fallback to first few examples
                    example_text = " ".join(r.document.example_texts[:8])

            # Look up page number from document map
            doc_meta = self._documents.get(r.document.concept_id, {})

            bm25_results.append({
                "concept_id": r.document.concept_id,
                "concept_name": r.document.name,
                "subject": r.document.subject,
                "chapter": r.document.chapter,
                "score": score,
                "text": text,
                "example_text": example_text,
                "definition_count": len(real_definitions),
                "example_count": len(r.document.example_texts),
                "page_start": doc_meta.get("page_start"),
                "book": doc_meta.get("book"),
                "figure_ids": self._get_figure_ids(r.document.concept_id, doc_meta.get("book")),
            })

        # Semantic search via Qdrant
        semantic_results = self._semantic_search(query, top_k * 2, subject_filter)

        # Search within worked examples
        worked_example_results = self._search_worked_examples(query, subject_filter)

        # Fuse results using RRF
        fused = self._rrf_fusion(bm25_results, semantic_results)

        # Add worked example results if they match the query well
        if worked_example_results:
            # Only add if the worked example has a good match score
            for wer in worked_example_results[:2]:
                # Check if this worked example is relevant
                if wer.get("score", 0) >= 3:  # At least 3 keyword matches
                    # Find the right position to insert (by RRF score)
                    inserted = False
                    for i, existing in enumerate(fused):
                        if wer.get("score", 0) > existing.get("rrf_score", 0) * 100:
                            fused.insert(i, wer)
                            inserted = True
                            break
                    if not inserted and len(fused) < 10:
                        fused.append(wer)

        # Return top_k
        return fused[:top_k]

    def _search_worked_examples(self, query: str, subject_filter: Optional[str] = None) -> list[dict]:
        """Search within reassembled worked examples."""
        if not self._worked_examples:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for ex in self._worked_examples:
            # Skip if subject filter doesn't match
            if subject_filter and ex.get("subject", "").lower() != subject_filter.lower():
                continue

            # Score by keyword overlap with problem text
            problem_lower = ex.get("problem_text", "").lower()
            matches = sum(1 for word in query_words if word in problem_lower and len(word) > 2)

            if matches >= 2:  # At least 2 keywords match
                scored.append((matches, ex))

        # Sort by match count
        scored.sort(key=lambda x: -x[0])

        results = []
        for score, ex in scored[:3]:
            results.append({
                "concept_id": f"worked_example_{ex.get('id', '')}",
                "concept_name": ex.get("problem_text", "")[:50].strip(),
                "subject": ex.get("subject", ""),
                "chapter": "",
                "score": score * 0.1,  # Lower base score (will be boosted by RRF)
                "text": "",
                "example_text": ex.get("complete_text", ""),
                "definition_count": 0,
                "example_count": 1,
                "page_start": ex.get("page"),
                "book": ex.get("book"),
                "is_worked_example": True,
            })

        return results
