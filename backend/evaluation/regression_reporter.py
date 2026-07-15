"""Reporter for Regression Evaluation Framework."""

import json
import os
from typing import List, Dict
from backend.evaluation.regression_models import RegressionResult, RegressionMetrics

class RegressionReporter:
    def __init__(self, output_dir: str = "data/evaluation/reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def calculate_metrics(self, results: List[RegressionResult]) -> RegressionMetrics:
        total = len(results)
        if total == 0:
            return RegressionMetrics(
                total_queries=0,
                overall_accuracy=0.0,
                retrieval_recall_1=0.0,
                retrieval_recall_5=0.0,
                intent_accuracy=0.0,
                strategy_accuracy=0.0,
                verification_pass_rate=0.0,
                unsupported_query_rate=0.0,
                avg_latency_ms=0.0,
                determinism_rate=0.0
            )

        overall_correct = sum(1 for r in results if r.retrieval_correct and r.intent_correct and r.strategy_correct and r.sections_correct and r.verification_passed)
        
        recall_1 = sum(1 for r in results if r.retrieval_rank == 1)
        recall_5 = sum(1 for r in results if r.retrieval_rank is not None and r.retrieval_rank <= 5)
        
        intent_correct = sum(1 for r in results if r.intent_correct)
        strategy_correct = sum(1 for r in results if r.strategy_correct)
        verification_passed = sum(1 for r in results if r.verification_passed)
        unsupported = sum(1 for r in results if not r.supported_actual)
        determinism = sum(1 for r in results if r.deterministic)
        
        avg_latency = sum(r.time_total_ms for r in results) / total
        
        return RegressionMetrics(
            total_queries=total,
            overall_accuracy=(overall_correct / total) * 100,
            retrieval_recall_1=(recall_1 / total) * 100,
            retrieval_recall_5=(recall_5 / total) * 100,
            intent_accuracy=(intent_correct / total) * 100,
            strategy_accuracy=(strategy_correct / total) * 100,
            verification_pass_rate=(verification_passed / total) * 100,
            unsupported_query_rate=(unsupported / total) * 100,
            avg_latency_ms=avg_latency,
            determinism_rate=(determinism / total) * 100
        )
        
    def generate_reports(self, results: List[RegressionResult]):
        metrics = self.calculate_metrics(results)
        
        # 1. regression_report.json
        report_data = {
            "metrics": metrics.model_dump(),
            "results": [r.model_dump() for r in results]
        }
        with open(os.path.join(self.output_dir, "regression_report.json"), "w") as f:
            json.dump(report_data, f, indent=2)
            
        # 2. intent_breakdown.json
        intent_breakdown = {}
        for r in results:
            if r.expected_intent not in intent_breakdown:
                intent_breakdown[r.expected_intent] = {"total": 0, "correct": 0}
            intent_breakdown[r.expected_intent]["total"] += 1
            if r.intent_correct:
                intent_breakdown[r.expected_intent]["correct"] += 1
                
        for k in intent_breakdown:
            intent_breakdown[k]["accuracy"] = (intent_breakdown[k]["correct"] / intent_breakdown[k]["total"]) * 100
            
        with open(os.path.join(self.output_dir, "intent_breakdown.json"), "w") as f:
            json.dump(intent_breakdown, f, indent=2)
            
        # 3. strategy_breakdown.json
        strategy_breakdown = {}
        for r in results:
            if r.expected_strategy not in strategy_breakdown:
                strategy_breakdown[r.expected_strategy] = {"total": 0, "correct": 0}
            strategy_breakdown[r.expected_strategy]["total"] += 1
            if r.strategy_correct:
                strategy_breakdown[r.expected_strategy]["correct"] += 1
                
        for k in strategy_breakdown:
            strategy_breakdown[k]["accuracy"] = (strategy_breakdown[k]["correct"] / strategy_breakdown[k]["total"]) * 100
            
        with open(os.path.join(self.output_dir, "strategy_breakdown.json"), "w") as f:
            json.dump(strategy_breakdown, f, indent=2)
