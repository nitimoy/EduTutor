"""Abstract base class and registry for PDF parsers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, ClassVar

from backend.compiler.config import ParserConfig
from backend.compiler.models import EducationalObject, ParserOutput, Subject

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[Parser]] = {}


def register_parser(name: str) -> Callable[[type[Parser]], type[Parser]]:
    """Class decorator factory that registers a parser implementation by name.

    Usage:
        @register_parser("marker")
        class MarkerParser(Parser):
            ...
    """

    def _decorator(parser_class: type[Parser]) -> type[Parser]:
        _REGISTRY[name] = parser_class
        logger.debug("Registered parser %s", name)
        return parser_class

    return _decorator


def get_parser(name: str) -> type[Parser]:
    """Return a parser class by registered name."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown parser: {name}")
    return _REGISTRY[name]


def list_parsers() -> list[str]:
    """Return all registered parser names."""
    return list(_REGISTRY.keys())


class Parser(ABC):
    """Abstract parser that converts a PDF into structured parser output."""

    name: ClassVar[str] = "base"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    @property
    def version(self) -> str:
        """Version string of the underlying parsing library. Override per adapter."""
        return "unknown"

    @abstractmethod
    def parse(
        self,
        pdf_path: Path,
        subject: Subject,
        book_title: str,
        part: str | None = None,
    ) -> ParserOutput:
        """Parse a PDF and return structured output."""

    def is_available(self) -> bool:
        """Return True if the parser can be used in this environment."""
        return True

    def _stamp_provenance(self, objects: list[EducationalObject]) -> None:
        """Record which parser (and version) produced each object."""
        for obj in objects:
            obj.parser_name = self.name
            obj.parser_version = self.version


class ParserBase(Parser):
    """Concrete base that can be subclassed without redefining __init__."""

    def __init__(self, config: ParserConfig | None = None) -> None:
        super().__init__(config)

    def parse(
        self,
        pdf_path: Path,
        subject: Subject,
        book_title: str,
        part: str | None = None,
    ) -> ParserOutput:
        raise NotImplementedError("Subclasses must implement parse()")
