"""Deterministic evaluation of the Response Verification Engine.

Builds a faithful RenderedResponse (via the frozen Renderer + Echo), then constructs
adversarially **tampered** variants (dropped section, extra/missing citation, reordered /
duplicated / new section, ungrounded term, missing content line) by copying the frozen
pydantic objects. For each case it runs the engine and checks the verdict + that the
expected issue codes are raised, plus report determinism. No LLM. Architectural correctness
only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.evaluation.verification_models import (
    CaseResult,
    VerificationEvalReport,
)
from backend.generation.language_model import EchoLanguageModel
from backend.generation.models import GenerationConfig, LanguageGenerationPlan, RenderedResponse
from backend.generation.plan_builder import build_generation_plan
from backend.generation.renderer import Renderer
from backend.tutor.models import (
    Citation,
    EducationalIntent,
    PlanSection,
    SectionKind,
    SectionStatus,
    TeachingStrategyKind,
    TutorPlan,
)
from backend.verification.engine import ResponseVerificationEngine


def _cit(cid: str, name: str) -> Citation:
    return Citation(concept_id=cid, concept_name=name, source_field="definition_texts", locator="0")


def _present(kind: SectionKind, items, cits) -> PlanSection:
    return PlanSection(kind=kind, status=SectionStatus.PRESENT, items=list(items),
                       citations=list(cits))


def _empty(kind: SectionKind) -> PlanSection:
    return PlanSection(kind=kind, status=SectionStatus.EMPTY)


def synthetic_plan() -> TutorPlan:
    """A synthetic TutorPlan whose lines have distinct content words (so tampering shows)."""
    return TutorPlan(
        query="What is alpha?",
        intent=EducationalIntent.DEFINITION,
        strategy=TeachingStrategyKind.CONCEPT_EXPLANATION,
        primary_concept_id="c1", primary_concept_name="Alpha",
        prerequisites=_present(SectionKind.PREREQUISITES, ["Vectors"], [_cit("c2", "Vectors")]),
        main_explanation=_present(SectionKind.MAIN_EXPLANATION,
                                  ["Alpha denotes the leading idea which forms the core of this entirely contrived testing scenario. We need enough words."], [_cit("c1", "Alpha")]),
        formula=_empty(SectionKind.FORMULA),
        worked_example=_present(SectionKind.WORKED_EXAMPLE,
                                ["Compute alpha carefully.", "Verify beta afterwards."],
                                [_cit("c1", "Alpha")]),
        proof=_empty(SectionKind.PROOF),
        exercise=_empty(SectionKind.EXERCISE),
        comparison=_empty(SectionKind.COMPARISON),
        related_concepts=_empty(SectionKind.RELATED_CONCEPTS),
        suggested_next_topics=_empty(SectionKind.NEXT_TOPICS),
        summary=_present(SectionKind.SUMMARY, ["Alpha summarises vectors."], [_cit("c1", "Alpha")]),
        references=[_cit("c1", "Alpha"), _cit("c2", "Vectors")],
    )


def _faithful() -> tuple[TutorPlan, LanguageGenerationPlan, RenderedResponse]:
    plan = synthetic_plan()
    gplan = build_generation_plan(plan)
    rendered = Renderer().render(plan, GenerationConfig(), EchoLanguageModel())
    return plan, gplan, rendered


@dataclass
class _Case:
    name: str
    tutor_plan: TutorPlan
    generation_plan: LanguageGenerationPlan
    rendered: RenderedResponse
    expected_pass: bool
    expected_codes: tuple[str, ...] = field(default_factory=tuple)


def _replace_sections(rendered: RenderedResponse, sections) -> RenderedResponse:
    return rendered.model_copy(update={"sections": tuple(sections)})


def default_cases() -> list[_Case]:
    cases: list[_Case] = []

    # 1. faithful
    p, g, r = _faithful()
    cases.append(_Case("faithful", p, g, r, expected_pass=True))

    # 2. dropped section
    p, g, r = _faithful()
    cases.append(_Case("dropped_section", p, g,
                       _replace_sections(r, r.sections[1:]), False, ("SECTION_MISSING",)))

    # 3. extra citation (add a foreign citation to the main_explanation section)
    p, g, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={
        "citations": secs[1].citations + (_cit("cX", "Ghost"),)})
    cases.append(_Case("extra_citation", p, g, _replace_sections(r, secs), False,
                       ("CITATION_EXTRA",)))

    # 4. missing citation (drop the section's only citation)
    p, g, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={"citations": ()})
    cases.append(_Case("missing_citation", p, g, _replace_sections(r, secs), False,
                       ("CITATION_MISSING",)))

    # 5. reordered sections
    p, g, r = _faithful()
    secs = list(r.sections)
    secs[0], secs[1] = secs[1], secs[0]
    cases.append(_Case("reordered_sections", p, g, _replace_sections(r, secs), False,
                       ("ORDER_CHANGED",)))

    # 6. duplicated section
    p, g, r = _faithful()
    cases.append(_Case("duplicated_section", p, g,
                       _replace_sections(r, r.sections + (r.sections[0],)), False,
                       ("SECTION_DUPLICATED",)))

    # 7. new (unexpected) section
    p, g, r = _faithful()
    ghost = r.sections[0].model_copy(update={
        "unit_id": "c1::formula", "unit_kind": SectionKind.FORMULA})
    cases.append(_Case("new_section", p, g,
                       _replace_sections(r, r.sections + (ghost,)), False, ("SECTION_EXTRA",)))

    # 8. ungrounded term injected
    p, g, r = _faithful()
    secs = list(r.sections)
    secs[1] = secs[1].model_copy(update={"text": secs[1].text + " quantumnucleus"})
    cases.append(_Case("ungrounded_term", p, g, _replace_sections(r, secs), False,
                       ("UNSUPPORTED_TERM",)))

    # 9. missing content line (drop the second worked-example line from the rendered text)
    p, g, r = _faithful()
    secs = list(r.sections)
    we_idx = next(i for i, s in enumerate(secs) if s.unit_kind == SectionKind.WORKED_EXAMPLE)
    secs[we_idx] = secs[we_idx].model_copy(update={"text": "Worked Example: Compute alpha carefully."})
    cases.append(_Case("missing_content_line", p, g, _replace_sections(r, secs), False,
                       ("CONTENT_MISSING",)))

    return cases


class VerificationEvaluationEngine:
    def __init__(self) -> None:
        self._engine = ResponseVerificationEngine()

    def evaluate(self, cases: list[_Case]) -> VerificationEvalReport:
        results = [self._evaluate_case(c) for c in cases]
        n = len(results) or 1

        def rate(attr: str) -> float:
            return round(sum(1 for r in results if getattr(r, attr)) / n, 6)

        report = VerificationEvalReport(
            n_cases=len(results),
            verdict_accuracy=rate("verdict_ok"),
            code_detection_rate=rate("codes_ok"),
            determinism_rate=rate("deterministic"),
            case_results=results,
        )
        report.all_passed = (
            report.verdict_accuracy == 1.0 and report.code_detection_rate == 1.0
            and report.determinism_rate == 1.0)
        return report

    def _evaluate_case(self, case: _Case) -> CaseResult:
        report = self._engine.verify(case.tutor_plan, case.generation_plan, case.rendered)
        report2 = self._engine.verify(case.tutor_plan, case.generation_plan, case.rendered)
        deterministic = report.model_dump_json() == report2.model_dump_json()

        verdict_ok = report.passed == case.expected_pass
        raised = {i.code for i in report.issues}
        codes_ok = all(code in raised for code in case.expected_codes)

        return CaseResult(name=case.name, verdict_ok=verdict_ok, codes_ok=codes_ok,
                          deterministic=deterministic)


def _print_summary(report: VerificationEvalReport) -> None:
    print("\n=== Response Verification eval (architectural correctness) ===")
    print(f"  cases               {report.n_cases}")
    print(f"  verdict accuracy    {report.verdict_accuracy:.3f}")
    print(f"  code detection      {report.code_detection_rate:.3f}")
    print(f"  determinism         {report.determinism_rate:.3f}")
    print(f"  ALL PASSED          {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Response Verification Engine")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    report = VerificationEvaluationEngine().evaluate(default_cases())
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
