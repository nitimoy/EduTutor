"""Educational compiler pipeline CLI."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from backend.compiler.config import CompilerConfig, ParserConfig
from backend.compiler.exporter import JsonExporter, SQLiteExporter
from backend.compiler.merger import MergeEngine
from backend.compiler.models import ParserOutput, Subject
from backend.compiler.parser import DoclingParser, MarkerParser, PyMuPDFParser
from backend.compiler.validator.validator import Validator
from backend.semantic.concepts.concept_builder import ConceptBuilder
from backend.semantic.concepts.concept_filter import ConceptFilter
from backend.semantic.concepts.concept_exporter import (
    ConceptJsonExporter,
    ConceptSQLiteExporter,
)
from backend.semantic.concepts.concept_validator import ConceptValidator
from backend.semantic.relationships.relationship_engine import RelationshipEngine
from backend.semantic.relationships.relationship_exporter import (
    RelationshipJsonExporter,
    RelationshipSQLiteExporter,
)
from backend.semantic.reasoning.reasoning_engine import ReasoningEngine
from backend.semantic.reasoning.reasoning_exporter import (
    ReasoningJsonExporter,
    ReasoningSQLiteExporter,
)
from backend.retrieval.index.builder import KnowledgeIndexBuilder
from backend.retrieval.index.exporter import KnowledgeIndexExporter

logger = logging.getLogger(__name__)


# Mapping from filename / manifest subject to canonical subject.
SUBJECT_ALIASES: dict[str, Subject] = {
    "math": "mathematics",
    "mathematics": "mathematics",
    "phy": "physics",
    "physics": "physics",
    "chem": "chemistry",
    "chemistry": "chemistry",
}


def _detect_subject(pdf_path: Path) -> Subject:
    """Detect subject from filename."""
    lower = pdf_path.stem.lower()
    for alias, subject in SUBJECT_ALIASES.items():
        if alias in lower:
            return subject
    logger.warning("Could not detect subject for %s; defaulting to mathematics", pdf_path)
    return "mathematics"


def _detect_book_title(pdf_path: Path, subject: Subject) -> str:
    """Produce a readable book title from filename."""
    stem = pdf_path.stem.replace("_", " ").replace("-", " ").title()
    return f"{stem}"


def _load_manifest(raw_dir: Path) -> dict[str, dict[str, str]]:
    """Load manifest and map suggested filename → book metadata."""
    manifest_path = Path("data/manifest.json")
    if not manifest_path.exists():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    mapping: dict[str, dict[str, str]] = {}
    for book in data.get("books", []):
        filename = book.get("suggested_filename", "")
        if filename:
            mapping[filename] = book
    return mapping


def _run_parser_stage(
    pdf_path: Path,
    config: CompilerConfig,
) -> dict[str, ParserOutput]:
    """Run enabled parsers and return their outputs."""
    subject = _detect_subject(pdf_path)
    manifest = _load_manifest(config.raw_dir)
    book_meta = manifest.get(pdf_path.name, {})
    book_title = book_meta.get("book") or _detect_book_title(pdf_path, subject)
    part = book_meta.get("part")

    outputs: dict[str, ParserOutput] = {}

    if config.parsers.get("pymupdf", ParserConfig()).enabled:
        parser = PyMuPDFParser(config.parsers.get("pymupdf", ParserConfig()))
        if parser.is_available():
            outputs["pymupdf"] = parser.parse(pdf_path, subject, book_title, part)
        else:
            logger.error("PyMuPDF parser is not available")

    if config.parsers.get("marker", ParserConfig()).enabled:
        parser = MarkerParser(config.parsers.get("marker", ParserConfig()))
        if parser.is_available():
            outputs["marker"] = parser.parse(pdf_path, subject, book_title, part)
        else:
            logger.warning("Marker parser is not available; install marker-pdf to enable")

    if config.parsers.get("docling", ParserConfig()).enabled:
        parser = DoclingParser(config.parsers.get("docling", ParserConfig()))
        if parser.is_available():
            outputs["docling"] = parser.parse(pdf_path, subject, book_title, part)
        else:
            logger.warning("Docling parser is not available; install docling to enable")

    if not outputs:
        raise RuntimeError("No parsers produced output")

    return outputs


def _run_merge_stage(outputs: dict[str, ParserOutput]) -> object:
    """Merge parser outputs into a single Educational IR."""
    engine = MergeEngine()
    return engine.merge(outputs)


def _run_validate_stage(ir: object, config: CompilerConfig) -> object:
    """Validate the merged IR."""
    validator = Validator(confidence_threshold=config.confidence_threshold)
    return validator.validate(ir)


def _run_concepts_stage(ir: object, config: CompilerConfig) -> object:
    """Discover canonical concepts and link objects."""
    builder = ConceptBuilder()
    index = builder.build(ir)
    
    filter_engine = ConceptFilter()
    filtered_index = filter_engine.filter(index, ir)
    
    validator = ConceptValidator()
    concept_report = validator.validate(filtered_index, ir)
    logger.info(
        "Concepts: %d discovered, %d valid, %d orphan",
        concept_report.total_concepts,
        concept_report.valid_concepts,
        concept_report.orphan_concepts,
    )
    return filtered_index


def _run_relationships_stage(ir: object, concept_index: object) -> object:
    """Infer semantic relationships between entities."""
    engine = RelationshipEngine()
    index = engine.build(ir, concept_index)
    logger.info("Relationships: %d inferred", len(index.relationships))
    return index


def _run_reasoning_stage(ir: object, concept_index: object, relationship_index: object) -> object:
    """Run educational reasoning heuristics."""
    engine = ReasoningEngine()
    index = engine.build(ir, concept_index, relationship_index)
    logger.info("Reasoning: Computed intelligence for %d concepts", len(index.concept_reasoning))
    return index


def _run_export_stage(
    ir: object, config: CompilerConfig, subject: Subject, book_slug: str, concept_index: object = None, relationship_index: object = None, reasoning_index: object = None
) -> dict[str, Path]:
    """Export IR to JSON and SQLite.

    Each source PDF gets its own subdirectory (keyed by `book_slug`, e.g. the
    PDF's filename stem) so that a subject with multiple book parts (NCERT
    Math/Physics/Chemistry each ship as Part-I + Part-II) doesn't have one
    part's export silently overwrite the other's.
    """
    output_dir = config.compiled_dir / subject / book_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    json_exporter = JsonExporter(output_dir)
    paths = json_exporter.export(ir)

    sqlite_exporter = SQLiteExporter(config.db_path)
    sqlite_exporter.export(ir)

    if concept_index is not None:
        concept_json = ConceptJsonExporter(output_dir)
        concept_paths = concept_json.export(concept_index)
        paths.update(concept_paths)

        concept_sqlite = ConceptSQLiteExporter(config.db_path)
        concept_sqlite.export(concept_index)

    if relationship_index is not None:
        rel_json = RelationshipJsonExporter(output_dir)
        rel_paths = rel_json.export(relationship_index)
        paths.update(rel_paths)

        rel_sqlite = RelationshipSQLiteExporter(config.db_path)
        rel_sqlite.export(relationship_index)

    if reasoning_index is not None:
        reason_json = ReasoningJsonExporter(output_dir)
        reason_paths = reason_json.export(reasoning_index)
        paths.update(reason_paths)

        reason_sqlite = ReasoningSQLiteExporter(config.db_path)
        reason_sqlite.export(reasoning_index)

    # Knowledge Index: build the flattened, self-contained retrieval documents
    # as the final export step so every compiled book ships a ready-to-search
    # index in its canonical directory. Requires all three semantic indices.
    if (
        concept_index is not None
        and relationship_index is not None
        and reasoning_index is not None
    ):
        knowledge_index = KnowledgeIndexBuilder().build(
            ir, concept_index, relationship_index, reasoning_index
        )
        knowledge_exporter = KnowledgeIndexExporter()
        knowledge_exporter.export_json(knowledge_index, output_dir)
        knowledge_exporter.export_sqlite(
            knowledge_index, output_dir / "knowledge_index.db"
        )
        paths["knowledge_index"] = output_dir / "knowledge_index.json"
        paths["knowledge_index_db"] = output_dir / "knowledge_index.db"

    return paths


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Educational Knowledge Compiler")
    parser.add_argument("pdf", type=Path, help="Path to the PDF to compile")
    parser.add_argument(
        "--stage",
        choices=["parse", "merge", "validate", "concepts", "relationships", "reasoning", "export", "all"],
        default="all",
        help="Run a single stage or the full pipeline",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a JSON config file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override compiled output directory",
    )
    args = parser.parse_args(argv)

    config = CompilerConfig()
    if args.config:
        config = CompilerConfig.model_validate_json(args.config.read_text())
    if args.output_dir:
        config.compiled_dir = args.output_dir

    _setup_logging(config.log_level)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return 1

    subject = _detect_subject(pdf_path)

    if args.stage == "parse":
        outputs = _run_parser_stage(pdf_path, config)
        for name, output in outputs.items():
            print(f"{name}: {len(output.objects)} objects")
        return 0

    if args.stage == "merge":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        print(f"Merged IR: {len(ir.book.objects)} objects")
        return 0

    if args.stage == "validate":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        report = _run_validate_stage(ir, config)
        print(f"Validation: {report.valid_objects} valid, {report.flagged_objects} flagged")
        return 0

    if args.stage == "concepts":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        _run_validate_stage(ir, config)
        concept_index = _run_concepts_stage(ir, config)
        print(f"Concepts: {len(concept_index.concepts)} discovered")
        print(f"References: {len(concept_index.references)} links")
        print(f"Unlinked: {len(concept_index.unlinked_object_ids)} objects")
        return 0

    if args.stage == "relationships":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        _run_validate_stage(ir, config)
        concept_index = _run_concepts_stage(ir, config)
        relationship_index = _run_relationships_stage(ir, concept_index)
        print(f"Relationships: {len(relationship_index.relationships)} inferred")
        return 0

    if args.stage == "reasoning":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        _run_validate_stage(ir, config)
        concept_index = _run_concepts_stage(ir, config)
        relationship_index = _run_relationships_stage(ir, concept_index)
        reasoning_index = _run_reasoning_stage(ir, concept_index, relationship_index)
        print(f"Reasoning: Computed intelligence for {len(reasoning_index.concept_reasoning)} concepts")
        return 0

    if args.stage == "export":
        outputs = _run_parser_stage(pdf_path, config)
        ir = _run_merge_stage(outputs)
        _run_validate_stage(ir, config)
        concept_index = _run_concepts_stage(ir, config)
        relationship_index = _run_relationships_stage(ir, concept_index)
        reasoning_index = _run_reasoning_stage(ir, concept_index, relationship_index)
        paths = _run_export_stage(ir, config, subject, pdf_path.stem, concept_index, relationship_index, reasoning_index)
        for key, path in paths.items():
            print(f"{key}: {path}")
        return 0

    # all
    outputs = _run_parser_stage(pdf_path, config)
    ir = _run_merge_stage(outputs)
    report = _run_validate_stage(ir, config)
    concept_index = _run_concepts_stage(ir, config)
    relationship_index = _run_relationships_stage(ir, concept_index)
    reasoning_index = _run_reasoning_stage(ir, concept_index, relationship_index)
    paths = _run_export_stage(ir, config, subject, pdf_path.stem, concept_index, relationship_index, reasoning_index)

    print(f"Compiled {pdf_path} -> {subject}")
    print(f"Objects: {len(ir.book.objects)}")
    print(f"Formulas: {len(ir.formulas)}")
    print(f"Tables: {len(ir.tables)}")
    print(f"Figures: {len(ir.figures)}")
    print(f"Valid: {report.valid_objects}, Flagged: {report.flagged_objects}")
    print(f"Concepts: {len(concept_index.concepts)}")
    print(f"Relationships: {len(relationship_index.relationships)}")
    print(f"Reasoning Concepts: {len(reasoning_index.concept_reasoning)}")
    for key, path in paths.items():
        print(f"{key}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
