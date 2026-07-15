"""Graph-integrity tests for the Canonical Concept Layer.

Verifies that the concept parent graph is always a forest (no cycles), has no
dangling parent pointers, and keeps sub_concept_ids consistent with parent_id —
the invariants relied on by the reasoning/prerequisite layers.
"""

from backend.semantic.concepts.concept_builder import (
    _break_parent_cycles,
    _prune_dangling_parents,
    _rebuild_sub_concepts,
)
from backend.semantic.concepts.concept_models import Concept


def _concept(cid: str, parent_id: str | None = None) -> Concept:
    return Concept(
        id=cid,
        name=cid,
        subject="mathematics",
        book="Test",
        chapter="Chapter 1",
        parent_id=parent_id,
    )


def _enforce(concepts: dict[str, Concept]) -> None:
    _prune_dangling_parents(concepts)
    _break_parent_cycles(concepts)
    _rebuild_sub_concepts(concepts)


def _has_cycle(concepts: dict[str, Concept]) -> bool:
    for start in concepts:
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None and cur in concepts:
            if cur in seen:
                return True
            seen.add(cur)
            cur = concepts[cur].parent_id
    return False


def test_two_node_cycle_is_broken():
    concepts = {"a": _concept("a", "b"), "b": _concept("b", "a")}
    _enforce(concepts)
    assert not _has_cycle(concepts)


def test_three_node_cycle_is_broken():
    concepts = {
        "a": _concept("a", "b"),
        "b": _concept("b", "c"),
        "c": _concept("c", "a"),
    }
    _enforce(concepts)
    assert not _has_cycle(concepts)


def test_dangling_parent_is_cleared():
    concepts = {"a": _concept("a", "ghost")}
    _enforce(concepts)
    assert concepts["a"].parent_id is None


def test_no_self_parent_survives():
    concepts = {"a": _concept("a", "a")}
    _enforce(concepts)
    assert concepts["a"].parent_id is None
    assert not _has_cycle(concepts)


def test_sub_concepts_match_parents_and_are_sorted():
    concepts = {
        "root": _concept("root", None),
        "z": _concept("z", "root"),
        "a": _concept("a", "root"),
    }
    _enforce(concepts)
    assert concepts["root"].sub_concept_ids == ["a", "z"]  # sorted, deterministic
    assert concepts["a"].sub_concept_ids == []


def test_valid_forest_is_left_intact():
    concepts = {
        "root": _concept("root", None),
        "child": _concept("child", "root"),
        "grandchild": _concept("grandchild", "child"),
    }
    _enforce(concepts)
    assert concepts["child"].parent_id == "root"
    assert concepts["grandchild"].parent_id == "child"
    assert not _has_cycle(concepts)
