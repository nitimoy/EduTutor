"""Engine factory — the only place that builds educational engine instances.

Route handlers never instantiate ``EducationalTutorEngine`` or
``LearningSessionEngine`` directly. They receive engines through FastAPI dependency
injection, which delegates to this factory. The factory is created once during
application lifespan and stored in ``app.state``.
"""

from __future__ import annotations

from backend.api.config import ServiceConfig
from backend.orchestrator.engine import EducationalTutorEngine
from backend.session.engine import LearningSessionEngine
from backend.session.manager import SessionManager
from backend.session.resolver import FollowUpResolver
from backend.session.store import InMemorySessionStore, SQLiteSessionStore


class EngineFactory:
    """Builds and caches the educational engines from a ``ServiceConfig``.

    Engines are constructed lazily on first access and reused for the lifetime of
    the factory (i.e. the lifetime of the application).
    """

    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._tutor_engine: EducationalTutorEngine | None = None
        self._session_engine: LearningSessionEngine | None = None
        self._session_manager: SessionManager | None = None
        self._session_store = SQLiteSessionStore("data/sessions.db")
        self._session_resolver = FollowUpResolver()

    @property
    def config(self) -> ServiceConfig:
        return self._config

    @property
    def tutor_engine(self) -> EducationalTutorEngine:
        if self._tutor_engine is None:
            oc = self._config.to_orchestrator_config()
            kwargs = {}
            # Use Cerebras for both v1 and v2
            from backend.integrations.openrouter import OpenRouterLanguageModel
            kwargs["language_model"] = OpenRouterLanguageModel(
                model_id=oc.generation.model_id,
                api_key=self._config.api_key,
                base_url="https://api.cerebras.ai/v1",
            )
            # Try to build hybrid retrieval strategy (BM25F + Dense)
            strategy = self._build_hybrid_strategy(oc)
            if strategy:
                kwargs["strategy"] = strategy
            self._tutor_engine = EducationalTutorEngine(oc, **kwargs)
        return self._tutor_engine

    def _build_hybrid_strategy(self, oc):
        """Build retrieval strategy - BM25F primary with dense fallback for semantic queries."""
        try:
            from pathlib import Path
            from backend.retrieval.strategies.bm25f import BM25FRetrievalStrategy

            compiled_dir = Path(oc.compiled_dir) if oc.compiled_dir else Path("data/compiled")
            if not compiled_dir.exists():
                return None

            # Use BM25F as primary - it's more reliable for exact matches
            # The dense retrieval was causing wrong results for proof queries
            bm25f = BM25FRetrievalStrategy(compiled_dir)
            return bm25f

        except Exception as e:
            print(f"Warning: Could not build retrieval strategy: {e}")
            return None

    @property
    def session_engine(self) -> LearningSessionEngine:
        if self._session_engine is None:
            self._session_engine = LearningSessionEngine()
        return self._session_engine

    @property
    def session_manager(self) -> SessionManager:
        if self._session_manager is None:
            self._session_manager = SessionManager(
                engine=self.tutor_engine,
                store=self._session_store,
                resolver=self._session_resolver,
            )
        return self._session_manager
