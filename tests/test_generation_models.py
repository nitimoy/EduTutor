"""Tests for the generation Prompt IR / config / result models."""

import pytest
from pydantic import ValidationError

from backend.generation.models import (
    GenerationConfig,
    GenerationResult,
    PromptBlock,
    PromptDocument,
    RenderUnit,
    RenderedResponse,
    StyleDirective,
)
from backend.tutor.models import Citation, SectionKind


def _cit():
    return Citation(concept_id="c1", concept_name="C1", source_field="definition_texts", locator="0")


def test_config_defaults_are_offline_and_deterministic():
    c = GenerationConfig()
    assert c.provider == "echo" and c.temperature == 0.0 and c.seed == 0


def test_render_unit_is_immutable():
    u = RenderUnit(unit_id="u1", kind=SectionKind.SUMMARY)
    with pytest.raises((ValidationError, TypeError)):
        u.unit_id = "u2"


def test_prompt_document_is_immutable():
    d = PromptDocument(unit_id="u1", unit_kind=SectionKind.SUMMARY, system="s")
    with pytest.raises((ValidationError, TypeError)):
        d.system = "x"


def test_generation_result_carries_unit_id_and_citations():
    doc = PromptDocument(unit_id="c1::summary", unit_kind=SectionKind.SUMMARY, system="s",
                         citations=(_cit(),))
    r = GenerationResult(unit_id=doc.unit_id, unit_kind=doc.unit_kind, prompt=doc,
                         text="hi", citations=(_cit(),))
    assert r.unit_id == "c1::summary" and len(r.citations) == 1


def test_rendered_response_roundtrip():
    resp = RenderedResponse(query="q", text="t", references=(_cit(),))
    restored = RenderedResponse.model_validate_json(resp.model_dump_json())
    assert restored == resp


def test_style_directive_defaults():
    s = StyleDirective()
    assert s.max_sentences is None and s.tone and s.format


def test_prompt_block_holds_lines():
    b = PromptBlock(label="Content", lines=("a", "b"))
    assert b.lines == ("a", "b")
