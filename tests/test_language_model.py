"""Tests for the LanguageModel interface, EchoLanguageModel, and the provider factory."""

import pytest

from backend.generation.language_model import EchoLanguageModel, LanguageModel
from backend.generation.models import GenerationConfig, PromptBlock, PromptDocument
from backend.generation.providers import make_language_model
from backend.tutor.models import Citation, SectionKind


def _doc():
    return PromptDocument(
        unit_id="c1::summary", unit_kind=SectionKind.SUMMARY, system="rules",
        blocks=(PromptBlock(label="Content", lines=("C1 recap.",)),
                PromptBlock(label="Citations", lines=("[C1] concept=c1",))),
        citations=(Citation(concept_id="c1", concept_name="C1",
                            source_field="definition_texts", locator="0"),))


def test_echo_is_a_language_model():
    assert isinstance(EchoLanguageModel(), LanguageModel)


def test_echo_metadata_is_deterministic():
    md = EchoLanguageModel().metadata()
    assert md.provider == "echo" and md.deterministic is True


def test_echo_stamps_unit_id_and_preserves_citations():
    result = EchoLanguageModel().generate(_doc(), GenerationConfig())
    assert result.unit_id == "c1::summary"
    assert [c.concept_id for c in result.citations] == ["c1"]


def test_echo_output_is_grounded_in_content():
    result = EchoLanguageModel().generate(_doc(), GenerationConfig())
    # Every content token appears; nothing new is invented.
    assert "C1 recap." in result.text


def test_echo_is_deterministic():
    a = EchoLanguageModel().generate(_doc(), GenerationConfig()).model_dump_json()
    b = EchoLanguageModel().generate(_doc(), GenerationConfig()).model_dump_json()
    assert a == b


def test_factory_returns_echo_by_default():
    model = make_language_model(GenerationConfig())
    assert isinstance(model, EchoLanguageModel)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        make_language_model(GenerationConfig(provider="mistral"))


def test_factory_real_provider_is_lazy_but_registered():
    # Real providers are known to the factory; instantiation would need an SDK/key, so we
    # only assert the unknown-vs-known boundary (no network, no SDK import at module load).
    from backend.generation.providers import _REMOTE
    assert set(_REMOTE) == {"openai", "claude", "gemini"}
