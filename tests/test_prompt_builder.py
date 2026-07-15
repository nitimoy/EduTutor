"""Tests for the PromptBuilder (provider-neutral PromptDocument)."""

from backend.generation.models import GenerationConfig
from backend.generation.plan_builder import build_generation_plan
from backend.generation.prompt_builder import PromptBuilder


def _docs(tutor_plan):
    plan = build_generation_plan(tutor_plan)
    builder = PromptBuilder()
    return plan, [builder.build(u, plan, GenerationConfig()) for u in plan.units]


def test_document_carries_unit_id_and_kind(tutor_plan):
    plan, docs = _docs(tutor_plan)
    for unit, doc in zip(plan.units, docs):
        assert doc.unit_id == unit.unit_id and doc.unit_kind == unit.kind


def test_system_has_contract_and_no_facts(tutor_plan):
    _, docs = _docs(tutor_plan)
    system = docs[0].system
    assert "Rephrase ONLY" in system or "rephrase only" in system.lower()
    # No concept content leaks into the system prompt.
    assert "first thing" not in system.lower()


def test_content_block_holds_only_unit_content(tutor_plan):
    _, docs = _docs(tutor_plan)
    main = next(d for d in docs if d.unit_kind.value == "main_explanation")
    content = next(b for b in main.blocks if b.label == "Content")
    assert content.lines == ("C1 is the first thing.",)


def test_citations_serialized_in_a_block(tutor_plan):
    _, docs = _docs(tutor_plan)
    main = next(d for d in docs if d.unit_kind.value == "main_explanation")
    citeblock = next(b for b in main.blocks if b.label == "Citations")
    assert any("c1" in line for line in citeblock.lines)
    assert main.citations[0].concept_id == "c1"


def test_prompt_documents_are_byte_deterministic(tutor_plan):
    _, a = _docs(tutor_plan)
    _, b = _docs(tutor_plan)
    assert [d.model_dump_json() for d in a] == [d.model_dump_json() for d in b]


def test_only_unit_citations_appear(tutor_plan):
    # main_explanation cites only c1, never c2 (from another section).
    _, docs = _docs(tutor_plan)
    main = next(d for d in docs if d.unit_kind.value == "main_explanation")
    assert {c.concept_id for c in main.citations} == {"c1"}
