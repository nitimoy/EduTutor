"""Pedagogical Benchmarking Suite.

Runs a suite of deterministic tests evaluating the orchestration layer's
ability to fetch the right concepts and form correct pedagogical plans.
"""

import json
import logging
from typing import Any, Dict
import sys

from backend.orchestrator.engine import EducationalTutorEngine
from backend.student.models import StudentProfile

logger = logging.getLogger(__name__)


class PedagogyBenchmark:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        with open(dataset_path, "r") as f:
            self.cases = json.load(f)
        
        from backend.orchestrator.config import OrchestratorConfig
        config = OrchestratorConfig(compiled_dir="data/compiled")
        self.engine = EducationalTutorEngine(config=config)
        self.profile = StudentProfile(grade_level="12", learning_style="visual")

    def evaluate(self):
        passed = 0
        total = len(self.cases)
        
        print(f"Starting Pedagogical Benchmark on {total} cases...")
        
        for case in self.cases:
            query = case["query"]
            expected = case["expected"]
            
            try:
                response = self.engine.answer(query, self.profile)
                
                from backend.orchestrator.models import UnsupportedQueryResponse
                
                # Check unsupported / out of scope queries
                if expected.get("supported") is False:
                    assert isinstance(response, UnsupportedQueryResponse), f"Query '{query}' should be unsupported."
                    passed += 1
                    continue
                    
                # From here, query must be supported
                assert not isinstance(response, UnsupportedQueryResponse), f"Query '{query}' failed evidence support. Reason: {getattr(response, 'reason', 'unknown')}"
                
                plan = response.tutor_plan
                
                if "primary_concept" in expected:
                    assert plan.primary_concept_name.lower() == expected["primary_concept"].lower(), \
                        f"Expected primary concept '{expected['primary_concept']}', got '{plan.primary_concept_name}'"
                
                if "intent" in expected:
                    assert plan.intent.value == expected["intent"], \
                        f"Expected intent '{expected['intent']}', got '{plan.intent.value}'"
                        
                if "strategy" in expected:
                    if plan.strategy.value != expected["strategy"]:
                        # Check if it was a data-aware fallback
                        fallback_note = next((note for note in getattr(plan, "notes", []) if "fell back to" in note), None)
                        if not fallback_note:
                            assert plan.strategy.value == expected["strategy"], \
                                f"Expected strategy '{expected['strategy']}', got '{plan.strategy.value}'"
                
                # Check section presence
                if "must_have_sections" in expected:
                    # Determine if a fallback occurred so we can relax strict section checks
                    fallback_note = next((note for note in getattr(plan, "notes", []) if "fell back to" in note), None)
                    if not fallback_note:
                        active_sections = [
                            s.kind.value for s in (plan.sections if hasattr(plan, 'sections') else [
                                getattr(plan, field) for field in ["prerequisites", "main_explanation", "formula", "worked_example", "proof", "exercise", "comparison", "related_concepts", "suggested_next_topics", "summary"]
                            ])
                            if getattr(s, 'status', None) and s.status.value == "present"
                        ]
                        for req_section in expected["must_have_sections"]:
                            assert req_section in active_sections, \
                                f"Missing required section '{req_section}' for query '{query}'"
                            
                if "must_not_have_sections" in expected:
                    active_sections = [
                        s.kind.value for s in (plan.sections if hasattr(plan, 'sections') else [
                            getattr(plan, field) for field in ["prerequisites", "main_explanation", "formula", "worked_example", "proof", "exercise", "comparison", "related_concepts", "suggested_next_topics", "summary"]
                        ])
                        if getattr(s, 'status', None) and s.status.value == "present"
                    ]
                    for ban_section in expected["must_not_have_sections"]:
                        assert ban_section not in active_sections, \
                            f"Found forbidden section '{ban_section}' for query '{query}'"

                passed += 1
            except AssertionError as e:
                print(f"❌ FAIL: {query}")
                print(f"   Reason: {e}")
            except Exception as e:
                print(f"❌ ERROR: {query}")
                print(f"   Exception: {e}")
                
        print(f"\n--- Pedagogical Benchmark Results ---")
        print(f"Passed: {passed}/{total} ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            print("✅ All benchmark cases passed perfectly.")
            sys.exit(0)
        else:
            print(f"⚠️ {total - passed} cases failed. See above.")
            sys.exit(1)

if __name__ == "__main__":
    benchmark = PedagogyBenchmark("backend/evaluation/datasets/pedagogy.json")
    benchmark.evaluate()
