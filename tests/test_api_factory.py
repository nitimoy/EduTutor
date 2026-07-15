"""Tests for EngineFactory."""

from backend.api.config import ServiceConfig
from backend.api.factory import EngineFactory
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine


def test_factory_exposes_config():
    config = ServiceConfig()
    factory = EngineFactory(config)
    assert factory.config is config


def test_factory_session_engine_is_singleton():
    factory = EngineFactory(ServiceConfig())
    a = factory.session_engine
    b = factory.session_engine
    assert a is b
    assert isinstance(a, LearningSessionEngine)


def test_factory_tutor_engine_is_singleton_when_compiled_dir_not_needed():
    """With use_repository=False and an injected strategy, tutor_engine builds successfully."""
    # We can't test the default factory without compiled data, but we can
    # verify the lazy pattern by injecting a config that doesn't require it.
    from backend.evaluation.orchestrator_eval import FakeStrategy
    from backend.generation.language_model import EchoLanguageModel
    from backend.orchestrator.config import OrchestratorConfig

    config = ServiceConfig()
    factory = EngineFactory(config)

    # Manually inject to test singleton behavior.
    oc = OrchestratorConfig(use_repository=False)
    engine = EducationalTutorEngine(
        oc, strategy=FakeStrategy(), language_model=EchoLanguageModel(),
    )
    factory._tutor_engine = engine

    a = factory.tutor_engine
    b = factory.tutor_engine
    assert a is b
    assert isinstance(a, EducationalTutorEngine)
