"""Deterministic routing rules and named policies.

A routing rule is ``(name, predicate, target)``: if ``predicate(features)`` is
True, route to strategy ``target``. Rules are evaluated in precedence order and the
first match wins; if none match, the policy's default strategy is used. Rules are
pure functions of :class:`QueryFeatures` — deterministic and generalizable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.retrieval.routing.analyzer import QueryFeatures

# Strategy identifiers the router can select.
STRATEGY_BM25F = "bm25f"
STRATEGY_DENSE = "dense"
STRATEGY_HYBRID = "hybrid"


@dataclass(frozen=True)
class RoutingRule:
    """A single precedence-ordered routing rule."""

    name: str
    predicate: Callable[[QueryFeatures], bool]
    target: str


@dataclass(frozen=True)
class RoutingPolicy:
    """An ordered list of rules plus a default strategy."""

    name: str
    rules: tuple[RoutingRule, ...]
    default: str


# --- Predicates (named for clear error-analysis output) ----------------------
def _is_exact_concept(f: QueryFeatures) -> bool:
    return f.exact_concept_match


def _is_quoted(f: QueryFeatures) -> bool:
    return f.has_quoted_phrase


def _is_math(f: QueryFeatures) -> bool:
    return f.has_math_notation


def _is_definition(f: QueryFeatures) -> bool:
    return f.is_definition


def _is_explanation(f: QueryFeatures) -> bool:
    return f.is_explanation


def _is_comparison(f: QueryFeatures) -> bool:
    return f.is_comparison


# --- Named candidate policies (from the sprint brief, generalized) ------------
# Policy A: exact concept / quoted / math -> BM25F (lexical); everything else Dense.
_POLICY_A = RoutingPolicy(
    name="A_exact_to_bm25f",
    rules=(
        RoutingRule("exact_concept->bm25f", _is_exact_concept, STRATEGY_BM25F),
        RoutingRule("quoted_phrase->bm25f", _is_quoted, STRATEGY_BM25F),
        RoutingRule("math_notation->bm25f", _is_math, STRATEGY_BM25F),
    ),
    default=STRATEGY_DENSE,
)

# Policy B: formula/math or comparison -> BM25F; explanation/definition -> Dense.
_POLICY_B = RoutingPolicy(
    name="B_formula_bm25f_explain_dense",
    rules=(
        RoutingRule("math_notation->bm25f", _is_math, STRATEGY_BM25F),
        RoutingRule("comparison->dense", _is_comparison, STRATEGY_DENSE),
        RoutingRule("explanation->dense", _is_explanation, STRATEGY_DENSE),
        RoutingRule("definition->dense", _is_definition, STRATEGY_DENSE),
    ),
    default=STRATEGY_DENSE,
)

# Policy C: exact concept -> BM25F; definition -> Dense; otherwise Dense.
_POLICY_C = RoutingPolicy(
    name="C_exact_bm25f_else_dense",
    rules=(
        RoutingRule("exact_concept->bm25f", _is_exact_concept, STRATEGY_BM25F),
        RoutingRule("definition->dense", _is_definition, STRATEGY_DENSE),
    ),
    default=STRATEGY_DENSE,
)

# Policy D: like A but exact/quoted -> Hybrid (fuse) instead of pure BM25F, to keep
# dense recall while adding the lexical anchor.
_POLICY_D = RoutingPolicy(
    name="D_exact_to_hybrid",
    rules=(
        RoutingRule("exact_concept->hybrid", _is_exact_concept, STRATEGY_HYBRID),
        RoutingRule("quoted_phrase->hybrid", _is_quoted, STRATEGY_HYBRID),
        RoutingRule("math_notation->hybrid", _is_math, STRATEGY_HYBRID),
    ),
    default=STRATEGY_DENSE,
)

POLICIES: dict[str, RoutingPolicy] = {
    p.name: p for p in (_POLICY_A, _POLICY_B, _POLICY_C, _POLICY_D)
}


def build_policy(name: str) -> RoutingPolicy:
    """Look up a named policy."""
    if name not in POLICIES:
        raise ValueError(f"Unknown routing policy '{name}'. Known: {sorted(POLICIES)}")
    return POLICIES[name]
