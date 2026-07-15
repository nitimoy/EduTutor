"""The Educational Tutor Orchestrator.

Coordinates the frozen components into one deterministic end-to-end pipeline behind a single
public API (:meth:`EducationalTutorEngine.answer`). It adds no educational logic and mutates
no input — it only sequences calls, propagates metadata, traces stages, and assembles a
:class:`TutorResponse`. Any stage exception halts the pipeline immediately (no retries).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable, Optional, TypeVar

from backend.generation.language_model import LanguageModel
from backend.generation.plan_builder import build_generation_plan
from backend.generation.providers import make_language_model
from backend.generation.renderer import Renderer
from backend.orchestrator.config import OrchestratorConfig
from backend.orchestrator.errors import (
    ConfigurationError,
    StageExecutionError,
    VerificationFailedError,
)
from backend.orchestrator.models import (
    ExecutionMetadata,
    RetrievalMetadata,
    TimingInfo,
    TutorResponse,
)
from backend.orchestrator.tracing import ExecutionTrace, Tracer
from backend.retrieval.strategies.base import RetrievalContext, RetrievalStrategy
from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy
from backend.student.applier import TeachingPlanApplier
from backend.student.engine import StudentModel
from backend.student.models import StudentProfile
from backend.student.rules import DEFAULT_POLICY, RulePolicy
from backend.tutor.composer import TutorBrain
from backend.tutor.repository import CompiledArtifactRepository, KnowledgeRepository
from backend.verification.engine import ResponseVerificationEngine
from backend.evidence.engine import EvidenceAssessmentEngine
from backend.evidence.models import EvidenceReport
from backend.orchestrator.models import UnsupportedQueryResponse
from backend.generation.models import RenderedResponse
from backend.tutor.models import TutorPlan, EducationalIntent, TeachingStrategyKind, PlanSection, SectionKind, SectionStatus, TeachingPlan
from backend.verification.models import VerificationReport, CoverageReport, CitationReport, GroundingReport, CompletenessReport, ContractReport, ProviderInvariantReport, VerificationMetrics
from backend.student.models import TeachingPlanDelta
from backend.tutor.profile import ResponseProfiler
from backend.retrieval.ranking import ConceptRanker

T = TypeVar("T")

# Fixed stage order (matches the pipeline and the trace).
STAGES = ("profiling", "retrieval", "ranking", "evidence_assessment", "planning", "personalization", "composition", "generation", "verification")


class EducationalTutorEngine:
    """Run the full educational pipeline deterministically."""

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        *,
        strategy: Optional[RetrievalStrategy] = None,
        repository: Optional[KnowledgeRepository] = None,
        brain: Optional[TutorBrain] = None,
        student_model: Optional[StudentModel] = None,
        applier: Optional[TeachingPlanApplier] = None,
        renderer: Optional[Renderer] = None,
        language_model: Optional[LanguageModel] = None,
        verification_engine: Optional[ResponseVerificationEngine] = None,
        policy: Optional[RulePolicy] = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._strategy = strategy or self._build_strategy()
        self._repository = repository if repository is not None else self._build_repository()
        self._brain = brain or TutorBrain()
        self._student_model = student_model or StudentModel(policy or DEFAULT_POLICY)
        self._applier = applier or TeachingPlanApplier()
        self._renderer = renderer or Renderer()
        self._language_model = language_model or make_language_model(self._config.generation)
        self._verifier = verification_engine or ResponseVerificationEngine(self._config.verification)
        self._evidence_engine = EvidenceAssessmentEngine()
        self._ranker = ConceptRanker()

    # --- component construction from config --------------------------------
    def _build_strategy(self) -> RetrievalStrategy:
        if self._config.compiled_dir is None:
            raise ConfigurationError(
                "no retrieval strategy injected and config.compiled_dir is unset")
        return BM25FRetrievalStrategy(self._config.compiled_dir)

    def _build_repository(self) -> Optional[KnowledgeRepository]:
        if not self._config.use_repository:
            return None
        if self._config.compiled_dir is None:
            raise ConfigurationError(
                "use_repository is set but config.compiled_dir is unset")
        return CompiledArtifactRepository.from_compiled_dir(self._config.compiled_dir)

    # --- public API --------------------------------------------------------
    def answer(
        self,
        query: str,
        student_profile: StudentProfile,
        retrieval_context: Optional[RetrievalContext] = None,
    ) -> TutorResponse:
        tracer = Tracer()

        profile = self._stage(tracer, "profiling",
            lambda: ResponseProfiler.build(query))

        # Auto-detect subject from query if no explicit context provided.
        ctx = retrieval_context
        if ctx is None and profile.subject is not None:
            ctx = RetrievalContext(subject=profile.subject)

        # Adjust top_k based on query scope.
        from backend.tutor.profile import QueryScope
        top_k = self._config.top_k
        if profile.scope == QueryScope.CHAPTER_LEVEL:
            # Chapter-level queries need many concepts for comprehensive coverage.
            top_k = max(top_k, 15)
        elif profile.scope == QueryScope.MULTI_CONCEPT:
            # Multi-concept queries need at least 2-3 concepts.
            top_k = max(top_k, 5)
        elif profile.intent in (EducationalIntent.REVISION,):
            # Revision queries need more concepts.
            top_k = max(top_k, 10)

        results = self._stage(tracer, "retrieval",
            lambda: self._strategy.search(profile.query, top_k, ctx))
            
        ranked_results = self._stage(tracer, "ranking",
            lambda: self._ranker.rank(profile.query, profile, results))

        evidence_report = self._stage(tracer, "evidence_assessment",
            lambda: self._evidence_engine.assess(profile.query, ranked_results, self._repository))
            
        if not evidence_report.supported:
            return UnsupportedQueryResponse(
                query=query,
                reason=evidence_report.reason,
                evidence_report=evidence_report,
                retrieval_metadata=RetrievalMetadata(
                    strategy_name=self._strategy.metadata().name,
                    top_k=self._config.top_k,
                    n_results=len(results),
                    result_concept_ids=tuple(r.document.concept_id for r in results),
                    retrieved_concepts=[],
                    subject=retrieval_context.subject if retrieval_context else None,
                    chapter=retrieval_context.chapter if retrieval_context else None,
                ),
                execution_metadata=ExecutionMetadata(
                    provider="system", model_id="system", style_preset="system", 
                    intent="unsupported", teaching_strategy="refusal",
                    primary_concept_name="N/A", verification_passed=True
                ),
                execution_trace=tracer.build(),
                timing=TimingInfo(),
                rendered_response=RenderedResponse(query=query, text=evidence_report.reason or "The query could not be grounded in the available NCERT corpus.", sections=[]),
                tutor_plan=TutorPlan(
                    query=query,
                    intent=EducationalIntent.DEFINITION,
                    strategy=TeachingStrategyKind.CONCEPT_EXPLANATION,
                    primary_concept_name="",
                    prerequisites=PlanSection(kind=SectionKind.PREREQUISITES, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    main_explanation=PlanSection(kind=SectionKind.MAIN_EXPLANATION, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    formula=PlanSection(kind=SectionKind.FORMULA, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    worked_example=PlanSection(kind=SectionKind.WORKED_EXAMPLE, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    proof=PlanSection(kind=SectionKind.PROOF, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    exercise=PlanSection(kind=SectionKind.EXERCISE, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    comparison=PlanSection(kind=SectionKind.COMPARISON, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    related_concepts=PlanSection(kind=SectionKind.RELATED_CONCEPTS, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    suggested_next_topics=PlanSection(kind=SectionKind.NEXT_TOPICS, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                    summary=PlanSection(kind=SectionKind.SUMMARY, status=SectionStatus.UNSUPPORTED_BY_INDEX),
                ),
                verification_report=VerificationReport(
                    coverage=CoverageReport(),
                    citations=CitationReport(),
                    grounding=GroundingReport(),
                    completeness=CompletenessReport(),
                    contract=ContractReport(),
                    provider=ProviderInvariantReport(),
                    metrics=VerificationMetrics(),
                    passed=True  # Refusal, not a verification failure
                ),
                personalization=TeachingPlanDelta(
                    source_plan=TeachingPlan(
                        query=query,
                        intent=EducationalIntent.DEFINITION,
                        strategy=TeachingStrategyKind.CONCEPT_EXPLANATION,
                    ),
                ),
            )

        teaching_plan = self._stage(tracer, "planning",
            lambda: self._brain.build_teaching_plan(profile, ranked_results, self._repository))

        def _personalize():
            delta = self._student_model.personalize(teaching_plan, student_profile)
            return delta, self._applier.apply(delta)
        delta, personalized_plan = self._stage(tracer, "personalization", _personalize)

        tutor_plan = self._stage(tracer, "composition",
            lambda: self._brain.compose_from(personalized_plan, ranked_results))

        def _generate():
            gen_plan = build_generation_plan(tutor_plan, self._config.style_preset)
            rendered = self._renderer.render(
                tutor_plan, self._config.generation, self._language_model)
            return gen_plan, rendered
        gen_plan, rendered = self._stage(tracer, "generation", _generate)

        report = self._stage(tracer, "verification",
            lambda: self._verifier.verify(tutor_plan, gen_plan, rendered))

        trace = tracer.build()
        response = self._assemble(
            profile.query, ranked_results, delta, tutor_plan, rendered, report, trace, ctx, evidence_report)

        if self._config.strict_verification and not report.passed:
            raise VerificationFailedError(response)
        return response

    # --- helpers -----------------------------------------------------------
    def _stage(self, tracer: Tracer, name: str, fn: Callable[[], T]) -> T:
        """Run one stage under the tracer; wrap any failure and halt (no retry)."""
        try:
            with tracer.stage(name):
                return fn()
        except StageExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - deliberately halt on any stage error
            raise StageExecutionError(name, exc) from exc

    def _strategy_name(self) -> str:
        try:
            return self._strategy.metadata().name
        except Exception:  # noqa: BLE001 - a fake strategy may not implement metadata()
            return self._config.retrieval_strategy

    def _assemble(
        self, query, results, delta, tutor_plan, rendered, report, trace: ExecutionTrace,
        retrieval_context: Optional[RetrievalContext],
        evidence_report: Optional[EvidenceReport] = None,
    ) -> TutorResponse:
        lm_meta = self._language_model.metadata()
        from backend.orchestrator.models import RetrievedConceptMetadata
        retrieval_metadata = RetrievalMetadata(
            strategy_name=self._strategy_name(), top_k=self._config.top_k,
            n_results=len(results),
            result_concept_ids=tuple(r.document.concept_id for r in results),
            retrieved_concepts=[
                RetrievedConceptMetadata(
                    concept_id=r.document.concept_id,
                    name=r.document.name,
                    score=r.score,
                    breakdown=asdict(r.ranking_breakdown) if r.ranking_breakdown else None
                ) for r in results
            ],
            subject=retrieval_context.subject if retrieval_context else None,
            chapter=retrieval_context.chapter if retrieval_context else None)
        execution_metadata = ExecutionMetadata(
            provider=lm_meta.provider, model_id=lm_meta.model_id,
            style_preset=self._config.style_preset, intent=tutor_plan.intent.value,
            teaching_strategy=tutor_plan.strategy.value,
            primary_concept_name=tutor_plan.primary_concept_name,
            personalization_decisions=len(delta.decisions),
            verification_passed=report.passed,
            strict_verification=self._config.strict_verification)
        timing = TimingInfo(
            total_ms=trace.total_duration_ms,
            per_stage_ms={s.name: s.duration_ms for s in trace.stages})
        return TutorResponse(
            query=query, rendered_response=rendered, tutor_plan=tutor_plan,
            verification_report=report, personalization=delta,
            citations=tuple(tutor_plan.references),
            retrieval_metadata=retrieval_metadata, execution_metadata=execution_metadata,
            execution_trace=trace, timing=timing, passed=report.passed,
            evidence_report=evidence_report)
