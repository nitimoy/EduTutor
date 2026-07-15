"""Parser package."""

from backend.compiler.parser.base import Parser, register_parser
from backend.compiler.parser.pymupdf_parser import PyMuPDFParser
from backend.compiler.parser.marker_parser import MarkerParser
from backend.compiler.parser.docling_parser import DoclingParser

__all__ = [
    "Parser",
    "register_parser",
    "PyMuPDFParser",
    "MarkerParser",
    "DoclingParser",
]
