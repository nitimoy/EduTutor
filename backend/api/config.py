"""Service-layer configuration.

``ServiceConfig`` is the single source of truth for the API server. It reads from
environment variables (and ``.env``), then maps down to the frozen
``OrchestratorConfig`` / ``GenerationConfig`` / ``VerificationConfig`` via
``to_orchestrator_config()``. The service layer never reads env vars directly — it
always goes through this config object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings

from backend.generation.models import GenerationConfig
from backend.orchestrator.config import OrchestratorConfig
from backend.verification.config import VerificationConfig


class ServiceConfig(BaseSettings):
    """Flat, environment-driven service configuration.

    Every field maps to an environment variable of the same name (case-insensitive).
    The ``to_orchestrator_config()`` method assembles the frozen config objects that
    the educational engine expects.
    """

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- data paths -----------------------------------------------------------
    compiled_dir: Optional[Path] = None

    # --- retrieval ------------------------------------------------------------
    retrieval_strategy: str = "bm25f"
    top_k: int = 5
    use_repository: bool = True

    # --- generation -----------------------------------------------------------
    provider: str = "auto"
    model_id: str = Field("openrouter/auto", validation_alias=AliasChoices("LLM_MODEL", "MODEL_ID"))
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    seed: int = 0
    style_preset: str = "default"

    # --- verification ---------------------------------------------------------
    # Thresholds are relaxed for real LLMs that rephrase content naturally.
    # Echo model passes at 1.0; real providers need ~0.7 headroom.
    strict_verification: bool = False
    min_grounding_coverage: float = 0.7
    min_completeness: float = 0.7

    # --- service --------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # LLM API configuration — supports multiple providers via env vars.
    # Change these in .env to switch providers:
    #   Cerebras: CEREBRAS_API_KEY + CEREBRAS_BASE_URL
    #   OpenAI:   OPENAI_API_KEY + OPENAI_BASE_URL
    #   Custom:   LLM_API_KEY + LLM_BASE_URL
    api_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("LLM_API_KEY", "CEREBRAS_API_KEY", "OPENAI_API_KEY"),
    )
    base_url: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("LLM_BASE_URL", "CEREBRAS_BASE_URL", "OPENAI_BASE_URL"),
    )

    # --- version --------------------------------------------------------------
    api_version: str = "8.0.0"

    def to_orchestrator_config(self) -> OrchestratorConfig:
        """Build the frozen ``OrchestratorConfig`` from flat service settings."""
        return OrchestratorConfig(
            compiled_dir=self.compiled_dir,
            retrieval_strategy=self.retrieval_strategy,
            top_k=self.top_k,
            use_repository=self.use_repository,
            style_preset=self.style_preset,
            generation=GenerationConfig(
                provider=self.provider,
                model_id=self.model_id,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                seed=self.seed,
                style_preset=self.style_preset,
            ),
            verification=VerificationConfig(
                min_grounding_coverage=self.min_grounding_coverage,
                min_completeness=self.min_completeness,
            ),
            strict_verification=self.strict_verification,
        )

    def public_summary(self) -> dict[str, object]:
        """Non-secret subset for the ``/config`` endpoint."""
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "retrieval_strategy": self.retrieval_strategy,
            "top_k": self.top_k,
            "use_repository": self.use_repository,
            "style_preset": self.style_preset,
            "strict_verification": self.strict_verification,
            "compiled_dir": str(self.compiled_dir) if self.compiled_dir else None,
            "api_version": self.api_version,
        }
