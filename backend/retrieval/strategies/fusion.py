"""Reciprocal Rank Fusion (RRF).

Pure, deterministic rank-fusion with no learned weights, ML, or model calls. Kept
independent of the retrieval strategies so it is unit-testable in isolation and
reusable by any future fusion consumer.

Standard formula, for a document d appearing across N ranked lists::

    score(d) = Σ_i  w_i / (k + rank_i(d))

where ``rank_i(d)`` is d's 1-based rank in list i (a list that does not contain d
contributes nothing), ``k`` (default 60) damps the influence of low ranks, and
``w_i`` is an optional per-list weight (all 1.0 by default = standard RRF). Weights
are fixed configuration constants, not learned.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[str]],
    k: int = DEFAULT_RRF_K,
    weights: Optional[Sequence[float]] = None,
) -> list[tuple[str, float]]:
    """Fuse several ranked id lists into one, highest RRF score first.

    Args:
        ranked_lists: each an ordered list of document ids (rank 1 = index 0).
            Duplicate ids within a single list are ignored after their first
            (best) occurrence, so a document is counted at most once per list.
        k: RRF damping constant (must be > 0).
        weights: optional per-list multipliers ``w_i``. Length must match the
            number of ranked lists. Defaults to all 1.0 (standard, equal-weight
            RRF). Weights are fixed constants — no learning.

    Returns:
        ``(id, score)`` pairs sorted by score descending, then id ascending for a
        deterministic, hash-independent tie-break.
    """
    if k <= 0:
        raise ValueError("RRF k must be positive")

    lists = list(ranked_lists)
    if weights is None:
        weights = [1.0] * len(lists)
    elif len(weights) != len(lists):
        raise ValueError(
            f"weights length {len(weights)} != number of ranked lists {len(lists)}"
        )

    scores: dict[str, float] = {}
    for ranked, weight in zip(lists, weights):
        seen: set[str] = set()
        for index, doc_id in enumerate(ranked):
            if doc_id in seen:
                continue  # keep only the best rank for a duplicated id in one list
            seen.add(doc_id)
            rank = index + 1
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
