"""Tests for building a LanguageGenerationPlan from a TutorPlan."""

from backend.generation.plan_builder import (
    build_generation_plan,
    make_unit_id,
    skipped_section_kinds,
)


def test_only_present_sections_in_slot_order(tutor_plan):
    plan = build_generation_plan(tutor_plan)
    kinds = [u.kind.value for u in plan.units]
    assert kinds == ["prerequisites", "main_explanation", "worked_example", "summary"]


def test_empty_and_unsupported_sections_skipped(tutor_plan):
    plan = build_generation_plan(tutor_plan)
    rendered = {u.kind.value for u in plan.units}
    assert "formula" not in rendered and "proof" not in rendered


def test_content_and_citations_carried_verbatim(tutor_plan):
    plan = build_generation_plan(tutor_plan)
    main = next(u for u in plan.units if u.kind.value == "main_explanation")
    assert main.content_lines == ("C1 is the first thing.",)
    assert [c.concept_id for c in main.citations] == ["c1"]


def test_unit_ids_are_unique_and_stable(tutor_plan):
    a = [u.unit_id for u in build_generation_plan(tutor_plan).units]
    b = [u.unit_id for u in build_generation_plan(tutor_plan).units]
    assert a == b and len(set(a)) == len(a)


def test_make_unit_id_is_deterministic():
    assert make_unit_id("c1", "summary") == "c1::summary"
    assert make_unit_id(None, "summary") == "plan::summary"


def test_generation_plan_is_deterministic(tutor_plan):
    a = build_generation_plan(tutor_plan).model_dump_json()
    b = build_generation_plan(tutor_plan).model_dump_json()
    assert a == b


def test_skipped_sections_reported(tutor_plan):
    skipped = skipped_section_kinds(tutor_plan)
    assert "formula" in skipped and "proof" in skipped
    assert "main_explanation" not in skipped
