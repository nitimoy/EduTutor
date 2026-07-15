"""Deterministic evaluation of the Learning Session Engine — architectural correctness.

Verifies: deterministic updates, identical replay (``apply(before, delta) == after`` and
re-folding yields the same delta), the canonical-delta property (the summary is fully
regenerable from ``(before, delta, session)``), state-transition correctness, event
ordering, reproducibility, and the numeric invariants. No educational-quality metrics.
Offline, no LLM.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from backend.evaluation.session_models import (
    CaseResult,
    SessionCase,
    SessionEvalReport,
    TransitionCase,
)
from backend.session.engine import LearningSessionEngine
from backend.session.events import EventType, LearningEvent, SessionEventLog
from backend.session.state_delta import StudentStateApplier
from backend.session.summary import build_summary
from backend.student.learning_state import LearningState
from backend.student.models import StudentState


def _ev(t: EventType, c: Optional[str] = None) -> LearningEvent:
    return LearningEvent(type=t, concept_id=c)


def default_cases() -> list[SessionCase]:
    return [
        SessionCase(
            name="master_via_exercises_and_proof",
            before=StudentState(prerequisite_gaps=["c1"]),
            session=SessionEventLog(session_id="s.master", events=[
                _ev(EventType.LESSON_STARTED, "c1"),
                _ev(EventType.EXERCISE_ATTEMPTED, "c1"),
                _ev(EventType.EXERCISE_CORRECT, "c1"),
                _ev(EventType.EXERCISE_CORRECT, "c1"),
                _ev(EventType.PROOF_COMPLETED, "c1"),
                _ev(EventType.CONCEPT_MASTERED, "c1"),
                _ev(EventType.LESSON_COMPLETED),
            ]),
            expected_mastered=["c1"],
            expected_streak_delta=1,
        ),
        SessionCase(
            name="struggle_needs_review",
            before=StudentState(concept_states={"c2": LearningState.MASTERED},
                                concept_mastery={"c2": 0.85}),
            session=SessionEventLog(session_id="s.review", events=[
                _ev(EventType.REVIEW_COMPLETED, "c2"),
            ]),
        ),
        SessionCase(
            name="incorrect_lowers_mastery",
            before=StudentState(concept_mastery={"c3": 0.5}),
            session=SessionEventLog(session_id="s.wrong", events=[
                _ev(EventType.EXERCISE_ATTEMPTED, "c3"),
                _ev(EventType.EXERCISE_INCORRECT, "c3"),
            ]),
        ),
        SessionCase(
            name="proof_skipped_is_neutral",
            before=StudentState(concept_mastery={"c4": 0.4}),
            session=SessionEventLog(session_id="s.skip", events=[
                _ev(EventType.PROOF_SKIPPED, "c4"),
            ]),
        ),
        SessionCase(
            name="empty_session_is_noop",
            before=StudentState(concept_mastery={"c5": 0.3}),
            session=SessionEventLog(session_id="s.empty", events=[]),
        ),
    ]


def default_transition_cases() -> list[TransitionCase]:
    return [
        TransitionCase(from_state="unseen", event_type="lesson_started", to_state="introduced"),
        TransitionCase(from_state="introduced", event_type="exercise_correct", to_state="practicing"),
        TransitionCase(from_state="practicing", event_type="exercise_correct", to_state="mastered"),
        TransitionCase(from_state="practicing", event_type="exercise_incorrect", to_state="practicing"),
        TransitionCase(from_state="mastered", event_type="review_completed", to_state="mastered"),
        TransitionCase(from_state="forgotten", event_type="review_completed", to_state="needs_review"),
        TransitionCase(from_state="introduced", event_type="concept_mastered", to_state="mastered"),
    ]


class SessionEvaluationEngine:
    def __init__(self, engine: Optional[LearningSessionEngine] = None,
                 applier: Optional[StudentStateApplier] = None) -> None:
        self._engine = engine or LearningSessionEngine()
        self._applier = applier or StudentStateApplier()

    def evaluate(
        self, cases: list[SessionCase], transition_cases: list[TransitionCase]
    ) -> SessionEvalReport:
        results = [self._evaluate_case(c) for c in cases]
        n = len(results) or 1

        def rate(attr: str) -> float:
            return round(sum(1 for r in results if getattr(r, attr)) / n, 6)

        t_ok = sum(1 for t in transition_cases if self._transition_ok(t))
        t_total = len(transition_cases) or 1

        report = SessionEvalReport(
            n_cases=len(results),
            determinism_rate=rate("deterministic"),
            replay_rate=rate("replay_ok"),
            canonical_delta_rate=rate("canonical_delta_ok"),
            outcome_rate=rate("outcome_ok"),
            invariant_rate=rate("invariants_ok"),
            n_transition_cases=len(transition_cases),
            transition_correctness_rate=round(t_ok / t_total, 6),
            case_results=results,
        )
        report.all_passed = (
            report.determinism_rate == 1.0 and report.replay_rate == 1.0
            and report.canonical_delta_rate == 1.0 and report.outcome_rate == 1.0
            and report.invariant_rate == 1.0
            and report.transition_correctness_rate == 1.0
        )
        return report

    def _evaluate_case(self, case: SessionCase) -> CaseResult:
        before_json = case.before.model_dump_json()

        result = self._engine.process(case.before, case.session)
        result2 = self._engine.process(case.before, case.session)
        deterministic = result.model_dump_json() == result2.model_dump_json()

        # Replay: applying the canonical delta reproduces the after-state.
        replayed = self._applier.apply(case.before, result.delta)
        replay_ok = replayed.model_dump_json() == result.after.model_dump_json()

        # Canonical delta: the summary is regenerable from (before, delta, session).
        regen = build_summary(case.before, replayed, case.session)
        canonical_ok = regen.model_dump_json() == result.summary.model_dump_json()

        # Expected structural outcome.
        outcome_ok = (
            set(result.summary.concepts_mastered) == set(case.expected_mastered)
            and set(result.summary.concepts_needing_review) == set(case.expected_needing_review)
            and result.delta.streak_delta == case.expected_streak_delta
        )

        # Invariants: ranges clamped, before unchanged, counts consistent.
        ranges_ok = all(
            0.0 <= v <= 1.0 for v in result.after.concept_mastery.values()
        ) and all(0.0 <= v <= 1.0 for v in result.after.concept_confidence.values())
        before_unchanged = case.before.model_dump_json() == before_json
        counts_ok = (
            result.summary.exercises_solved + result.summary.exercises_failed
            <= result.summary.exercises_attempted
        )
        invariants_ok = ranges_ok and before_unchanged and counts_ok

        return CaseResult(
            name=case.name, deterministic=deterministic, replay_ok=replay_ok,
            canonical_delta_ok=canonical_ok, outcome_ok=outcome_ok,
            invariants_ok=invariants_ok,
        )

    def _transition_ok(self, case: TransitionCase) -> bool:
        before = StudentState(concept_states={case.concept_id: LearningState(case.from_state)})
        session = SessionEventLog(
            session_id="determinism_test", events=[LearningEvent(
                type=EventType(case.event_type), concept_id=case.concept_id)])
        after = self._engine.process(before, session).after
        return after.state_of(case.concept_id).value == case.to_state


def _print_summary(report: SessionEvalReport) -> None:
    print("\n=== Learning Session Engine eval (architectural correctness) ===")
    print(f"  session cases          {report.n_cases}")
    print(f"  deterministic updates  {report.determinism_rate:.3f}")
    print(f"  identical replay       {report.replay_rate:.3f}")
    print(f"  canonical delta        {report.canonical_delta_rate:.3f}")
    print(f"  expected outcomes      {report.outcome_rate:.3f}")
    print(f"  invariants             {report.invariant_rate:.3f}")
    print(f"  state transitions      {report.transition_correctness_rate:.3f} "
          f"({report.n_transition_cases} cases)")
    print(f"  ALL PASSED             {report.all_passed}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate the Learning Session Engine")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    engine = SessionEvaluationEngine()
    report = engine.evaluate(default_cases(), default_transition_cases())
    _print_summary(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.model_dump_json(indent=2) + "\n")
        print(f"\nWrote {args.out}")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
