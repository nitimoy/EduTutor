"""Deterministic evaluation of the Student Model — architectural correctness only.

Verifies: determinism (byte-identical delta across two runs), decision correctness
(expected actions produced), priority ordering (decisions in non-decreasing priority),
state-transition correctness (the fixed table), and the structural invariants
(``source_plan`` unchanged after apply; applied section-kinds ⊆ source; every applied
section's ``item_refs`` identical to the source ⇒ no invention). No educational-quality
metrics. Offline, no LLM.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from backend.evaluation.student_models import (
    CaseResult,
    StateTransitionCase,
    StudentEvalReport,
    StudentPersonalizationCase,
)
from backend.student.applier import TeachingPlanApplier
from backend.student.engine import StudentModel
from backend.student.learning_state import LearningSignal, LearningState, transition
from backend.student.models import (
    DifficultyPreference,
    ExamplePreference,
    ExplanationPreference,
    PacePreference,
    StudentPreferences,
    StudentProfile,
    StudentState,
)
from backend.tutor.models import (
    EducationalIntent,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
)


def reference_plan() -> TeachingPlan:
    """A fixed synthetic plan exercising every section the rules touch."""
    def sec(kind: SectionKind) -> SectionSpec:
        return SectionSpec(kind=kind, status=SectionStatus.PRESENT,
                           item_refs=[], note="")
    return TeachingPlan(
        query="reference", intent=EducationalIntent.PROOF,
        strategy=TeachingStrategyKind.STEP_BY_STEP_DERIVATION,
        primary_concept_id="c1", primary_concept_name="Alpha",
        sections=[
            sec(SectionKind.MAIN_EXPLANATION), sec(SectionKind.PREREQUISITES),
            sec(SectionKind.PROOF), sec(SectionKind.WORKED_EXAMPLE),
            sec(SectionKind.SUMMARY),
        ],
    )


def default_cases() -> list[StudentPersonalizationCase]:
    return [
        StudentPersonalizationCase(
            name="beginner_with_gaps",
            profile=StudentProfile(
                state=StudentState(concept_mastery={"c1": 0.1}, prerequisite_gaps=["c0"]),
                preferences=StudentPreferences(
                    difficulty=DifficultyPreference.EASY, example=ExamplePreference.MANY)),
            expected_actions=["insert_prerequisite_review", "lower_difficulty",
                              "increase_worked_examples"],
            expected_suppressed=["proof"],
            expected_front=["worked_example"],
        ),
        StudentPersonalizationCase(
            name="advanced_fast",
            profile=StudentProfile(
                state=StudentState(concept_mastery={"c1": 0.95}, completed_concepts=["c1"]),
                preferences=StudentPreferences(
                    difficulty=DifficultyPreference.CHALLENGING, pace=PacePreference.FAST)),
            expected_actions=["raise_difficulty", "adjust_depth"],
            expected_front=["proof"],
        ),
        StudentPersonalizationCase(
            name="forgotten_concept",
            # mid mastery isolates the revision rule (low-mastery rules would otherwise
            # also fire and move examples ahead of the summary).
            profile=StudentProfile(
                state=StudentState(concept_states={"c1": LearningState.FORGOTTEN},
                                   concept_mastery={"c1": 0.5})),
            expected_actions=["recommend_revision"],
            expected_front=["summary"],
        ),
        StudentPersonalizationCase(
            name="conflicting_difficulty",  # low mastery AND challenging pref -> one wins
            profile=StudentProfile(
                state=StudentState(concept_mastery={"c1": 0.1}),
                preferences=StudentPreferences(difficulty=DifficultyPreference.CHALLENGING)),
            expected_actions=["lower_difficulty"],  # declared first at equal priority
        ),
        StudentPersonalizationCase(
            name="new_student_no_signal",
            profile=StudentProfile(),  # low (0.0) mastery still triggers beginner-ish rules
            expected_actions=[],  # subset check: no specific action required
        ),
        StudentPersonalizationCase(
            name="detailed_explanation_pref",
            profile=StudentProfile(preferences=StudentPreferences(
                explanation=ExplanationPreference.DETAILED)),
            expected_actions=["adjust_depth"],
        ),
    ]


def default_transition_cases() -> list[StateTransitionCase]:
    return [
        StateTransitionCase(from_state="unseen", signal="introduce", to_state="introduced"),
        StateTransitionCase(from_state="introduced", signal="practice_success", to_state="practicing"),
        StateTransitionCase(from_state="practicing", signal="practice_success", to_state="mastered"),
        StateTransitionCase(from_state="mastered", signal="decay", to_state="forgotten"),
        StateTransitionCase(from_state="forgotten", signal="review", to_state="needs_review"),
        StateTransitionCase(from_state="needs_review", signal="practice_success", to_state="mastered"),
        StateTransitionCase(from_state="mastered", signal="reset", to_state="unseen"),
        StateTransitionCase(from_state="practicing", signal="introduce", to_state="practicing"),  # no-op
    ]


class StudentModelEvaluationEngine:
    def __init__(self, model: Optional[StudentModel] = None,
                 applier: Optional[TeachingPlanApplier] = None) -> None:
        self._model = model or StudentModel()
        self._applier = applier or TeachingPlanApplier()

    def evaluate(
        self,
        cases: list[StudentPersonalizationCase],
        transition_cases: list[StateTransitionCase],
        plan: Optional[TeachingPlan] = None,
    ) -> StudentEvalReport:
        plan = plan or reference_plan()
        results = [self._evaluate_case(c, plan) for c in cases]
        n = len(results) or 1

        def rate(attr: str) -> float:
            return round(sum(1 for r in results if getattr(r, attr)) / n, 6)

        t_ok = sum(1 for t in transition_cases if _transition_ok(t))
        t_total = len(transition_cases) or 1
        transition_rate = round(t_ok / t_total, 6)

        report = StudentEvalReport(
            n_cases=len(results),
            determinism_rate=rate("deterministic"),
            decision_correctness_rate=rate("decision_ok"),
            priority_ordering_rate=rate("priority_ordered"),
            invariant_pass_rate=rate("invariants_ok"),
            n_transition_cases=len(transition_cases),
            transition_correctness_rate=transition_rate,
            case_results=results,
        )
        report.all_passed = (
            report.determinism_rate == 1.0
            and report.decision_correctness_rate == 1.0
            and report.priority_ordering_rate == 1.0
            and report.invariant_pass_rate == 1.0
            and report.transition_correctness_rate == 1.0
        )
        return report

    def _evaluate_case(
        self, case: StudentPersonalizationCase, plan: TeachingPlan
    ) -> CaseResult:
        before = plan.model_dump_json()
        delta = self._model.personalize(plan, case.profile)
        delta2 = self._model.personalize(plan, case.profile)
        deterministic = delta.model_dump_json() == delta2.model_dump_json()

        produced = [d.action.value for d in delta.decisions]
        decision_ok = set(case.expected_actions).issubset(set(produced))

        priorities = [d.priority for d in delta.decisions]
        priority_ordered = priorities == sorted(priorities)

        applied = self._applier.apply(delta)
        source_unchanged = plan.model_dump_json() == before
        applied_kinds = [s.kind for s in applied.sections]
        source_by_kind = {s.kind: s for s in plan.sections}
        kinds_subset = set(applied_kinds).issubset(set(source_by_kind))
        # no invention: every applied section's items are identical to the source's
        content_identical = all(
            s.item_refs == source_by_kind[s.kind].item_refs for s in applied.sections
        )
        suppressed_ok = all(
            SectionKind(k) not in applied_kinds for k in case.expected_suppressed
        )
        front_ok = _front_matches(applied_kinds, case.expected_front)
        invariants_ok = (
            source_unchanged and kinds_subset and content_identical
            and suppressed_ok and front_ok
        )

        return CaseResult(
            name=case.name, deterministic=deterministic, decision_ok=decision_ok,
            priority_ordered=priority_ordered, invariants_ok=invariants_ok,
            produced_actions=produced,
        )


def _front_matches(applied_kinds: list[SectionKind], expected_front: list[str]) -> bool:
    for i, kind_value in enumerate(expected_front):
        if i >= len(applied_kinds) or applied_kinds[i].value != kind_value:
            return False
    return True


def _transition_ok(case: StateTransitionCase) -> bool:
    nxt, _ = transition(LearningState(case.from_state), LearningSignal(case.signal))
    return nxt.value == case.to_state


def _print_summary(report: StudentEvalReport) -> None:
    print("\n=== Student Model eval (architectural correctness) ===")
    print(f"  personalization cases   {report.n_cases}")
    print(f"  determinism             {report.determinism_rate:.3f}")
    print(f"  decision correctness    {report.decision_correctness_rate:.3f}")
    print(f"  priority ordering       {report.priority_ordering_rate:.3f}")
    print(f"  invariants (no-invent)  {report.invariant_pass_rate:.3f}")
    print(f"  state transitions       {report.transition_correctness_rate:.3f} "
          f"({report.n_transition_cases} cases)")
    print(f"  ALL PASSED              {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Student Model (architecture)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    engine = StudentModelEvaluationEngine()
    report = engine.evaluate(default_cases(), default_transition_cases())
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
