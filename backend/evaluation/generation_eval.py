"""Deterministic evaluation of the Language Generation Layer — architectural correctness.

Offline (Echo model). Verifies the renderer honors its contract:
  * prompt determinism (byte-identical PromptDocuments across runs),
  * section order preserved (== TutorPlan slot order) and unit_ids stable,
  * no added concepts (all prompt citation ids ⊆ TutorPlan citation ids),
  * citation preservation (per-section + response references),
  * grounding (Echo output uses only the unit's content lines),
  * response determinism,
  * template purity (no educational vocabulary in style/system templates),
  * provider-neutral adapter equivalence (every adapter is a pure function of the doc).
No language-quality metrics.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

from backend.evaluation.generation_models import (
    CaseResult,
    GenerationCase,
    GenerationEvalReport,
)
from backend.generation.adapters import ADAPTERS
from backend.generation.language_model import EchoLanguageModel
from backend.generation.models import GenerationConfig
from backend.generation.plan_builder import build_generation_plan
from backend.generation.prompt_builder import PromptBuilder
from backend.generation.renderer import Renderer
from backend.generation.style import STYLE_PRESETS
from backend.tutor.models import (
    Citation,
    EducationalIntent,
    PlanSection,
    SectionKind,
    SectionStatus,
    TeachingStrategyKind,
    TutorPlan,
)

# A small controlled vocabulary of educational terms that must NEVER appear in a template.
_FORBIDDEN_TEMPLATE_TERMS = {
    "electric", "charge", "matrix", "matrices", "osmosis", "coulomb", "dipole",
    "function", "solution", "physics", "chemistry", "mathematics", "molecule",
    "force", "energy", "theorem", "integral", "derivative",
}
_WORD_RE = re.compile(r"[a-z]+")


def _section(kind: SectionKind, items, cids, status=SectionStatus.PRESENT) -> PlanSection:
    return PlanSection(
        kind=kind, status=status, items=list(items),
        citations=[Citation(concept_id=c, concept_name=c.upper(),
                            source_field="definition_texts", locator="0") for c in cids])


def _empty(kind: SectionKind) -> PlanSection:
    return PlanSection(kind=kind, status=SectionStatus.EMPTY)


def synthetic_plan() -> TutorPlan:
    """A fixed synthetic TutorPlan exercising several populated + empty sections."""
    refs = [
        Citation(concept_id="c1", concept_name="C1", source_field="definition_texts", locator="0"),
        Citation(concept_id="c2", concept_name="C2", source_field="prerequisites", locator="0"),
    ]
    return TutorPlan(
        query="What is c1?",
        intent=EducationalIntent.DEFINITION,
        strategy=TeachingStrategyKind.CONCEPT_EXPLANATION,
        primary_concept_id="c1", primary_concept_name="C1",
        prerequisites=_section(SectionKind.PREREQUISITES, ["C2"], ["c2"]),
        main_explanation=_section(SectionKind.MAIN_EXPLANATION, ["C1 is the first thing."], ["c1"]),
        formula=_empty(SectionKind.FORMULA),
        worked_example=_section(SectionKind.WORKED_EXAMPLE, ["Step one.", "Step two."], ["c1"]),
        proof=_empty(SectionKind.PROOF),
        exercise=_empty(SectionKind.EXERCISE),
        comparison=_empty(SectionKind.COMPARISON),
        related_concepts=_empty(SectionKind.RELATED_CONCEPTS),
        suggested_next_topics=_empty(SectionKind.NEXT_TOPICS),
        summary=_section(SectionKind.SUMMARY, ["C1 recap."], ["c1"]),
        references=refs,
    )


def default_cases() -> list[GenerationCase]:
    return [
        GenerationCase(
            name="definition_plan",
            tutor_plan=synthetic_plan(),
            expected_unit_kinds=["prerequisites", "main_explanation", "worked_example", "summary"],
        ),
    ]


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def check_template_purity() -> bool:
    """No style directive or system template may contain educational vocabulary."""
    corpus: list[str] = []
    for preset in STYLE_PRESETS.values():
        for directive in preset.values():
            corpus.extend([directive.tone, directive.format])
    # Also scan a built system prompt (contract + style framing).
    plan = build_generation_plan(synthetic_plan())
    builder = PromptBuilder()
    for unit in plan.units:
        doc = builder.build(unit, plan, GenerationConfig())
        corpus.append(doc.system)
    words: set[str] = set()
    for text in corpus:
        words |= _tokens(text)
    return not (words & _FORBIDDEN_TEMPLATE_TERMS)


def check_adapter_equivalence() -> bool:
    """Every adapter is a deterministic pure function of the same PromptDocument."""
    plan = build_generation_plan(synthetic_plan())
    doc = PromptBuilder().build(plan.units[0], plan, GenerationConfig())
    for adapter_cls in ADAPTERS.values():
        adapter = adapter_cls()
        r1 = adapter.to_request(doc, GenerationConfig())
        r2 = adapter.to_request(doc, GenerationConfig())
        if r1 != r2:
            return False
    return True


class GenerationEvaluationEngine:
    def __init__(self) -> None:
        self._renderer = Renderer()
        self._builder = PromptBuilder()

    def evaluate(self, cases: list[GenerationCase]) -> GenerationEvalReport:
        results = [self._evaluate_case(c) for c in cases]
        n = len(results) or 1

        def rate(attr: str) -> float:
            return round(sum(1 for r in results if getattr(r, attr)) / n, 6)

        report = GenerationEvalReport(
            n_cases=len(results),
            prompt_determinism_rate=rate("prompt_deterministic"),
            order_preserved_rate=rate("order_preserved"),
            unit_id_stability_rate=rate("unit_ids_stable"),
            no_added_concepts_rate=rate("no_added_concepts"),
            citation_preservation_rate=rate("citations_preserved"),
            grounding_rate=rate("grounded"),
            response_determinism_rate=rate("response_deterministic"),
            template_purity_ok=check_template_purity(),
            adapter_equivalence_ok=check_adapter_equivalence(),
            case_results=results,
        )
        report.all_passed = (
            all(getattr(report, f"{m}_rate") == 1.0 for m in (
                "prompt_determinism", "order_preserved", "unit_id_stability",
                "no_added_concepts", "citation_preservation", "grounding",
                "response_determinism"))
            and report.template_purity_ok and report.adapter_equivalence_ok
        )
        return report

    def _evaluate_case(self, case: GenerationCase) -> CaseResult:
        plan = case.tutor_plan
        config = GenerationConfig()

        docs_a = self._renderer.build_prompt_documents(plan, config)
        docs_b = self._renderer.build_prompt_documents(plan, config)
        prompt_deterministic = (
            [d.model_dump_json() for d in docs_a] == [d.model_dump_json() for d in docs_b])

        unit_kinds = [d.unit_kind.value for d in docs_a]
        order_preserved = unit_kinds == case.expected_unit_kinds
        unit_ids_stable = (
            [d.unit_id for d in docs_a] == [d.unit_id for d in docs_b]
            and len(set(d.unit_id for d in docs_a)) == len(docs_a))

        plan_cids = {c.concept_id for c in plan.references if c.concept_id}
        prompt_cids = {c.concept_id for d in docs_a for c in d.citations if c.concept_id}
        no_added = prompt_cids.issubset(plan_cids)

        model = EchoLanguageModel()
        r1 = self._renderer.render(plan, config, model)
        r2 = self._renderer.render(plan, config, model)
        response_deterministic = r1.model_dump_json() == r2.model_dump_json()
        # Citation isn't hashable (frozen model); compare in order.
        citations_preserved = (
            list(r1.references) == list(plan.references)
            and all(list(sec.citations) == list(_source_citations(plan, sec.unit_kind))
                    for sec in r1.sections))
        grounded = all(self._is_grounded(sec, docs_a) for sec in r1.sections)

        return CaseResult(
            name=case.name, prompt_deterministic=prompt_deterministic,
            order_preserved=order_preserved, unit_ids_stable=unit_ids_stable,
            no_added_concepts=no_added, citations_preserved=citations_preserved,
            grounded=grounded, response_deterministic=response_deterministic)

    def _is_grounded(self, section, docs) -> bool:
        doc = next((d for d in docs if d.unit_id == section.unit_id), None)
        if doc is None:
            return False
        content = next((b for b in doc.blocks if b.label == "Content"), None)
        allowed = _tokens(" ".join(content.lines)) if content else set()
        allowed |= _tokens(section.unit_kind.value)  # the heading is a section label
        return _tokens(section.text).issubset(allowed)


def _source_citations(plan: TutorPlan, kind: SectionKind):
    for field in ("prerequisites", "main_explanation", "formula", "worked_example", "proof",
                  "exercise", "comparison", "related_concepts", "suggested_next_topics", "summary"):
        section = getattr(plan, field)
        if section.kind == kind:
            return list(section.citations)
    return []


def _print_summary(report: GenerationEvalReport) -> None:
    print("\n=== Language Generation eval (architectural correctness) ===")
    print(f"  cases                    {report.n_cases}")
    print(f"  prompt determinism       {report.prompt_determinism_rate:.3f}")
    print(f"  section order preserved  {report.order_preserved_rate:.3f}")
    print(f"  unit_id stability        {report.unit_id_stability_rate:.3f}")
    print(f"  no added concepts        {report.no_added_concepts_rate:.3f}")
    print(f"  citation preservation    {report.citation_preservation_rate:.3f}")
    print(f"  grounding (echo)         {report.grounding_rate:.3f}")
    print(f"  response determinism     {report.response_determinism_rate:.3f}")
    print(f"  template purity          {report.template_purity_ok}")
    print(f"  adapter equivalence      {report.adapter_equivalence_ok}")
    print(f"  ALL PASSED               {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Language Generation Layer")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    report = GenerationEvaluationEngine().evaluate(default_cases())
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
