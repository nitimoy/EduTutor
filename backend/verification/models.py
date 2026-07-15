"""Report IRs for the Response Verification Layer.

All models are immutable data. The verifier never modifies generated text — it only
produces an explainable, deterministic ``VerificationReport`` describing whether a
``RenderedResponse`` faithfully represents its ``TutorPlan`` / ``LanguageGenerationPlan``.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# Deterministic ordering weight for severity sorting.
_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


def severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANK[severity]


class VerificationIssue(BaseModel):
    """One explainable finding with a stable machine-readable ``code``."""

    model_config = ConfigDict(frozen=True)

    code: str
    severity: Severity
    message: str
    unit_id: Optional[str] = None
    detail: dict[str, str] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """The outcome of a single verifier."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    issues: tuple[VerificationIssue, ...] = ()


class CoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_kinds: tuple[str, ...] = ()
    rendered_kinds: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    duplicated: tuple[str, ...] = ()
    order_preserved: bool = True
    coverage_pct: float = 1.0
    passed: bool = True


class CitationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected: int = 0
    preserved: int = 0
    missing: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()
    reordered_units: tuple[str, ...] = ()
    references_preserved: bool = True
    citation_accuracy: float = 1.0
    passed: bool = True


class SectionGrounding(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: str
    kind: str
    source_terms: int = 0
    rendered_terms: int = 0
    supported_terms: int = 0
    unsupported_terms: tuple[str, ...] = ()
    unsupported_citations: tuple[str, ...] = ()
    coverage_pct: float = 1.0
    grounded: bool = True


class GroundingReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    sections: tuple[SectionGrounding, ...] = ()
    unsupported_additions: int = 0
    grounding_completeness: float = 1.0
    passed: bool = True


class CompletenessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    covered_lines: int = 0
    missing_lines: tuple[str, ...] = ()
    extra_lines: tuple[str, ...] = ()
    total_lines: int = 0
    coverage_pct: float = 1.0
    passed: bool = True


class ContractReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    no_new_sections: bool = True
    no_reordered: bool = True
    no_missing_required: bool = True
    no_duplicates: bool = True
    no_empty_rendered: bool = True
    passed: bool = True


class ProviderInvariantReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    citations_unchanged: bool = True
    identity_unchanged: bool = True
    unit_id_unchanged: bool = True
    ordering_unchanged: bool = True
    passed: bool = True


class VerificationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    coverage: float = 1.0
    citation_accuracy: float = 1.0
    section_preservation: float = 1.0
    grounding_completeness: float = 1.0
    unsupported_additions: int = 0
    missing_content: int = 0
    deterministic: bool = True


class VerificationReport(BaseModel):
    """The complete, explainable verification result."""

    model_config = ConfigDict(frozen=True)

    coverage: CoverageReport
    citations: CitationReport
    grounding: GroundingReport
    completeness: CompletenessReport
    contract: ContractReport
    provider: ProviderInvariantReport
    metrics: VerificationMetrics
    results: tuple[VerificationResult, ...] = ()
    issues: tuple[VerificationIssue, ...] = ()
    passed: bool = True
    deterministic: bool = True
