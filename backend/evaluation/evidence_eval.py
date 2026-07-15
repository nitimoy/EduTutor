"""Deterministic evaluation of the Evidence Assessment Engine.

Checks determinism, replayability, and verifies that supported queries pass while
unsupported queries gracefully halt the pipeline before Planning begins.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.models import UnsupportedQueryResponse
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult, StrategyMetadata
from backend.student.models import StudentProfile
from backend.generation.language_model import EchoLanguageModel


class EvidenceEvalReport(BaseModel):
    """Metrics for the evidence assessment evaluation."""

    coverage: bool = False
    educational_evidence: bool = False
    lexical_support: bool = False
    planner_support: bool = False
    presence_detection: bool = False
    determinism: bool = False
    all_passed: bool = False


class FakeStrategy:
    """Deterministic in-memory retrieval: returns fixed docs based on query."""

    def __init__(self) -> None:
        self._supported_doc = KnowledgeDocument(
            concept_id="c1", name="Alpha Protocol", subject="physics", chapter="Ch1",
            definition_texts=["Alpha Protocol denotes the leading idea."],
            example_texts=["Compute alpha carefully."], prerequisites=["Beta"]
        )
        self._hollow_doc = KnowledgeDocument(
            concept_id="c2", name="Hollow Heading", subject="physics", chapter="Ch1"
            # No definitions, formulas, or examples
        )

    def search(self, query, top_k=5, context=None):
        if "alpha" in query.lower():
            return [SearchResult(score=0.9, document=self._supported_doc)]
        elif "hollow" in query.lower():
            return [SearchResult(score=0.8, document=self._hollow_doc)]
        elif "unsupported" in query.lower():
            # Misslexical overlap
            return [SearchResult(score=0.5, document=self._supported_doc)]
        return []

    def metadata(self):
        return StrategyMetadata(name="fake", kind="lexical", deterministic=True)


def _engine() -> EducationalTutorEngine:
    config = OrchestratorConfig(
        use_repository=False, top_k=5, style_preset="default", strict_verification=False)
    return EducationalTutorEngine(
        config, strategy=FakeStrategy(), language_model=EchoLanguageModel())


class EvidenceEvaluationEngine:
    def evaluate(self) -> EvidenceEvalReport:
        report = EvidenceEvalReport(
            coverage=self._check_coverage(),
            educational_evidence=self._check_educational(),
            lexical_support=self._check_lexical(),
            planner_support=self._check_planner(),
            presence_detection=self._check_presence(),
            determinism=self._check_determinism(),
        )
        report.all_passed = all([
            report.coverage, report.educational_evidence, report.lexical_support,
            report.planner_support, report.presence_detection, report.determinism])
        return report

    def _check_coverage(self) -> bool:
        # Zero results should halt
        response = _engine().answer("zero results query", StudentProfile())
        return isinstance(response, UnsupportedQueryResponse) and not response.passed

    def _check_educational(self) -> bool:
        # Hollow concept should halt
        response = _engine().answer("hollow heading", StudentProfile())
        return isinstance(response, UnsupportedQueryResponse) and not response.passed

    def _check_lexical(self) -> bool:
        # Query with zero lexical overlap to retrieved doc
        response = _engine().answer("unsupported completely missing terms", StudentProfile())
        return isinstance(response, UnsupportedQueryResponse) and not response.passed

    def _check_planner(self) -> bool:
        # "derive alpha protocol" -> proof intent, but FakeStrategy doc has no proof texts/formulas (or examples if worked example)
        # Actually, formula intent requires formulas. 
        response = _engine().answer("formula for alpha protocol", StudentProfile())
        return isinstance(response, UnsupportedQueryResponse) and not response.passed

    def _check_presence(self) -> bool:
        # Normal supported query should PASS
        response = _engine().answer("what is alpha protocol", StudentProfile())
        # Should not be UnsupportedQueryResponse, or should have passed=True
        return not isinstance(response, UnsupportedQueryResponse) and response.passed

    def _check_determinism(self) -> bool:
        engine = _engine()
        profile = StudentProfile()
        a1 = engine.answer("what is alpha protocol", profile).deterministic_fingerprint()
        a2 = engine.answer("what is alpha protocol", profile).deterministic_fingerprint()
        
        b1 = engine.answer("zero results query", profile).deterministic_fingerprint()
        b2 = engine.answer("zero results query", profile).deterministic_fingerprint()
        
        return a1 == a2 and b1 == b2


def run_evaluation() -> EvidenceEvalReport:
    """Run the offline evaluation."""
    engine = EvidenceEvaluationEngine()
    return engine.evaluate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output JSON instead of summary")
    args = parser.parse_args()

    report = run_evaluation()
    
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print("--- Evidence Assessment Evaluation ---")
        for k, v in report.model_dump().items():
            print(f"{k.replace('_', ' ').title().ljust(30)}: {v}")
        if not report.all_passed:
            exit(1)
