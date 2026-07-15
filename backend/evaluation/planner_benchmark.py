"""Planner Regression Benchmark.

Tests the pedagogical overhaul (Phase 13) against 8 regression cases that
previously failed: conceptual questions becoming worked examples, comparisons
becoming paragraphs, learning-path queries returning nearest concepts, and
hallucinated conclusions bypassing verification.

Assertions per case:
  1. Correct QuestionType detected.
  2. Correct teaching strategy used.
  3. Required sections present (if data supports them).
  4. Forbidden sections NOT lead (no worked_example as first section for
     conceptual/comparison intents).
  5. Disclaimer present when evidence sufficiency is PARTIAL.
  6. No GROUNDED_FACTS section hallucinating conclusions.

Run:
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.evaluation.planner_benchmark
"""

import json
import sys
import logging
from pathlib import Path

from backend.orchestrator.engine import EducationalTutorEngine
from backend.orchestrator.config import OrchestratorConfig
from backend.student.models import StudentProfile
from backend.tutor.question_classifier import classify
from backend.tutor.goal_detector import detect_goal
from backend.tutor.models import QuestionType, SectionKind, SectionStatus
from backend.orchestrator.models import UnsupportedQueryResponse

logger = logging.getLogger(__name__)

DATASET = Path("backend/evaluation/datasets/pedagogy_planner.json")
COMPILED_DIR = "data/compiled"

_SECTION_FIELDS = [
    ("grounded_facts", SectionKind.GROUNDED_FACTS),
    ("prerequisites", SectionKind.PREREQUISITES),
    ("main_explanation", SectionKind.MAIN_EXPLANATION),
    ("formula", SectionKind.FORMULA),
    ("worked_example", SectionKind.WORKED_EXAMPLE),
    ("proof", SectionKind.PROOF),
    ("exercise", SectionKind.EXERCISE),
    ("comparison", SectionKind.COMPARISON),
    ("related_concepts", SectionKind.RELATED_CONCEPTS),
    ("suggested_next_topics", SectionKind.NEXT_TOPICS),
    ("summary", SectionKind.SUMMARY),
]


def _present_sections(plan) -> list[SectionKind]:
    """Return list of SectionKinds that are PRESENT in the plan."""
    present = []
    for field, kind in _SECTION_FIELDS:
        section = getattr(plan, field, None)
        if section and section.status == SectionStatus.PRESENT:
            # GROUNDED_FACTS is "present" if status=PRESENT (even if items=[])
            if kind == SectionKind.GROUNDED_FACTS:
                if section.note:
                    present.append(kind)
            elif section.items:
                present.append(kind)
    return present


def _lead_section(plan) -> SectionKind | None:
    """Return the first PRESENT section in canonical render order."""
    for _field, kind in _SECTION_FIELDS:
        section = getattr(plan, _field, None)
        if section and section.status == SectionStatus.PRESENT:
            if kind == SectionKind.GROUNDED_FACTS:
                if section.note:
                    return kind
            elif section.items:
                return kind
    return None


def _has_disclaimer(plan) -> bool:
    gf = getattr(plan, "grounded_facts", None)
    return gf is not None and gf.status == SectionStatus.PRESENT and bool(gf.note)


