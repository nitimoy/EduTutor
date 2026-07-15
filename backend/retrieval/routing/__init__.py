"""Deterministic adaptive retrieval routing.

A rule engine that inspects observable query characteristics (interrogative form,
quoted phrases, mathematical notation, exact-concept-name overlap with the index
vocabulary, length) and picks a retrieval strategy per query. No ML, no LLM, no
training, no hardcoded educational concepts — routing rules are text-pattern
predicates that generalize across subjects.
"""

from backend.retrieval.routing.analyzer import QueryFeatures, analyze_query
from backend.retrieval.routing.rules import (
    POLICIES,
    RoutingRule,
    build_policy,
)
from backend.retrieval.routing.router import AdaptiveRouterStrategy, RoutingDecision

__all__ = [
    "QueryFeatures",
    "analyze_query",
    "RoutingRule",
    "POLICIES",
    "build_policy",
    "AdaptiveRouterStrategy",
    "RoutingDecision",
]
