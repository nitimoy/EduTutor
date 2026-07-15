"""Tests for the six deterministic verifiers (via VerificationContext)."""

from backend.evaluation.verification_eval import _faithful
from backend.generation.models import GenerationConfig
from backend.tutor.models import Citation, SectionKind
from backend.verification.verifiers import (
    CitationVerifier,
    CompletenessVerifier,
    GroundingVerifier,
    ProviderInvariantVerifier,
    RendererContractVerifier,
    SectionCoverageVerifier,
    VerificationContext,
)


def _ctx(rendered=None):
    plan, gplan, faithful = _faithful()
    return VerificationContext(plan, gplan, rendered or faithful)


def _resections(rendered, sections):
    return rendered.model_copy(update={"sections": tuple(sections)})


# ---------------------------------------------------------------- coverage
def test_coverage_faithful_passes():
    report, result = SectionCoverageVerifier().verify(_ctx())
    assert result.passed and report.coverage_pct == 1.0


def test_coverage_detects_missing_section():
    plan, gplan, r = _faithful()
    ctx = VerificationContext(plan, gplan, _resections(r, r.sections[1:]))
    report, result = SectionCoverageVerifier().verify(ctx)
    assert not result.passed
    assert any(i.code == "SECTION_MISSING" for i in result.issues)


def test_coverage_detects_reorder():
    plan, gplan, r = _faithful()
    secs = list(r.sections); secs[0], secs[1] = secs[1], secs[0]
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = SectionCoverageVerifier().verify(ctx)
    assert any(i.code == "ORDER_CHANGED" for i in result.issues)


# ---------------------------------------------------------------- citation
def test_citation_faithful_passes():
    report, result = CitationVerifier().verify(_ctx())
    assert result.passed and report.citation_accuracy == 1.0


def test_citation_detects_extra():
    plan, gplan, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={
        "citations": secs[1].citations + (Citation(concept_id="cX", concept_name="G",
                                                    source_field="definition_texts", locator="0"),)})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = CitationVerifier().verify(ctx)
    assert any(i.code == "CITATION_EXTRA" for i in result.issues)


def test_citation_detects_missing():
    plan, gplan, r = _faithful()
    secs = list(r.sections); secs[1] = secs[1].model_copy(update={"citations": ()})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = CitationVerifier().verify(ctx)
    assert any(i.code == "CITATION_MISSING" for i in result.issues)


# ---------------------------------------------------------------- grounding
def test_grounding_faithful_passes():
    report, result = GroundingVerifier().verify(_ctx())
    assert result.passed and report.grounding_completeness == 1.0


def test_grounding_allows_connective_rephrasing():
    # Adding only stop/function words must NOT flag anything.
    plan, gplan, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={"text": "Therefore the " + secs[1].text + " here."})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = GroundingVerifier().verify(ctx)
    assert result.passed  # 'therefore'/'the'/'here' are function words -> not content


def test_grounding_flags_new_content_word():
    plan, gplan, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={"text": secs[1].text + " neutrino"})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = GroundingVerifier().verify(ctx)
    assert any(i.code == "UNSUPPORTED_TERM" and i.detail.get("term") == "neutrino"
               for i in result.issues)


# ---------------------------------------------------------------- completeness
def test_completeness_faithful_passes():
    report, result = CompletenessVerifier().verify(_ctx())
    assert result.passed and report.coverage_pct == 1.0


def test_completeness_detects_missing_line():
    plan, gplan, r = _faithful()
    secs = list(r.sections)
    idx = next(i for i, s in enumerate(secs) if s.unit_kind == SectionKind.WORKED_EXAMPLE)
    secs[idx] = secs[idx].model_copy(update={"text": "Worked Example: Compute alpha carefully."})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = CompletenessVerifier().verify(ctx)
    assert any(i.code == "CONTENT_MISSING" for i in result.issues)


# ---------------------------------------------------------------- contract
def test_contract_faithful_passes():
    _, result = RendererContractVerifier().verify(_ctx())
    assert result.passed


def test_contract_detects_empty_section():
    plan, gplan, r = _faithful()
    secs = list(r.sections); secs[0] = secs[0].model_copy(update={"text": "   "})
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = RendererContractVerifier().verify(ctx)
    assert any(i.code == "CONTRACT_EMPTY_SECTION" for i in result.issues)


# ---------------------------------------------------------------- provider invariants
def test_provider_invariant_faithful_passes():
    _, result = ProviderInvariantVerifier().verify(_ctx())
    assert result.passed


def test_provider_invariant_detects_unit_id_change():
    plan, gplan, r = _faithful()
    secs = list(r.sections); secs[0], secs[1] = secs[1], secs[0]
    ctx = VerificationContext(plan, gplan, _resections(r, secs))
    _, result = ProviderInvariantVerifier().verify(ctx)
    assert any(i.code == "INVARIANT_UNIT_ID" for i in result.issues)
