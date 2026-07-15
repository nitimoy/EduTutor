"""The Evidence Assessment Engine."""

from __future__ import annotations

from typing import Optional

from backend.retrieval.api.search import SearchResult
from backend.tutor.models import EducationalIntent
from backend.tutor.intent import detect_intent
from backend.tutor.repository import KnowledgeRepository
from backend.evidence.models import EvidenceReport, CorpusPresence, EvidenceRelevance
from backend.evidence.checks import (
    EvidenceContext,
    RetrievalCoverageCheck,
    EducationalEvidenceCheck,
    LexicalSupportCheck,
    PlannerSupportCheck,
    CorpusPresenceCheck,
    TopicRelevanceCheck,
)


class EvidenceAssessmentEngine:
    """Deterministically evaluates retrieval evidence before planning."""

    def __init__(self):
        self.retrieval_check = RetrievalCoverageCheck()
        self.educational_check = EducationalEvidenceCheck()
        self.lexical_check = LexicalSupportCheck()
        self.planner_check = PlannerSupportCheck()
        self.presence_check = CorpusPresenceCheck()
        self.topic_relevance_check = TopicRelevanceCheck()

    def assess(
        self,
        query: str,
        results: list[SearchResult],
        repository: Optional[KnowledgeRepository] = None,
    ) -> EvidenceReport:
        """
        Evaluate the retrieved evidence.
        Returns an EvidenceReport detailing whether the pipeline should proceed.
        """
        issues: list[str] = []
        intent, _ = detect_intent(query)
        
        ctx = EvidenceContext(query=query, results=results, intent=intent, issues=issues)
        
        # 1. Retrieval Coverage
        if not self.retrieval_check.evaluate(ctx):
            return self._build_report(ctx, False, CorpusPresence.NOT_FOUND)
            
        # 2. Educational Evidence
        if not self.educational_check.evaluate(ctx):
            return self._build_report(ctx, False, CorpusPresence.NOT_FOUND)
            
        # 3. Lexical Support
        if not self.lexical_check.evaluate(ctx):
            return self._build_report(ctx, False, CorpusPresence.NOT_FOUND)
            
        # 4. Planner Support
        planner_supported = self.planner_check.evaluate(ctx)
        if not planner_supported:
            return self._build_report(ctx, False, CorpusPresence.NOT_FOUND)
            
        # 5. Corpus Presence
        presence = self.presence_check.evaluate(ctx)
        if presence == CorpusPresence.NOT_FOUND:
            ctx.issues.append("Requested concept absent from compiled corpus.")
            return self._build_report(ctx, False, presence, relevance=EvidenceRelevance.NOT_RELEVANT)
            
        # 6. Topic Relevance
        relevance = self.topic_relevance_check.evaluate(ctx, repository)
        if relevance == EvidenceRelevance.NOT_RELEVANT:
            return self._build_report(ctx, False, presence, planner_supported=planner_supported, relevance=relevance)
            
        # If all checks pass
        return self._build_report(ctx, True, presence, planner_supported=True, relevance=relevance)
        
    def _build_report(
        self,
        ctx: EvidenceContext,
        supported: bool,
        presence: CorpusPresence,
        planner_supported: bool = False,
        relevance: EvidenceRelevance = EvidenceRelevance.NOT_RELEVANT,
    ) -> EvidenceReport:
        score = ctx.results[0].score if ctx.results else 0.0
        
        reason = ""
        if not supported:
            if relevance == EvidenceRelevance.NOT_RELEVANT:
                reason = "I couldn't find educational material relevant to the requested topic within the compiled corpus."
            else:
                reason = ctx.issues[0] if ctx.issues else "Evidence insufficient to satisfy intent."
            
        return EvidenceReport(
            supported=supported,
            reason=reason,
            retrieval_score=score,
            coverage=0.0,  # We can expand on coverage if needed
            planner_supported=planner_supported,
            presence=presence,
            relevance=relevance,
            issues=list(ctx.issues),
        )
