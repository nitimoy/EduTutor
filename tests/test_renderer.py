"""End-to-end Renderer tests (offline, Echo). Enforces the renderer contract."""

from backend.generation.language_model import EchoLanguageModel
from backend.generation.models import GenerationConfig
from backend.generation.renderer import Renderer


def test_renders_sections_in_tutorplan_slot_order(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    kinds = [s.unit_kind.value for s in resp.sections]
    assert kinds == ["prerequisites", "main_explanation", "worked_example", "summary"]


def test_references_preserved_verbatim(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    # Citation isn't hashable (frozen model); references are preserved in order.
    assert list(resp.references) == list(tutor_plan.references)


def test_per_section_citations_preserved(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    main = next(s for s in resp.sections if s.unit_kind.value == "main_explanation")
    assert {c.concept_id for c in main.citations} == {"c1"}


def test_unit_ids_propagate_to_results(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    assert all(s.unit_id.startswith("c1::") for s in resp.sections)
    assert len({s.unit_id for s in resp.sections}) == len(resp.sections)


def test_response_is_deterministic(tutor_plan):
    model = EchoLanguageModel()
    a = Renderer().render(tutor_plan, GenerationConfig(), model).model_dump_json()
    b = Renderer().render(tutor_plan, GenerationConfig(), model).model_dump_json()
    assert a == b


def test_no_added_concepts(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    plan_ids = {c.concept_id for c in tutor_plan.references if c.concept_id}
    used = {c.concept_id for s in resp.sections for c in s.citations if c.concept_id}
    assert used.issubset(plan_ids)


def test_skipped_sections_reported(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    assert "formula" in resp.skipped_sections and "proof" in resp.skipped_sections


def test_echo_response_marked_deterministic(tutor_plan):
    resp = Renderer().render(tutor_plan, GenerationConfig(), EchoLanguageModel())
    assert resp.deterministic is True and resp.provider == "echo"


def test_build_prompt_documents_matches_render_units(tutor_plan):
    docs = Renderer().build_prompt_documents(tutor_plan, GenerationConfig())
    assert [d.unit_kind.value for d in docs] == [
        "prerequisites", "main_explanation", "worked_example", "summary"]
