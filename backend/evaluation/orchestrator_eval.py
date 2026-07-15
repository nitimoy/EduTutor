"""Deterministic evaluation of the Educational Tutor Orchestrator.

Fully offline: an injected in-memory ``FakeStrategy`` (fixed results over synthetic
KnowledgeDocuments) + the Echo renderer + no repository — no compiled data required. Checks
determinism, stage ordering, metadata propagation, verification-failure handling, citation
preservation, configuration propagation, and no mutation of frozen inputs. Architectural
correctness only.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from backend.evaluation.orchestrator_models import OrchestratorEvalReport
from backend.generation.language_model import EchoLanguageModel
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.engine import STAGES, EducationalTutorEngine
from backend.orchestrator.errors import VerificationFailedError
from backend.retrieval.index.models import KnowledgeDocument
from backend.retrieval.strategies.base import SearchResult, StrategyMetadata
from backend.student.models import (
    DifficultyPreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)
from backend.verification.engine import ResponseVerificationEngine


class FakeStrategy:
    """Deterministic in-memory retrieval: returns a fixed 2-doc result for any query."""

    def __init__(self) -> None:
        self._docs = [
            KnowledgeDocument(
                concept_id="c1", name="Alpha", subject="physics", chapter="Ch1",
                definition_texts=["Alpha denotes the leading idea."],
                example_texts=["Compute alpha carefully."], prerequisites=["Beta"]),
            KnowledgeDocument(
                concept_id="c2", name="Beta", subject="physics", chapter="Ch1",
                definition_texts=["Beta supports alpha."]),
        ]

    def search(self, query, top_k=5, context=None):
        results = [SearchResult(score=float(2 - i), document=d)
                   for i, d in enumerate(self._docs)]
        if context is not None:
            results = [r for r in results if context.matches(r.document)]
        return results[:top_k]

    def metadata(self):
        return StrategyMetadata(name="fake", kind="lexical", deterministic=True)


class _FailVerifier:
    """Wraps the real verifier but forces a failing verdict (to exercise fail handling)."""

    def verify(self, tutor_plan, generation_plan, rendered):
        report = ResponseVerificationEngine().verify(tutor_plan, generation_plan, rendered)
        return report.model_copy(update={"passed": False})


def _profile() -> StudentProfile:
    return StudentProfile(
        state=StudentState(concept_mastery={"c1": 0.1}),
        preferences=StudentPreferences(difficulty=DifficultyPreference.EASY))


def _engine(strict: bool = False, verifier=None) -> EducationalTutorEngine:
    config = OrchestratorConfig(
        use_repository=False, top_k=5, style_preset="default", strict_verification=strict)
    return EducationalTutorEngine(
        config, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
        verification_engine=verifier)


class OrchestratorEvaluationEngine:
    def evaluate(self) -> OrchestratorEvalReport:
        report = OrchestratorEvalReport(
            deterministic=self._check_deterministic(),
            stage_ordering=self._check_stage_ordering(),
            metadata_propagation=self._check_metadata(),
            verify_fail_handling=self._check_verify_fail(),
            citation_preservation=self._check_citations(),
            config_propagation=self._check_config(),
            no_mutation=self._check_no_mutation(),
        )
        report.all_passed = all([
            report.deterministic, report.stage_ordering, report.metadata_propagation,
            report.verify_fail_handling, report.citation_preservation,
            report.config_propagation, report.no_mutation])
        return report

    def _check_deterministic(self) -> bool:
        a = _engine().answer("what is alpha", _profile())
        b = _engine().answer("what is alpha", _profile())
        return a.deterministic_fingerprint() == b.deterministic_fingerprint()

    def _check_stage_ordering(self) -> bool:
        resp = _engine().answer("what is alpha", _profile())
        names = resp.execution_trace.stage_names()
        statuses = {s.status.value for s in resp.execution_trace.stages}
        return names == STAGES and statuses == {"success"}

    def _check_metadata(self) -> bool:
        resp = _engine().answer("what is alpha", _profile())
        rm, em = resp.retrieval_metadata, resp.execution_metadata
        return (rm.n_results == 2 and rm.top_k == 5 and rm.strategy_name == "fake"
                and em.provider == "echo" and em.intent == resp.tutor_plan.intent.value)

    def _check_verify_fail(self) -> bool:
        # Default: returns with passed=False (no raise).
        resp = _engine(verifier=_FailVerifier()).answer("what is alpha", _profile())
        default_ok = resp.passed is False and resp.verification_report.passed is False
        # Strict: raises VerificationFailedError carrying the response.
        raised = False
        try:
            _engine(strict=True, verifier=_FailVerifier()).answer("what is alpha", _profile())
        except VerificationFailedError as exc:
            raised = isinstance(exc.response, type(resp))
        return default_ok and raised

    def _check_citations(self) -> bool:
        resp = _engine().answer("what is alpha", _profile())
        return (list(resp.citations) == list(resp.tutor_plan.references)
                == list(resp.rendered_response.references))

    def _check_config(self) -> bool:
        config = OrchestratorConfig(use_repository=False, top_k=3, style_preset="concise")
        engine = EducationalTutorEngine(
            config, strategy=FakeStrategy(), language_model=EchoLanguageModel())
        resp = engine.answer("what is alpha", _profile())
        return (resp.retrieval_metadata.top_k == 3
                and resp.execution_metadata.style_preset == "concise")

    def _check_no_mutation(self) -> bool:
        profile = _profile()
        before = profile.model_dump_json()
        _engine().answer("what is alpha", profile)
        return profile.model_dump_json() == before


def _print_summary(report: OrchestratorEvalReport) -> None:
    print("\n=== Orchestrator eval (architectural correctness) ===")
    for field in ("deterministic", "stage_ordering", "metadata_propagation",
                  "verify_fail_handling", "citation_preservation", "config_propagation",
                  "no_mutation"):
        print(f"  {field:<22} {getattr(report, field)}")
    print(f"  {'ALL PASSED':<22} {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Educational Tutor Orchestrator")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    report = OrchestratorEvaluationEngine().evaluate()
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