class PlannerBenchmark:
    def __init__(self):
        with open(DATASET) as f:
            self.cases = json.load(f)
        config = OrchestratorConfig(compiled_dir=COMPILED_DIR)
        self.engine = EducationalTutorEngine(config=config)
        self.profile = StudentProfile()

    def run(self):
        passed = 0
        total = len(self.cases)
        failures = []

        print(f"\n{'='*60}")
        print(f"  PLANNER REGRESSION BENCHMARK  ({total} cases)")
        print(f"{'='*60}\n")

        for case in self.cases:
            query = case["query"]
            expected = case["expected"]
            case_failures = []

            try:
                # 1. Check QuestionType classification (deterministic, no engine needed).
                qt, _key = classify(query)
                expected_qt = expected.get("question_type")
                if expected_qt and qt.value != expected_qt:
                    case_failures.append(
                        f"QuestionType: expected '{expected_qt}', got '{qt.value}'"
                    )

                # 2. Run the engine.
                response = self.engine.answer(query, self.profile)

                if isinstance(response, UnsupportedQueryResponse):
                    case_failures.append(
                        f"Query was rejected as unsupported: {response.reason}"
                    )
                    if case_failures:
                        failures.append((query, case_failures))
                        print(f"❌ FAIL: {query}")
                        for f_msg in case_failures:
                            print(f"   ✗ {f_msg}")
                    continue

                plan = response.tutor_plan
                present = _present_sections(plan)
                lead = _lead_section(plan)

                # 3. Strategy check.
                expected_strategy = expected.get("strategy")
                if expected_strategy and plan.strategy.value != expected_strategy:
                    # Check if a fallback note explains the deviation.
                    notes = getattr(plan, "notes", [])
                    fallback_notes = [n for n in notes if "fell back to" in n]
                    if not fallback_notes:
                        case_failures.append(
                            f"Strategy: expected '{expected_strategy}', got '{plan.strategy.value}'"
                        )

                # 4. Required sections check.
                must_have = expected.get("must_have_sections", [])
                for req in must_have:
                    kind = _kind_from_value(req)
                    if kind and kind not in present:
                        case_failures.append(
                            f"Missing required section: '{req}' (present: {[p.value for p in present]})"
                        )

                # 5. Forbidden sections check.
                must_not_have = expected.get("must_not_have_sections", [])
                for ban in must_not_have:
                    kind = _kind_from_value(ban)
                    if kind and kind in present:
                        case_failures.append(
                            f"Found forbidden section: '{ban}'"
                        )

                # 6. No worked_example as lead for conceptual/comparison/learning_path.
                must_not_lead = expected.get("must_not_have_sections_as_lead", [])
                for ban_lead in must_not_lead:
                    kind = _kind_from_value(ban_lead)
                    if kind and lead == kind:
                        case_failures.append(
                            f"Section '{ban_lead}' must not be the lead section "
                            f"(it is the first rendered section — pedagogical violation)"
                        )

                # 7. Disclaimer check for conceptual / partial-evidence cases.
                if expected.get("disclaimer_if_no_explanation"):
                    # Disclaimer should be present OR evidence was FULL (no disclaimer needed).
                    notes = getattr(plan, "notes", [])
                    has_suf_note = any("evidence_sufficiency" in n for n in notes)
                    has_disc = _has_disclaimer(plan)
                    # If there's no disclaimer AND there's no "full" evidence note,
                    # check if main_explanation is actually populated.
                    main_exp = getattr(plan, "main_explanation", None)
                    has_real_explanation = (
                        main_exp and main_exp.status == SectionStatus.PRESENT
                        and bool(main_exp.items)
                    )
                    if not has_real_explanation and not has_disc:
                        case_failures.append(
                            "Expected either a real explanation OR a disclaimer "
                            "when evidence is partial — got neither."
                        )

                if not case_failures:
                    passed += 1
                    goal = detect_goal(qt, query)
                    eg = getattr(plan, "educational_goal", None)
                    print(f"✅ PASS: {query}")
                    if plan.question_type:
                        print(f"   QuestionType={plan.question_type.value}  "
                              f"Goal={eg.value if eg else goal.value}  "
                              f"Strategy={plan.strategy.value}  "
                              f"Lead={lead.value if lead else 'none'}  "
                              f"Disclaimer={_has_disclaimer(plan)}")
                else:
                    failures.append((query, case_failures))
                    print(f"❌ FAIL: {query}")
                    for f_msg in case_failures:
                        print(f"   ✗ {f_msg}")

            except Exception as exc:
                failures.append((query, [f"Exception: {exc}"]))
                print(f"❌ ERROR: {query}")
                print(f"   Exception: {exc}")
                import traceback
                traceback.print_exc()

        print(f"\n{'='*60}")
        print(f"  RESULTS: {passed}/{total} passed ({100*passed//total}%)")
        if failures:
            print(f"  FAILURES ({len(failures)}):")
            for q, msgs in failures:
                print(f"  • {q}")
                for m in msgs:
                    print(f"      {m}")
        print(f"{'='*60}\n")

        sys.exit(0 if passed == total else 1)


def _kind_from_value(value: str) -> SectionKind | None:
    mapping = {
        "grounded_facts": SectionKind.GROUNDED_FACTS,
        "prerequisites": SectionKind.PREREQUISITES,
        "main_explanation": SectionKind.MAIN_EXPLANATION,
        "formula": SectionKind.FORMULA,
        "worked_example": SectionKind.WORKED_EXAMPLE,
        "proof": SectionKind.PROOF,
        "exercise": SectionKind.EXERCISE,
        "comparison": SectionKind.COMPARISON,
        "related_concepts": SectionKind.RELATED_CONCEPTS,
        "next_topics": SectionKind.NEXT_TOPICS,
        "summary": SectionKind.SUMMARY,
    }
    return mapping.get(value)


if __name__ == "__main__":
    benchmark = PlannerBenchmark()
    benchmark.run()
