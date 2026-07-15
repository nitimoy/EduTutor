"""Orchestrator configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.generation.models import GenerationConfig
from backend.verification.config import VerificationConfig


class OrchestratorConfig(BaseModel):
    """How the engine builds its components and behaves on a failing verdict.

    ``compiled_dir`` is only needed for components the caller does not inject. The default
    stack is fully offline (BM25F retrieval + Echo generation).
    """

    compiled_dir: Optional[Path] = None
    retrieval_strategy: Literal["bm25f"] = "bm25f"
    top_k: int = 5
    use_repository: bool = True
    style_preset: str = "default"
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    strict_verification: bool = False
