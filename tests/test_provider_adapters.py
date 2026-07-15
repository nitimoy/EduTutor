"""Tests for provider adapters (chat-message construction)."""

import pytest

from backend.generation.adapters import (
    ADAPTERS,
    ClaudeAdapter,
    EchoAdapter,
    GeminiAdapter,
    OpenAIAdapter,
    adapter_for,
)
from backend.generation.models import GenerationConfig, PromptBlock, PromptDocument
from backend.tutor.models import Citation, SectionKind


def _doc():
    return PromptDocument(
        unit_id="c1::main_explanation", unit_kind=SectionKind.MAIN_EXPLANATION,
        system="SYSTEM RULES", blocks=(
            PromptBlock(label="Content", lines=("C1 is the first thing.",)),
            PromptBlock(label="Citations", lines=("[C1] concept=c1 field=definition_texts locator=0",)),
        ),
        citations=(Citation(concept_id="c1", concept_name="C1",
                            source_field="definition_texts", locator="0"),))


def test_all_adapters_registered():
    assert set(ADAPTERS) == {"echo", "openai", "claude", "gemini"}


def test_adapter_for_unknown_raises():
    with pytest.raises(ValueError):
        adapter_for("mistral")


def test_openai_shape_has_system_and_user_messages():
    req = OpenAIAdapter().to_request(_doc(), GenerationConfig(model_id="gpt-x"))
    roles = [m["role"] for m in req["messages"]]
    assert roles == ["system", "user"]
    assert req["model"] == "gpt-x"
    assert "C1 is the first thing." in req["messages"][1]["content"]


def test_claude_shape_has_top_level_system():
    req = ClaudeAdapter().to_request(_doc(), GenerationConfig())
    assert req["system"] == "SYSTEM RULES"
    assert req["messages"][0]["role"] == "user"


def test_gemini_shape_has_system_instruction_and_contents():
    req = GeminiAdapter().to_request(_doc(), GenerationConfig())
    assert "systemInstruction" in req and req["contents"][0]["role"] == "user"


def test_every_adapter_preserves_content_and_citations():
    doc = _doc()
    for adapter_cls in ADAPTERS.values():
        req = adapter_cls().to_request(doc, GenerationConfig())
        blob = str(req)
        assert "C1 is the first thing." in blob  # content preserved
        assert "c1" in blob  # citation preserved


def test_adapters_are_deterministic_pure_functions():
    doc = _doc()
    for adapter_cls in ADAPTERS.values():
        a = adapter_cls().to_request(doc, GenerationConfig())
        b = adapter_cls().to_request(doc, GenerationConfig())
        assert a == b


def test_echo_adapter_roundtrips_text():
    text, finish = EchoAdapter().parse_response({"text": "hello", "finish_reason": "stop"})
    assert text == "hello" and finish == "stop"


def test_openai_parse_response():
    raw = {"choices": [{"message": {"content": "out"}, "finish_reason": "length"}]}
    assert OpenAIAdapter().parse_response(raw) == ("out", "length")
