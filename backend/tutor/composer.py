"""Answer Composer + the ``TutorBrain`` facade.

The composer performs the final, pure assembly of a resolved :class:`TeachingPlan`
into a :class:`TutorPlan` (fixed compiler-backed section slots + a de-duplicated
reference list). It does no selection of its own — the plan already decided what
to teach.

Phase 6 additions
-----------------
* ``TutorBrain.build_teaching_plan`` now runs:
    1. detect_intent (legacy)
    2. classify (QuestionType — fine-grained)
    3. organize (context)
    4. EvidenceSufficiencyCheck (can this answer WHY?)
    5. select_strategy_for_qt (intent-aware fallback)
    6. apply_lesson_pattern (block sections forbidden for this question type)
    7. Emit GROUNDED_FACTS disclaimer if sufficiency ≠ FULL and pattern says so.

* The grounded-facts disclaimer is a SectionSpec with kind=GROUNDED_FACTS and
  status=PRESENT. Its note text becomes a system-prompt directive that tells the
  LLM: "state this disclaimer, then list only grounded facts; do NOT infer."

``brain = TutorBrain()``
``tp = brain.build_teaching_plan(query, results, repository)  # stages 1-6``
``plan = brain.compose_from(tp, results)                       # stages 7-8``
``brain.plan(query, results, repository)`` runs the whole thing.
"""

from __future__ import annotations

from typing import Optional, Union

from backend.retrieval.strategies.base import RetrievalStrategy, SearchResult
from backend.tutor.citations import CitationBuilder
from backend.tutor.profile import ResponseProfile, ResponseProfiler
from backend.tutor.question_classifier import classify
from backend.tutor.goal_detector import detect_goal
from backend.tutor.lesson_patterns import pattern_for
from backend.tutor.models import (
    SOURCE_OBJECT,
    Citation,
    EducationalGoal,
    EvidenceSufficiency,
    PlanSection,
    QuestionType,
    SectionKind,
    SectionSpec,
    SectionStatus,
    TeachingPlan,
    TeachingStrategyKind,
    TutorPlan,
)
from backend.tutor.organizer import organize
from backend.tutor.repository import KnowledgeRepository
from backend.tutor.strategy import (
    apply_lesson_pattern,
    select_strategy_for_qt,
    template_for,
)
from backend.evidence.sufficiency import EvidenceSufficiencyCheck

_UNSUPPORTED_NOTE = (
    "Proof/exercise objects are not carried in the Knowledge Index; supply a "
    "KnowledgeRepository to include them. Misconceptions and derivations have no "
    "representation in the compiler artifacts and are never generated."
)

# The final TutorPlan's fixed slots, in declaration order.
_SLOTS: tuple[tuple[str, SectionKind], ...] = (
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
    ("grounded_facts", SectionKind.GROUNDED_FACTS),
)

_SUFFICIENCY_CHECKER = EvidenceSufficiencyCheck()


def _make_disclaimer_section(
    reason: str, educational_goal: EducationalGoal
) -> SectionSpec:
    """Build a GROUNDED_FACTS section with a natural, student-friendly disclaimer."""
    # Reason is a concise clause like "contains a definition but does not
    # explicitly explain the underlying reason". Compose a full, warm sentence.
    if reason:
        note = (
            f"The textbook {reason}. "
            f"The explanation below is therefore limited to the grounded "
            f"information available in the source material."
        )
    else:
        note = (
            "The textbook describes the concept and related information but does "
            "not explicitly explain the underlying reason. The explanation below "
            "is therefore limited to the grounded information available in the "
            "source material."
        )
    return SectionSpec(
        kind=SectionKind.GROUNDED_FACTS,
        status=SectionStatus.PRESENT,
        note=note,
    )


