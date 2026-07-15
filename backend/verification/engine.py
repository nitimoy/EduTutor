"""The Response Verification Engine.

Runs the six deterministic verifiers over a ``RenderedResponse`` and assembles a single
explainable ``VerificationReport``. Never modifies text, never retrieves, never infers.
The source of truth is the ``TutorPlan`` (and its derived ``LanguageGenerationPlan``); the
engine only checks that the rendered response faithfully represents them.
"""

from __future__ import annotations

from typing import Optional

from backend.generation.models import LanguageGenerationPlan, RenderedResponse
from backend.tutor.models import TutorPlan
from backend.verification.config import VerificationConfig
from backend.verification.models import (
    Severity,
    VerificationIssue,
    VerificationMetrics,
    VerificationReport,
    VerificationResult,
    severity_rank,
)
from backend.verification.verifiers import (
    CitationVerifier,
    CompletenessVerifier,
    GroundingVerifier,
    ProviderInvariantVerifier,
    RendererContractVerifier,
    SectionCoverageVerifier,
    VerificationContext,
)


class ResponseVerificationEngine:
    """Deterministically verify a RenderedResponse against its TutorPlan."""

    def __init__(self, config: Optional[VerificationConfig] = None) -> None:
        self._config = config or VerificationConfig()

    def verify(
        self,
        tutor_plan: TutorPlan,
        generation_plan: LanguageGenerationPlan,
        rendered_response: RenderedResponse,
        config: Optional[VerificationConfig] = None,
    ) -> VerificationReport:
        cfg = config or self._config
        ctx = VerificationContext(tutor_plan, generation_plan, rendered_response)

        coverage, r_cov = SectionCoverageVerifier().verify(ctx)
        citations, r_cit = CitationVerifier().verify(ctx)
        grounding, r_gnd = GroundingVerifier().verify(ctx)
        completeness, r_cmp = CompletenessVerifier().verify(ctx)
        contract, r_con = RendererContractVerifier().verify(ctx)
        provider, r_prv = ProviderInvariantVerifier().verify(ctx)

        results = (r_cov, r_cit, r_gnd, r_cmp, r_con, r_prv)

        # Merge issues, sorted deterministically by (severity, code, unit_id).
        all_issues = tuple(sorted(
            (i for r in results for i in r.issues),
            key=lambda i: (severity_rank(i.severity), i.code, i.unit_id or "")))

        metrics = VerificationMetrics(
            coverage=coverage.coverage_pct,
            citation_accuracy=citations.citation_accuracy,
            section_preservation=1.0 if contract.passed else 0.0,
            grounding_completeness=grounding.grounding_completeness,
            unsupported_additions=grounding.unsupported_additions,
            missing_content=len(completeness.missing_lines),
            deterministic=True,
        )

        passed = self._verdict(cfg, results, grounding, completeness, all_issues)

        return VerificationReport(
            coverage=coverage, citations=citations, grounding=grounding,
            completeness=completeness, contract=contract, provider=provider,
            metrics=metrics, results=results, issues=all_issues, passed=passed,
            deterministic=True)

    def _verdict(
        self, cfg: VerificationConfig, results, grounding, completeness, issues
    ) -> bool:
        """Deterministic overall pass/fail per config."""
        has_error = any(i.severity == Severity.ERROR for i in issues)
        has_warning = any(i.severity == Severity.WARNING for i in issues)
        thresholds_ok = (
            grounding.grounding_completeness >= cfg.min_grounding_coverage
            and completeness.coverage_pct >= cfg.min_completeness)
        if has_error or not thresholds_ok:
            return False
        if cfg.fail_on_warning and has_warning:
            return False
        return True
