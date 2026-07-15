"""Guards the Phase 3.4.1 sweep harness's in-line metric computation.

The sweep (scripts/hybrid_optimize.py) recomputes metrics itself for speed (to
re-fuse the whole k×weight grid from cached candidate lists). These tests pin that
computation to hand-verified values and to the frozen evaluation engine's formulas,
so a divergence is caught here rather than silently skewing the sweep.
"""

import math

import pytest

from scripts.hybrid_optimize import _metrics, evaluate_combo


def test_metrics_single_relevant_at_rank_2():
    m = _metrics(["x", "target", "y"], {"target"}, {"target": {"target"}})
    assert m["overall_mrr"] == 0.5
    assert m["overall_recall_at_1"] == 0.0
    assert m["overall_recall_at_3"] == 1.0
    assert m["overall_recall_at_5"] == 1.0
    assert m["overall_precision_at_3"] == pytest.approx(1 / 3)
    # nDCG@5: relevant at rank 2 -> dcg = 1/log2(3); idcg (1 relevant) = 1/log2(2)=1
    assert m["overall_ndcg_at_5"] == pytest.approx((1 / math.log2(3)) / 1.0)


def test_metrics_relevant_at_rank_1_is_perfect():
    m = _metrics(["target", "x"], {"target"}, {"target": {"target"}})
    assert m["overall_mrr"] == 1.0
    assert m["overall_recall_at_1"] == 1.0
    assert m["overall_ndcg_at_5"] == 1.0


def test_metrics_no_relevant_is_zero():
    m = _metrics(["x", "y"], {"target"}, {"target": {"target"}})
    assert m["overall_mrr"] == 0.0
    assert m["overall_recall_at_5"] == 0.0
    assert m["overall_ndcg_at_5"] == 0.0


def test_evaluate_combo_shape_and_ranges():
    # Two fake queries: one where dense is right, one where bm25 is right.
    data = {
        "sub": {
            "rows": [
                ({"a"}, ["b", "a"], ["a", "b"]),  # dense#1=a, bm25#2=a
                ({"c"}, ["c", "d"], ["d", "c"]),  # bm25#1=c, dense#2=c
            ],
            "id_to_norms": {"a": {"a"}, "b": {"b"}, "c": {"c"}, "d": {"d"}},
        }
    }
    macro, per_subject = evaluate_combo(data, k=60, w_dense=1.0, w_bm25=1.0)
    assert set(per_subject) == {"sub"}
    for v in macro.values():
        assert 0.0 <= v <= 1.0
    # Weighting dense higher should not crash and stays in range.
    macro2, _ = evaluate_combo(data, k=60, w_dense=2.0, w_bm25=1.0)
    assert 0.0 <= macro2["overall_mrr"] <= 1.0