class AnswerComposer:
    """Assemble a resolved teaching plan into the final :class:`TutorPlan`."""

    def compose(
        self, teaching_plan: TeachingPlan, citations: list[list[Citation]]
    ) -> TutorPlan:
        """Build the TutorPlan from an ordered plan + per-section citations."""
        resolved: dict[SectionKind, PlanSection] = {}
        for spec, section_cites in zip(teaching_plan.sections, citations):
            resolved[spec.kind] = PlanSection(
                kind=spec.kind,
                status=spec.status,
                items=[ref.text for ref in spec.item_refs],
                citations=section_cites,
                note=spec.note,
            )

        def slot(kind: SectionKind) -> PlanSection:
            return resolved.get(kind, PlanSection(kind=kind, status=SectionStatus.EMPTY))

        references = _dedupe_references(citations)

        return TutorPlan(
            query=teaching_plan.query,
            intent=teaching_plan.intent,
            strategy=teaching_plan.strategy,
            question_type=teaching_plan.question_type,
            educational_goal=teaching_plan.educational_goal,
            primary_concept_id=teaching_plan.primary_concept_id,
            primary_concept_name=teaching_plan.primary_concept_name,
            references=references,
            notes=list(teaching_plan.notes),
            **{field: slot(kind) for field, kind in _SLOTS},
        )


