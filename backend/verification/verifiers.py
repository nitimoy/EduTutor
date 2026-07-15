"""The six deterministic verifiers + the context they share.

Each verifier is a pure function of a :class:`VerificationContext` (precomputed views of
the frozen ``TutorPlan`` / ``LanguageGenerationPlan`` / ``RenderedResponse``). No verifier
modifies text, retrieves, or infers meaning — every check is deterministic set/sequence
comparison. Citations are compared as normalized ordered tuples because the frozen
``Citation`` model is not hashable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.generation.models import LanguageGenerationPlan, RenderedResponse
from backend.tutor.models import Citation, SectionStatus, TutorPlan
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
    VerificationResult,
)
from backend.verification.tokenizer import content_word_set, content_words

# Canonical TutorPlan slot order (matches the field order in TutorPlan).
# grounded_facts comes first because it's prepended during composition.
_SLOT_ORDER: tuple[str, ...] = (
    "grounded_facts", "prerequisites", "main_explanation", "formula", "worked_example", "proof",
    "exercise", "comparison", "related_concepts", "suggested_next_topics", "summary",
)


def citation_key(citation: Citation) -> tuple:
    """A hashable, order-preserving identity for a (non-hashable) Citation."""
    return (
        citation.concept_id, citation.concept_name, citation.source_field,
        citation.locator, citation.object_type,
    )


def _heading_words(kind_value: str) -> frozenset[str]:
    """Words in a section-kind heading the Echo renderer may prepend (e.g. 'worked example')."""
    words = list(content_words(kind_value.replace("_", " ")))
    if kind_value == "comparison":
        words.extend(["aspect", "definition", "properties", "key", "difference"])
    elif kind_value == "grounded_facts":
        words.extend(["disclaimer", "important"])
    return frozenset(words)


class VerificationContext:
    """Precomputed, read-only views the verifiers operate on."""

    def __init__(
        self,
        tutor_plan: TutorPlan,
        generation_plan: LanguageGenerationPlan,
        rendered: RenderedResponse,
    ) -> None:
        self.tutor_plan = tutor_plan
        self.generation_plan = generation_plan
        self.rendered = rendered

        # TutorPlan sections that should have rendered, in slot order.
        # A section is expected if it's PRESENT and has either items or a note
        # (grounded_facts uses only a note for its disclaimer text).
        self.expected_kinds: tuple[str, ...] = tuple(
            getattr(tutor_plan, field).kind.value
            for field in _SLOT_ORDER
            if getattr(tutor_plan, field).status == SectionStatus.PRESENT
            and (getattr(tutor_plan, field).items or getattr(tutor_plan, field).note)
        )
        self.plan_units = {u.unit_id: u for u in generation_plan.units}
        self.plan_unit_order: tuple[str, ...] = tuple(u.unit_id for u in generation_plan.units)
        self.rendered_sections = list(rendered.sections)
        self.rendered_unit_order: tuple[str, ...] = tuple(
            s.unit_id for s in rendered.sections)


class Verifier(ABC):
    name: str = ""

    @abstractmethod
    def verify(self, ctx: VerificationContext):
        """Run this verifier; return its sub-report and a VerificationResult."""


class SectionCoverageVerifier(Verifier):
    name = "section_coverage"

    def verify(self, ctx: VerificationContext) -> tuple[CoverageReport, VerificationResult]:
        rendered_kinds = tuple(s.unit_kind.value for s in ctx.rendered_sections)
        expected = ctx.expected_kinds
        expected_set, rendered_list = set(expected), list(rendered_kinds)

        missing = tuple(k for k in expected if k not in rendered_kinds)
        extra = tuple(k for k in rendered_kinds if k not in expected_set)
        seen: set[str] = set()
        duplicated = tuple(
            k for k in rendered_kinds if k in seen or seen.add(k))  # type: ignore[func-returns-value]
        # Order preserved iff the rendered kinds (that are expected) follow slot order.
        rendered_expected_seq = [k for k in rendered_kinds if k in expected_set]
        order_preserved = rendered_expected_seq == [k for k in expected if k in rendered_list]

        coverage_pct = round(
            (len(expected) - len(missing)) / len(expected), 6) if expected else 1.0
        passed = not missing and not extra and not duplicated and order_preserved

        issues: list[VerificationIssue] = []
        for k in missing:
            issues.append(VerificationIssue(
                code="SECTION_MISSING", severity=Severity.ERROR,
                message=f"present TutorPlan section '{k}' was not rendered", unit_id=None,
                detail={"kind": k}))
        for k in extra:
            issues.append(VerificationIssue(
                code="SECTION_EXTRA", severity=Severity.ERROR,
                message=f"rendered section '{k}' has no present TutorPlan source",
                detail={"kind": k}))
        for k in duplicated:
            issues.append(VerificationIssue(
                code="SECTION_DUPLICATED", severity=Severity.ERROR,
                message=f"section '{k}' rendered more than once", detail={"kind": k}))
        if not order_preserved:
            issues.append(VerificationIssue(
                code="ORDER_CHANGED", severity=Severity.ERROR,
                message="rendered section order differs from TutorPlan slot order"))

        report = CoverageReport(
            expected_kinds=expected, rendered_kinds=rendered_kinds, missing=missing,
            extra=extra, duplicated=duplicated, order_preserved=order_preserved,
            coverage_pct=coverage_pct, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))


class CitationVerifier(Verifier):
    name = "citation"

    def verify(self, ctx: VerificationContext) -> tuple[CitationReport, VerificationResult]:
        issues: list[VerificationIssue] = []
        expected_total = 0
        preserved_total = 0
        missing: list[str] = []
        extra: list[str] = []
        reordered: list[str] = []

        for section in ctx.rendered_sections:
            unit = ctx.plan_units.get(section.unit_id)
            if unit is None:
                continue  # coverage verifier handles orphan sections
            src = [citation_key(c) for c in unit.citations]
            got = [citation_key(c) for c in section.citations]
            expected_total += len(src)
            preserved_total += sum(1 for k in got if k in src)
            for k in src:
                if k not in got:
                    missing.append(section.unit_id)
                    issues.append(VerificationIssue(
                        code="CITATION_MISSING", severity=Severity.ERROR,
                        message=f"citation dropped in section '{section.unit_kind.value}'",
                        unit_id=section.unit_id, detail={"concept_id": str(k[0])}))
            for k in got:
                if k not in src:
                    extra.append(section.unit_id)
                    issues.append(VerificationIssue(
                        code="CITATION_EXTRA", severity=Severity.ERROR,
                        message=f"citation added in section '{section.unit_kind.value}'",
                        unit_id=section.unit_id, detail={"concept_id": str(k[0])}))
            if src != got and sorted(map(str, src)) == sorted(map(str, got)):
                reordered.append(section.unit_id)
                issues.append(VerificationIssue(
                    code="CITATION_REORDERED", severity=Severity.WARNING,
                    message=f"citations reordered in section '{section.unit_kind.value}'",
                    unit_id=section.unit_id))

        refs_ok = (
            [citation_key(c) for c in ctx.rendered.references]
            == [citation_key(c) for c in ctx.tutor_plan.references])
        if not refs_ok:
            issues.append(VerificationIssue(
                code="REFERENCES_CHANGED", severity=Severity.ERROR,
                message="RenderedResponse.references differ from TutorPlan.references"))

        accuracy = round(preserved_total / expected_total, 6) if expected_total else 1.0
        passed = not missing and not extra and refs_ok
        report = CitationReport(
            expected=expected_total, preserved=preserved_total,
            missing=tuple(dict.fromkeys(missing)), extra=tuple(dict.fromkeys(extra)),
            reordered_units=tuple(dict.fromkeys(reordered)), references_preserved=refs_ok,
            citation_accuracy=accuracy, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))


class GroundingVerifier(Verifier):
    name = "grounding"

    def verify(self, ctx: VerificationContext) -> tuple[GroundingReport, VerificationResult]:
        issues: list[VerificationIssue] = []
        sections: list[SectionGrounding] = []
        total_unsupported = 0

        for section in ctx.rendered_sections:
            content_block = next(
                (b for b in section.prompt.blocks if b.label == "Content"), None)
            source_words = content_word_set(
                " ".join(content_block.lines) if content_block else "")
            query_words = content_word_set(ctx.generation_plan.query) if ctx.generation_plan.query else frozenset()
            allowed = source_words | _heading_words(section.unit_kind.value) | query_words
            # Strip citation markers like [Title] concept=concept.foo field=bar locator=0 from text before checking grounding
            import re
            cleaned_text = re.sub(r'\[.*?\] concept=.*? field=\S+ locator=\S+', '', section.text)
            rendered_words = content_words(cleaned_text)
            unsupported = tuple(dict.fromkeys(w for w in rendered_words if w not in allowed))
            supported = len(rendered_words) - sum(
                1 for w in rendered_words if w not in allowed)

            # Citations appearing in a section must belong to that unit.
            unit = ctx.plan_units.get(section.unit_id)
            unit_ids = {citation_key(c)[0] for c in (unit.citations if unit else ())}
            unsupported_cites = tuple(
                str(citation_key(c)[0]) for c in section.citations
                if citation_key(c)[0] not in unit_ids)

            grounded = not unsupported and not unsupported_cites
            total_unsupported += len(unsupported)
            cov = round(supported / len(rendered_words), 6) if rendered_words else 1.0

            for term in unsupported:
                issues.append(VerificationIssue(
                    code="UNSUPPORTED_TERM", severity=Severity.WARNING,
                    message=f"content word '{term}' not grounded in section "
                            f"'{section.unit_kind.value}'",
                    unit_id=section.unit_id, detail={"term": term}))
            for cid in unsupported_cites:
                issues.append(VerificationIssue(
                    code="UNSUPPORTED_CITATION", severity=Severity.ERROR,
                    message=f"citation '{cid}' not part of section "
                            f"'{section.unit_kind.value}'",
                    unit_id=section.unit_id, detail={"concept_id": cid}))

            sections.append(SectionGrounding(
                unit_id=section.unit_id, kind=section.unit_kind.value,
                source_terms=len(source_words), rendered_terms=len(rendered_words),
                supported_terms=supported, unsupported_terms=unsupported,
                unsupported_citations=unsupported_cites, coverage_pct=cov, grounded=grounded))

        grounded_count = sum(1 for s in sections if s.grounded)
        completeness = round(grounded_count / len(sections), 6) if sections else 1.0
        passed = all(s.grounded for s in sections)
        report = GroundingReport(
            sections=tuple(sections), unsupported_additions=total_unsupported,
            grounding_completeness=completeness, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))


class CompletenessVerifier(Verifier):
    name = "completeness"

    def verify(self, ctx: VerificationContext) -> tuple[CompletenessReport, VerificationResult]:
        issues: list[VerificationIssue] = []
        covered = 0
        total = 0
        missing_lines: list[str] = []

        for section in ctx.rendered_sections:
            content_block = next(
                (b for b in section.prompt.blocks if b.label == "Content"), None)
            if content_block is None:
                continue
            rendered_words = content_word_set(section.text)
            for line in content_block.lines:
                total += 1
                line_words = content_word_set(line)
                # A content line is "covered" if at least one of its content words appears in the render
                # (supporting pedagogical rephrasing) or if it has no content words to begin with.
                if (not line_words) or not line_words.isdisjoint(rendered_words):
                    covered += 1
                else:
                    missing_lines.append(line)
                    issues.append(VerificationIssue(
                        code="CONTENT_MISSING", severity=Severity.ERROR,
                        message=f"content line not represented in section "
                                f"'{section.unit_kind.value}'",
                        unit_id=section.unit_id, detail={"line": line}))

        coverage_pct = round(covered / total, 6) if total else 1.0
        passed = not missing_lines
        report = CompletenessReport(
            covered_lines=covered, missing_lines=tuple(missing_lines), extra_lines=(),
            total_lines=total, coverage_pct=coverage_pct, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))


class RendererContractVerifier(Verifier):
    name = "contract"

    def verify(self, ctx: VerificationContext) -> tuple[ContractReport, VerificationResult]:
        issues: list[VerificationIssue] = []
        rendered_kinds = [s.unit_kind.value for s in ctx.rendered_sections]
        expected_set = set(ctx.expected_kinds)

        no_new = all(k in expected_set for k in rendered_kinds)
        no_missing = all(k in rendered_kinds for k in ctx.expected_kinds)
        seen: set[str] = set()
        no_dupes = not any(k in seen or seen.add(k) for k in rendered_kinds)  # type: ignore[func-returns-value]
        rendered_expected = [k for k in rendered_kinds if k in expected_set]
        no_reordered = rendered_expected == list(ctx.expected_kinds)
        no_empty = all(s.text.strip() for s in ctx.rendered_sections)

        if not no_new:
            issues.append(VerificationIssue(code="CONTRACT_NEW_SECTION", severity=Severity.ERROR,
                message="a rendered section is not in the TutorPlan"))
        if not no_missing:
            issues.append(VerificationIssue(code="CONTRACT_MISSING_SECTION", severity=Severity.ERROR,
                message="a required TutorPlan section was not rendered"))
        if not no_dupes:
            issues.append(VerificationIssue(code="CONTRACT_DUPLICATE", severity=Severity.ERROR,
                message="a section was rendered more than once"))
        if not no_reordered:
            issues.append(VerificationIssue(code="CONTRACT_REORDERED", severity=Severity.ERROR,
                message="rendered sections are not in TutorPlan order"))
        if not no_empty:
            issues.append(VerificationIssue(code="CONTRACT_EMPTY_SECTION", severity=Severity.ERROR,
                message="a rendered section is empty"))

        passed = no_new and no_missing and no_dupes and no_reordered and no_empty
        report = ContractReport(
            no_new_sections=no_new, no_reordered=no_reordered, no_missing_required=no_missing,
            no_duplicates=no_dupes, no_empty_rendered=no_empty, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))


class ProviderInvariantVerifier(Verifier):
    name = "provider_invariant"

    def verify(self, ctx: VerificationContext) -> tuple[ProviderInvariantReport, VerificationResult]:
        issues: list[VerificationIssue] = []

        unit_id_ok = ctx.rendered_unit_order == ctx.plan_unit_order
        # Section identity: each rendered unit_id maps to the same kind as its plan unit.
        identity_ok = all(
            ctx.plan_units[s.unit_id].kind == s.unit_kind
            for s in ctx.rendered_sections if s.unit_id in ctx.plan_units)
        ordering_ok = unit_id_ok
        citations_ok = all(
            [citation_key(c) for c in ctx.plan_units[s.unit_id].citations]
            == [citation_key(c) for c in s.citations]
            for s in ctx.rendered_sections if s.unit_id in ctx.plan_units)

        if not unit_id_ok:
            issues.append(VerificationIssue(code="INVARIANT_UNIT_ID", severity=Severity.ERROR,
                message="unit_id sequence changed between plan and rendered response"))
        if not identity_ok:
            issues.append(VerificationIssue(code="INVARIANT_IDENTITY", severity=Severity.ERROR,
                message="a rendered section's kind differs from its plan unit"))
        if not citations_ok:
            issues.append(VerificationIssue(code="INVARIANT_CITATIONS", severity=Severity.ERROR,
                message="a provider changed a section's citations"))

        passed = unit_id_ok and identity_ok and ordering_ok and citations_ok
        report = ProviderInvariantReport(
            citations_unchanged=citations_ok, identity_unchanged=identity_ok,
            unit_id_unchanged=unit_id_ok, ordering_unchanged=ordering_ok, passed=passed)
        return report, VerificationResult(name=self.name, passed=passed, issues=tuple(issues))
