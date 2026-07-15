"""Configuration for the educational compiler pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field


DEFAULT_RAW_DIR: Final[Path] = Path("data/raw")
DEFAULT_COMPILED_DIR: Final[Path] = Path("data/compiled")
DEFAULT_DB_PATH: Final[Path] = Path("data/compiler.db")
DEFAULT_CONFIDENCE_THRESHOLD: Final[float] = 0.5


class ParserConfig(BaseModel):
    """Per-parser configuration."""

    enabled: bool = True
    timeout_seconds: int = 600
    extra_args: dict[str, str | int | float | bool] = Field(default_factory=dict)


class CompilerConfig(BaseModel):
    """Top-level compiler configuration."""

    raw_dir: Path = DEFAULT_RAW_DIR
    compiled_dir: Path = DEFAULT_COMPILED_DIR
    db_path: Path = DEFAULT_DB_PATH
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    parsers: dict[str, ParserConfig] = Field(
        default_factory=lambda: {
            "pymupdf": ParserConfig(enabled=True),
            "marker": ParserConfig(enabled=False),
            "docling": ParserConfig(enabled=False),
        }
    )
    log_level: str = "INFO"

    class Config:
        arbitrary_types_allowed = True