class TutorBrain:
    """Deterministic post-retrieval teaching planner (no LLM)."""

    def __init__(self) -> None:
        self._composer = AnswerComposer()

    # --- stages 1-6: build the intermediate, editable plan -----------------
    def build_teaching_plan(
        self,
        profile_or_query: Union[str, ResponseProfile],
        results: list[SearchResult],
        repository: Optional[KnowledgeRepository] = None,
    ) -> TeachingPlan:
        if isinstance(profile_or_query, str):
            profile = ResponseProfiler.build(profile_or_query)
        else:
            profile = profile_or_query

        intent = profile.intent

        # Stage: fine-grained QuestionType classification.
        question_type, _match_key = classify(profile.query)

        # Stage: EducationalGoal — QuestionType × query context cues.
        educational_goal = detect_goal(question_type, profile.query)

        # Stage: organize retrieved knowledge into sections.
        context = organize(results, repository)

        # Stage: Evidence Sufficiency — dispatched on EducationalGoal.
        sufficiency, suf_reason = _SUFFICIENCY_CHECKER.check(
            educational_goal, context, results
        )

        # Stage: strategy selection (intent-aware, goal-aware fallback).
        # For chapter-level / broad topic queries, force REVISION_SUMMARY strategy
        # to provide a multi-concept overview instead of single-concept explanation.
        from backend.tutor.profile import QueryScope
        if profile.scope == QueryScope.CHAPTER_LEVEL:
            strategy = TeachingStrategyKind.REVISION_SUMMARY
            fallback_note = "Broad topic detected — using overview strategy."
        else:
            strategy, fallback_note = select_strategy_for_qt(
                question_type, intent, context, educational_goal=educational_goal
            )

        # Stage: collect sections per strategy template, apply lesson pattern.
        pattern = pattern_for(educational_goal)
        raw_sections = [context.section(kind) for kind in template_for(strategy)]
        sections = apply_lesson_pattern(raw_sections, pattern)

        notes: list[str] = []
        if fallback_note:
            notes.append(fallback_note)
        if any(s.status == SectionStatus.UNSUPPORTED_BY_INDEX for s in sections):
            notes.append(_UNSUPPORTED_NOTE)

        # Stage: emit GROUNDED_FACTS disclaimer when evidence cannot support
        # the required reasoning style and the lesson pattern requests one.
        if (
            sufficiency in (EvidenceSufficiency.PARTIALLY_SUPPORTED, EvidenceSufficiency.INSUFFICIENT)
            and pattern.disclaimer_if_partial
        ):
            disclaimer = _make_disclaimer_section(suf_reason, educational_goal)
            
            if sufficiency == EvidenceSufficiency.INSUFFICIENT or (
                sufficiency == EvidenceSufficiency.PARTIALLY_SUPPORTED 
                and educational_goal == EducationalGoal.STRUCTURED_COMPARISON
            ):
                from backend.tutor.strategy import _lead_section_for
                lead_kind = _lead_section_for(strategy, pattern)
                for i, s in enumerate(sections):
                    if s.kind == lead_kind:
                        sections[i] = SectionSpec(
                            kind=s.kind,
                            status=SectionStatus.EMPTY,
                            note=f"Blocked due to {sufficiency.value} evidence."
                        )
                
                # For comparison with insufficient evidence, also block MAIN_EXPLANATION
                # to prevent explaining just one concept when comparison was requested.
                if educational_goal == EducationalGoal.STRUCTURED_COMPARISON:
                    for i, s in enumerate(sections):
                        if s.kind == SectionKind.MAIN_EXPLANATION:
                            sections[i] = SectionSpec(
                                kind=s.kind,
                                status=SectionStatus.EMPTY,
                                note="Blocked: comparison requested but only one concept available."
                            )

            sections = [disclaimer] + sections
            notes.append(
                f"evidence_sufficiency={sufficiency.value}: {suf_reason}"
            )

        return TeachingPlan(
            query=profile.query,
            intent=intent,
            strategy=strategy,
            question_type=question_type,
            educational_goal=educational_goal,
            primary_concept_id=context.primary_concept_id,
            primary_concept_name=context.primary_concept_name,
            supporting_concept_ids=context.supporting_concept_ids,
            sections=sections,
            notes=notes,
        )

    # --- stages 7-8: resolve citations + compose ---------------------------
    def compose_from(
        self, teaching_plan: TeachingPlan, results: list[SearchResult]
    ) -> TutorPlan:
        """Resolve citations (using ``results`` for name→id) and compose the final plan."""
        citations = CitationBuilder.from_results(results).resolve(teaching_plan)
        plan = self._composer.compose(teaching_plan, citations)
        _assert_no_invention(plan, {r.document.concept_id for r in results})
        return plan

    # --- full pipeline -----------------------------------------------------
    def plan(
        self,
        profile_or_query: Union[str, ResponseProfile],
        results: list[SearchResult],
        repository: Optional[KnowledgeRepository] = None,
    ) -> TutorPlan:
        teaching_plan = self.build_teaching_plan(profile_or_query, results, repository)
        return self.compose_from(teaching_plan, results)

    def plan_for_query(
        self,
        profile_or_query: Union[str, ResponseProfile],
        strategy: RetrievalStrategy,
        repository: Optional[KnowledgeRepository] = None,
        top_k: int = 5,
    ) -> TutorPlan:
        """Convenience: run retrieval with ``strategy`` then plan over the results."""
        query = profile_or_query if isinstance(profile_or_query, str) else profile_or_query.query
        results = strategy.search(query, top_k=top_k)
        return self.plan(profile_or_query, results, repository)


def _dedupe_references(citations: list[list[Citation]]) -> list[Citation]:
    """Flatten + de-duplicate citations deterministically (first-seen order)."""
    seen: set[tuple] = set()
    out: list[Citation] = []
    for section_cites in citations:
        for c in section_cites:
            if c.concept_id is None and c.source_field != SOURCE_OBJECT:
                continue  # unresolved graph name — not a traceable reference
            key = (c.concept_id, c.source_field, c.locator, c.object_type)
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
    return out


def _assert_no_invention(plan: TutorPlan, valid_concept_ids: set[str]) -> None:
    """Every cited concept id must be a real retrieved document (or None/unresolved).

    Object-id locators come straight from repository recovery, so they are real by
    construction; the checkable invariant is that no *concept* id was fabricated.
    """
    for c in plan.references:
        if c.concept_id is not None and c.concept_id not in valid_concept_ids:
            raise AssertionError(
                f"Tutor Brain invented concept id {c.concept_id!r} not in retrieved set"
            )
