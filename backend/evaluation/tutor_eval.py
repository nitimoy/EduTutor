"""Deterministic evaluation engine for the Tutor Brain.

Runs the brain over a labeled dataset (through any ``RetrievalStrategy``) and reports:

* **intent accuracy** / **strategy accuracy** / **primary-concept accuracy** vs. labels,
* **citation validity** — the fraction of references whose concept id exists in the
  Knowledge Index (a real, traceable object),
* **no-hallucination rate** — the fraction of cases with zero invalid references,
* **determinism** — whether every plan is byte-identical across two runs.

Evaluation-owned (mirrors ``retrieval_benchmark``); it consumes the frozen retrieval and
compiler artifacts but modifies nothing. Offline by default (BM25F).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import yaml

from backend.evaluation.tutor_models import (
    CaseResult,
    TutorCase,
    TutorEvalDataset,
    TutorEvalReport,
)
from backend.retrieval.index.models import KnowledgeIndex
from backend.retrieval.strategies.base import RetrievalStrategy
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.semantic.concepts.concept_resolver import normalize_concept_name
from backend.tutor.composer import TutorBrain
from backend.tutor.repository import CompiledArtifactRepository, KnowledgeRepository


class TutorPlanEvaluationEngine:
    """Score Tutor Brain plans against a labeled dataset. Deterministic."""

    def __init__(
        self,
        strategy: RetrievalStrategy,
        index: KnowledgeIndex,
        repository: Optional[KnowledgeRepository] = None,
        brain: Optional[TutorBrain] = None,
        top_k: int = 5,
    ) -> None:
        self._strategy = strategy
        self._index_ids = {d.concept_id for d in index.documents}
        self._repository = repository
        self._brain = brain or TutorBrain()
        self._top_k = top_k

    def evaluate(self, dataset: TutorEvalDataset) -> TutorEvalReport:
        case_results = [self._evaluate_case(c) for c in dataset.cases]
        n = len(case_results)

        def _acc(pred: str) -> float:
            scored = [getattr(r, pred) for r in case_results if getattr(r, pred) is not None]
            return round(sum(1 for ok in scored if ok) / len(scored), 6) if scored else 0.0

        total_refs = sum(r.n_references for r in case_results)
        invalid_refs = sum(r.invalid_references for r in case_results)
        citation_validity = (
            round((total_refs - invalid_refs) / total_refs, 6) if total_refs else 1.0
        )
        clean = sum(1 for r in case_results if r.invalid_references == 0)

        return TutorEvalReport(
            dataset_version=dataset.version,
            subject=dataset.subject,
            n_cases=n,
            intent_accuracy=_acc("intent_ok"),
            strategy_accuracy=_acc("strategy_ok"),
            primary_accuracy=_acc("primary_ok"),
            citation_validity=citation_validity,
            no_hallucination_rate=round(clean / n, 6) if n else 1.0,
            deterministic=all(r.deterministic for r in case_results),
            case_results=case_results,
        )

    def _evaluate_case(self, case: TutorCase) -> CaseResult:
        results = self._strategy.search(case.query, top_k=self._top_k)
        plan = self._brain.plan(case.query, results, self._repository)
        # Determinism: a second identical run must be byte-identical.
        plan2 = self._brain.plan(case.query, results, self._repository)
        deterministic = plan.model_dump_json() == plan2.model_dump_json()

        invalid = sum(
            1 for c in plan.references
            if c.concept_id is not None and c.concept_id not in self._index_ids
        )

        intent_ok = (
            None if case.expected_intent is None
            else plan.intent.value == case.expected_intent
        )
        strategy_ok = (
            None if case.expected_strategy is None
            else plan.strategy.value == case.expected_strategy
        )
        primary_ok = (
            None if case.expected_primary_concept_name is None
            else normalize_concept_name(plan.primary_concept_name)
            == normalize_concept_name(case.expected_primary_concept_name)
        )

        return CaseResult(
            query=case.query,
            intent=plan.intent.value,
            expected_intent=case.expected_intent,
            intent_ok=intent_ok,
            strategy=plan.strategy.value,
            expected_strategy=case.expected_strategy,
            strategy_ok=strategy_ok,
            primary_concept_name=plan.primary_concept_name,
            expected_primary_concept_name=case.expected_primary_concept_name,
            primary_ok=primary_ok,
            n_references=len(plan.references),
            invalid_references=invalid,
            deterministic=deterministic,
        )


def _print_summary(report: TutorEvalReport) -> None:
    print(f"\n=== Tutor Brain eval — {report.subject} (v{report.dataset_version}) ===")
    print(f"  cases                {report.n_cases}")
    print(f"  intent accuracy      {report.intent_accuracy:.3f}")
    print(f"  strategy accuracy    {report.strategy_accuracy:.3f}")
    print(f"  primary accuracy     {report.primary_accuracy:.3f}")
    print(f"  citation validity    {report.citation_validity:.3f}")
    print(f"  no-hallucination     {report.no_hallucination_rate:.3f}")
    print(f"  deterministic        {report.deterministic}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Tutor Brain planning pipeline")
    ap.add_argument("--compiled", type=Path, required=True,
                    help="Compiled book dir (has knowledge_index.json + concept_index.json + educational_ir.json)")
    ap.add_argument("--dataset", type=Path, required=True, help="Tutor eval dataset YAML")
    ap.add_argument("--no-repository", action="store_true",
                    help="Skip concept recovery (retrieval-index-only mode)")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    index_path = args.compiled / "knowledge_index.json"
    index = KnowledgeIndex.model_validate_json(index_path.read_text())
    strategy = BM25FRetrievalStrategy(index_path)
    repository = None if args.no_repository else CompiledArtifactRepository.from_compiled_dir(args.compiled)
    dataset = TutorEvalDataset.model_validate(yaml.safe_load(args.dataset.read_text()))

    engine = TutorPlanEvaluationEngine(strategy, index, repository, top_k=args.top_k)
    report = engine.evaluate(dataset)
    _print_summary(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
