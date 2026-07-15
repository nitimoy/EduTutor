"""Evaluation engine for computing IR metrics on retrieval pipelines."""

import math
from backend.evaluation.retrieval_models import (
    RetrievalQueryDataset,
    RetrievalEvaluationReport,
    QueryEvaluation,
)
from backend.retrieval.api.search import RetrievalAPI
from backend.semantic.concepts.concept_resolver import normalize_concept_name


class RetrievalEvaluationEngine:
    """Computes MRR, Recall@k, Precision@k, and nDCG for retrieval testing."""

    def __init__(self, api: RetrievalAPI):
        self.api = api

    def evaluate(self, dataset: RetrievalQueryDataset) -> RetrievalEvaluationReport:
        """Run the evaluation dataset against the given Retrieval API."""
        query_evals = []

        for q in dataset.queries:
            # We want to retrieve up to top 5 for our @5 metrics.
            results = self.api.search(q.query, top_k=5)
            
            # Normalize expected names
            expected = {normalize_concept_name(name) for name in q.expected_concept_names}
            
            # Determine relevance of the returned results
            # A result is relevant if its normalized name or any alias matches an expected concept.
            relevance = []
            for res in results:
                doc_name_norm = normalize_concept_name(res.document.name)
                doc_aliases_norm = {normalize_concept_name(a) for a in res.document.aliases}
                
                if doc_name_norm in expected or expected.intersection(doc_aliases_norm):
                    relevance.append(1)
                else:
                    relevance.append(0)

            # Compute Metrics
            mrr = 0.0
            for i, rel in enumerate(relevance):
                if rel == 1:
                    mrr = 1.0 / (i + 1)
                    break
                    
            total_expected = len(expected)
            
            def recall_at(k: int) -> float:
                if total_expected == 0:
                    return 0.0
                rel_at_k = sum(relevance[:k])
                return float(rel_at_k) / total_expected
                
            def precision_at(k: int) -> float:
                rel_at_k = sum(relevance[:k])
                return float(rel_at_k) / k
                
            def dcg_at(k: int) -> float:
                dcg = 0.0
                for i, rel in enumerate(relevance[:k]):
                    dcg += rel / math.log2(i + 2)  # +2 because i is 0-indexed (log2(rank+1))
                return dcg
                
            # Ideal DCG assumes all relevant documents are ranked at the top.
            def idcg_at(k: int) -> float:
                ideal_relevance = [1] * min(total_expected, k)
                idcg = 0.0
                for i, rel in enumerate(ideal_relevance):
                    idcg += rel / math.log2(i + 2)
                return idcg if idcg > 0 else 1.0  # avoid div by zero
                
            ndcg_at_5 = dcg_at(5) / idcg_at(5) if total_expected > 0 else 0.0

            q_eval = QueryEvaluation(
                query=q.query,
                mrr=mrr,
                recall_at_1=recall_at(1),
                recall_at_3=recall_at(3),
                recall_at_5=recall_at(5),
                precision_at_1=precision_at(1),
                precision_at_3=precision_at(3),
                precision_at_5=precision_at(5),
                ndcg_at_5=ndcg_at_5,
            )
            query_evals.append(q_eval)

        # Compute overalls
        num_queries = len(query_evals)
        if num_queries == 0:
            return RetrievalEvaluationReport(dataset_version=dataset.version, search_strategy="deterministic_keyword")

        overall_mrr = sum(e.mrr for e in query_evals) / num_queries
        overall_recall_1 = sum(e.recall_at_1 for e in query_evals) / num_queries
        overall_recall_3 = sum(e.recall_at_3 for e in query_evals) / num_queries
        overall_recall_5 = sum(e.recall_at_5 for e in query_evals) / num_queries
        overall_precision_1 = sum(e.precision_at_1 for e in query_evals) / num_queries
        overall_precision_3 = sum(e.precision_at_3 for e in query_evals) / num_queries
        overall_precision_5 = sum(e.precision_at_5 for e in query_evals) / num_queries
        overall_ndcg_5 = sum(e.ndcg_at_5 for e in query_evals) / num_queries

        return RetrievalEvaluationReport(
            dataset_version=dataset.version,
            search_strategy="deterministic_keyword",
            overall_mrr=overall_mrr,
            overall_recall_at_1=overall_recall_1,
            overall_recall_at_3=overall_recall_3,
            overall_recall_at_5=overall_recall_5,
            overall_precision_at_1=overall_precision_1,
            overall_precision_at_3=overall_precision_3,
            overall_precision_at_5=overall_precision_5,
            overall_ndcg_at_5=overall_ndcg_5,
            query_evaluations=query_evals,
        )
