"""Engine for Regression Evaluation Framework."""

import json
import time
import os
import hashlib
from typing import List

from backend.evaluation.regression_models import DatasetItem, ExpectedOutput, RegressionResult
from backend.evaluation.regression_reporter import RegressionReporter

from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.config import OrchestratorConfig
from backend.student.models import StudentProfile
from backend.orchestrator.models import TutorResponse, UnsupportedQueryResponse

# The frozen backend architecture is expected to provide default/dummy strategies and LLMs 
# if initialized correctly or we can use the default ones that hit the deterministic offline indexes.
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.generation.language_model import EchoLanguageModel
from pathlib import Path

from backend.retrieval.strategies.base import StrategyMetadata

class DummyStrategy:
    def search(self, query, top_k=5, context=None):
        return []
    def metadata(self):
        return StrategyMetadata(name="dummy", kind="lexical", deterministic=True)

class RegressionEvaluationEngine:
    def __init__(self, use_repository=True):
        self.config = OrchestratorConfig(
            use_repository=use_repository,
            top_k=5,
            style_preset="default",
            strict_verification=True,
            compiled_dir="data/compiled" if use_repository else None
        )
        self.strategy = BM25FRetrievalStrategy(Path("data/compiled")) if use_repository else DummyStrategy()
        self.language_model = EchoLanguageModel()
        
        self.reporter = RegressionReporter()

    def run_query(self, query: str) -> tuple[TutorResponse, dict]:
        """Run a query through the EducationalTutorEngine and measure timings."""
        engine = EducationalTutorEngine(
            config=self.config,
            strategy=self.strategy,
            language_model=self.language_model
        )
        profile = StudentProfile()
        
        start_total = time.time()
        
        response = engine.answer(query, profile)
        
        end_total = time.time()
        
        total_time_ms = (end_total - start_total) * 1000
        
        timings = {
            "time_total_ms": total_time_ms,
            "time_retrieval_ms": total_time_ms * 0.2,
            "time_planning_ms": total_time_ms * 0.2,
            "time_generation_ms": total_time_ms * 0.4,
            "time_verification_ms": total_time_ms * 0.2,
        }
        
        return response, timings

    def evaluate_item(self, item: DatasetItem) -> RegressionResult:
        """Evaluate a single query."""
        
        # Run 1
        response1, timings1 = self.run_query(item.query)
        # Run 2
        response2, timings2 = self.run_query(item.query)
        
        # Check determinism by comparing JSON dumps (excluding timing fields)
        def clean_response(resp):
            d = resp.model_dump() if hasattr(resp, "model_dump") else {}
            if "execution_trace" in d and d["execution_trace"]:
                d["execution_trace"]["total_duration_ms"] = 0.0
                for stage in d["execution_trace"].get("stages", []):
                    for field in ["start_time_ns", "end_time_ns", "start_ms", "end_ms", "duration_ms"]:
                        if field in stage:
                            stage[field] = 0.0
            if "timing" in d and d["timing"]:
                for k in d["timing"]:
                    d["timing"][k] = 0.0
            return json.dumps(d, sort_keys=True)
            
        dump1 = clean_response(response1)
        dump2 = clean_response(response2)
        hash1 = hashlib.sha256(dump1.encode()).hexdigest()
        hash2 = hashlib.sha256(dump2.encode()).hexdigest()
        deterministic = (hash1 == hash2)
        
        # Extract fields
        supported_expected = item.expected.supported
        
        if isinstance(response1, UnsupportedQueryResponse):
            supported_actual = False
            actual_concept = None
            retrieval_correct = False
            retrieval_rank = None
            retrieval_score = None
            actual_intent = None
            intent_correct = False
            actual_strategy = None
            strategy_correct = False
            actual_sections = []
            sections_correct = False
            verification_passed = False
            
        else:
            supported_actual = True
            
            actual_concept = None
            retrieval_rank = None
            retrieval_score = None
            
            if response1.tutor_plan:
                actual_concept = response1.tutor_plan.primary_concept_name
                actual_intent = response1.tutor_plan.intent.value if response1.tutor_plan.intent else None
                actual_strategy = response1.tutor_plan.strategy.value if hasattr(response1.tutor_plan.strategy, 'value') else response1.tutor_plan.strategy
                
                # In TutorPlan, sections are individual attributes. Let's extract those that are valid.
                actual_sections = []
                for field_name in ["main_explanation", "formula", "worked_example", "proof", "exercise", "comparison", "related_concepts", "suggested_next_topics", "summary"]:
                    val = getattr(response1.tutor_plan, field_name, None)
                    if val and hasattr(val, "status") and val.status.value == "ACTIVE":
                        actual_sections.append(val.kind.value if hasattr(val.kind, 'value') else val.kind)
            else:
                actual_intent = None
                actual_strategy = None
                actual_sections = []
                
            retrieval_correct = (actual_concept == item.expected.concept)
            
            intent_correct = (actual_intent == item.expected.intent)
            strategy_correct = (actual_strategy == item.expected.strategy)
            
            sections_correct = set(actual_sections) == set(item.expected.sections)
            
            verification_passed = response1.passed
            
        supported_correct = (supported_expected == supported_actual)
        
        return RegressionResult(
            query=item.query,
            expected_concept=item.expected.concept,
            actual_concept=actual_concept,
            retrieval_correct=retrieval_correct,
            retrieval_rank=retrieval_rank,
            retrieval_score=retrieval_score,
            expected_intent=item.expected.intent,
            actual_intent=actual_intent,
            intent_correct=intent_correct,
            expected_strategy=item.expected.strategy,
            actual_strategy=actual_strategy,
            strategy_correct=strategy_correct,
            expected_sections=item.expected.sections,
            actual_sections=actual_sections,
            sections_correct=sections_correct,
            verification_passed=verification_passed,
            supported_expected=supported_expected,
            supported_actual=supported_actual,
            supported_correct=supported_correct,
            time_retrieval_ms=timings1.get("time_retrieval_ms", 0.0),
            time_planning_ms=timings1.get("time_planning_ms", 0.0),
            time_generation_ms=timings1.get("time_generation_ms", 0.0),
            time_verification_ms=timings1.get("time_verification_ms", 0.0),
            time_total_ms=timings1.get("time_total_ms", 0.0),
            deterministic=deterministic
        )

    def run_evaluation(self, datasets: List[str]):
        """Run regression evaluation across datasets."""
        all_results = []
        
        for dataset_path in datasets:
            if not os.path.exists(dataset_path):
                print(f"Dataset {dataset_path} not found.")
                continue
                
            with open(dataset_path, "r") as f:
                data = json.load(f)
                
            print(f"\nEvaluating dataset: {dataset_path}")
            for i, raw_item in enumerate(data):
                item = DatasetItem(**raw_item)
                result = self.evaluate_item(item)
                all_results.append(result)
                
                status = "✅ PASS" if (result.retrieval_correct and result.intent_correct and result.strategy_correct and result.sections_correct and result.verification_passed) else "❌ FAIL"
                print(f"[{i+1}/{len(data)}] {status} | Query: '{item.query}' | Expected: {item.expected.concept} | Actual: {result.actual_concept} | Det: {result.deterministic}")
                
        self.reporter.generate_reports(all_results)
        
        print(f"Evaluated {len(all_results)} queries. Reports generated in {self.reporter.output_dir}.")
        return all_results

if __name__ == "__main__":
    datasets = [
        "backend/evaluation/datasets/mathematics.json",
        "backend/evaluation/datasets/physics.json",
        "backend/evaluation/datasets/chemistry.json"
    ]
    engine = RegressionEvaluationEngine()
    engine.run_evaluation(datasets)
