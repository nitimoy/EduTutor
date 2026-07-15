"""Response Verification Layer — deterministic grounding/faithfulness checks (Phase 6.1).

Analyzes whether a ``RenderedResponse`` faithfully represents its ``TutorPlan`` /
``LanguageGenerationPlan``. **Never modifies text**: no LLM, no retrieval, no rewriting.
Produces an explainable, reproducible ``VerificationReport`` (section coverage, citation
preservation, content-word grounding, completeness, renderer contract, provider invariants).
"""

from backend.verification.config import VerificationConfig
from backend.verification.engine import ResponseVerificationEngine
from backend.verification.models import (
    CitationReport,
    CompletenessReport,
    ContractReport,
    CoverageReport,
    GroundingReport,
    ProviderInvariantReport,
    SectionGrounding,
    Severity,
    VerificationIssue,
    VerificationMetrics,
    VerificationReport,
    VerificationResult,
)
from backend.verification.tokenizer import content_word_set, content_words
from backend.verification.verifiers import (
    CitationVerifier,
    CompletenessVerifier,
    GroundingVerifier,
    ProviderInvariantVerifier,
    RendererContractVerifier,
    SectionCoverageVerifier,
    VerificationContext,
    Verifier,
    citation_key,
)

# Alias requested by the brief ("VerificationEngine").
VerificationEngine = ResponseVerificationEngine

__all__ = [
    "ResponseVerificationEngine",
    "VerificationEngine",
    "VerificationConfig",
    # reports
    "VerificationReport",
    "VerificationResult",
    "VerificationMetrics",
    "VerificationIssue",
    "Severity",
    "CoverageReport",
    "CitationReport",
    "GroundingReport",
    "SectionGrounding",
    "CompletenessReport",
    "ContractReport",
    "ProviderInvariantReport",
    # verifiers
    "Verifier",
    "VerificationContext",
    "SectionCoverageVerifier",
    "CitationVerifier",
    "GroundingVerifier",
    "CompletenessVerifier",
    "RendererContractVerifier",
    "ProviderInvariantVerifier",
    "citation_key",
    # tokenizer
    "content_words",
    "content_word_set",
]
