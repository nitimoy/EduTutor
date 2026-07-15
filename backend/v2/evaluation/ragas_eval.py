"""RAG evaluation using Ragas metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)


@dataclass
class EvaluationResult:
    """Result from RAG evaluation."""
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    overall_score: float
    details: dict


class RAGASEvaluator:
    """Evaluate RAG system using Ragas metrics."""

    def __init__(self):
        self._metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ]

    def evaluate(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: Optional[list[str]] = None,
    ) -> EvaluationResult:
        """Evaluate RAG responses using Ragas metrics."""
        from datasets import Dataset

        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths

        dataset = Dataset.from_dict(data)

        result = evaluate(
            dataset=dataset,
            metrics=self._metrics,
        )

        return EvaluationResult(
            faithfulness=result["faithfulness"],
            answer_relevancy=result["answer_relevancy"],
            context_precision=result["context_precision"],
            context_recall=result.get("context_recall", 0.0),
            overall_score=(
                result["faithfulness"]
                + result["answer_relevancy"]
                + result["context_precision"]
            ) / 3,
            details=dict(result),
        )

    def evaluate_single(
        self,
        question: str,
        answer: str,
        context: list[str],
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """Evaluate a single RAG response."""
        return self.evaluate(
            questions=[question],
            answers=[answer],
            contexts=[context],
            ground_truths=[ground_truth] if ground_truth else None,
        )
