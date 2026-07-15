"""Follow-up query resolution rules for deterministic contextual rewriting."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from backend.session.models import LearningSession


def _extract_explicit_concept(query: str) -> str | None:
    """Extract an explicitly mentioned concept from a follow-up query.
    
    Detects patterns like:
    - "more examples of differentiability"
    - "another example of matrices"
    - "explain differentiation"
    - "what about integrals"
    
    Returns the concept name if found, None otherwise.
    """
    q = query.lower().strip()
    
    # Pattern: "of <concept>" after example-related words
    m = re.search(r'(?:example|explain|about|of)\s+(?:the\s+)?(?:concept\s+of\s+)?([a-z][a-z\s]+?)(?:\s*$|\s*[?.])', q)
    if m:
        concept = m.group(1).strip()
        # Filter out common non-concept words
        stop_words = {'the', 'a', 'an', 'this', 'that', 'it', 'them', 'those', 'these', 'is', 'are', 'was', 'were'}
        words = concept.split()
        if words and words[0] not in stop_words:
            return concept
    
    return None


class FollowUpRule(ABC):
    """A rule to detect and rewrite a contextual follow-up query."""

    @abstractmethod
    def matches(self, query: str) -> bool:
        """Return True if this rule should handle the query."""
        pass

    @abstractmethod
    def rewrite(self, query: str, session: LearningSession) -> str:
        """Rewrite the query deterministically using session context."""
        pass


class AnotherExampleRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(
            r'\b(another|more|one more|give me (?:a |an |one )?|show me (?:a |an |one )?|can you (?:show|give) (?:a |an |one )?|i want (?:a |an |one )?|i need (?:a |an |one )?)\s*example(s)?\b',
            q
        ))

    def rewrite(self, query: str, session: LearningSession) -> str:
        # Check if user explicitly mentions a new concept (e.g., "more examples of differentiability")
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Show me a worked example of {explicit_concept}."
        concept = session.active_concept or "that concept"
        return f"Show me a worked example of {concept}."


class ExplainAgainRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\b(explain|what is)\s+(that|it|this)\s+again\b', q)) or q in ("i don't understand", "i am confused", "simplify")

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Explain the concept of {explicit_concept} again in simpler terms."
        concept = session.active_concept or "that concept"
        return f"Explain the concept of {concept} again in simpler terms."


class MoreExplanationRule(FollowUpRule):
    """Handle 'any more explanation?', 'tell me more', 'what else?', etc."""
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(
            r'\b(any\s+more|tell\s+me\s+more|what\s+else|more\s+about|go\s+deeper'
            r'|elaborate|continue|keep\s+going|anything\s+else)\b', q
        ))

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Explain {explicit_concept} in more detail."
        concept = session.active_concept or "that concept"
        return f"Explain {concept} in more detail."


class WhatsNextRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\bwhat(\'?)s\s+next\b', q)) or q == "next"

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"What are the next topics after {explicit_concept}?"
        concept = session.active_concept or "that concept"
        return f"What are the next topics after {concept}?"


class ClarifyRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\bwhat\s+(does|do)\s+(that|it|this)\s+mean\b', q)) or q in ("clarify", "explain further")

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Clarify the meaning of {explicit_concept}."
        concept = session.active_concept or "that concept"
        return f"Clarify the meaning of {concept}."


class PreviousStepRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return q in ("go back", "previous step", "what was before this", "what is before this")

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"What are the prerequisites for {explicit_concept}?"
        concept = session.active_concept or "that concept"
        return f"What are the prerequisites for {concept}?"


class PracticeQuestionRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\b(give me a practice question|test me|give me a problem)\b', q))

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Give me a practice question about {explicit_concept}."
        concept = session.active_concept or "that concept"
        return f"Give me a practice question about {concept}."


class ShowSolutionRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\b(show the solution|what is the answer|how to solve it)\b', q))

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Show the solution for the practice question about {explicit_concept}."
        concept = session.active_concept or "that concept"
        return f"Show the solution for the practice question about {concept}."


class SummarizeLessonRule(FollowUpRule):
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        return bool(re.search(r'\b(summarize today\'s lesson|summarize|recap)\b', q))

    def rewrite(self, query: str, session: LearningSession) -> str:
        explicit_concept = _extract_explicit_concept(query)
        if explicit_concept:
            return f"Summarize the lesson on {explicit_concept}."
        concept = session.active_concept or "that concept"
        return f"Summarize the lesson on {concept}."


class ComputationalQueryRule(FollowUpRule):
    """Handle computational queries like 'multiply matrices', 'calculate determinant', etc."""
    def matches(self, query: str) -> bool:
        q = query.lower().strip()
        # Detect computational intent: operation verbs + numbers or matrix notation
        has_operation = bool(re.search(
            r'\b(multiply|add|subtract|divide|calculate|compute|evaluate|find|solve|determine|simplify|expand|factor|reduce)\b', q
        ))
        has_numbers = bool(re.search(r'\d+|\[|\(', q))
        return has_operation and has_numbers

    def rewrite(self, query: str, session: LearningSession) -> str:
        return f"Solve this problem: {query}"


class FollowUpResolver:
    """Deterministically rewrites vague queries into fully formed ones."""

    def __init__(self, rules: list[FollowUpRule] | None = None) -> None:
        self.rules = rules or [
            ComputationalQueryRule(),
            AnotherExampleRule(),
            ExplainAgainRule(),
            MoreExplanationRule(),
            WhatsNextRule(),
            ClarifyRule(),
            PreviousStepRule(),
            PracticeQuestionRule(),
            ShowSolutionRule(),
            SummarizeLessonRule(),
        ]

    def resolve(self, query: str, session: LearningSession) -> str:
        """Find the first matching rule and apply its rewrite; otherwise return query."""
        for rule in self.rules:
            if rule.matches(query):
                return rule.rewrite(query, session)

        # Fallback: if query is very short and session has an active concept,
        # assume the user is asking about that concept
        if session.active_concept and len(query.split()) <= 4:
            q_lower = query.lower().strip()
            # Don't add context to questions that already have a subject
            if not any(q_lower.startswith(w) for w in ['what', 'how', 'why', 'when', 'where', 'which', 'who']):
                return f"{query} about {session.active_concept}"

        return query
