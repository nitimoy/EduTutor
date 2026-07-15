"""Validation for gold standard YAML files.

Checks structural integrity, referential consistency, and data quality
before gold standards are used in evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from backend.evaluation.models import GoldStandard


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass
class ValidationIssue:
    """A single issue found during gold standard validation."""
    severity: str  # "error", "warning"
    message: str


@dataclass
class ValidationResult:
    """Outcome of validating a gold standard file."""
    path: str
    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.issues.append(ValidationIssue(severity="error", message=message))
        self.valid = False

    def add_warning(self, message: str) -> None:
        self.issues.append(ValidationIssue(severity="warning", message=message))


def validate_gold_standard(path: Path) -> ValidationResult:
    """Validate a gold standard YAML file for structural and referential integrity."""
    result = ValidationResult(path=str(path), valid=True)

    # 1. File existence
    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    # 2. YAML parsing
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result.add_error(f"YAML parse error: {exc}")
        return result

    if not isinstance(data, dict):
        result.add_error("YAML root must be a mapping")
        return result

    # 3. Pydantic model validation (catches typos and structural issues)
    try:
        gold = GoldStandard.model_validate(data)
    except Exception as exc:
        result.add_error(f"Schema validation failed: {exc}")
        return result

    # 4. Version format
    if not _SEMVER_RE.match(gold.version):
        result.add_error(f"Version '{gold.version}' does not follow semver (X.Y.Z)")

    # 5. Concept name uniqueness
    concept_names = set()
    for concept in gold.concepts:
        if concept.name in concept_names:
            result.add_error(f"Duplicate concept name: '{concept.name}'")
        concept_names.add(concept.name)

    # 6. Parent references resolve
    for concept in gold.concepts:
        if concept.parent_name and concept.parent_name not in concept_names:
            result.add_error(
                f"Concept '{concept.name}' references parent '{concept.parent_name}' "
                f"which does not exist in the concepts list"
            )

    # 7. Relationship source/target references resolve
    for rel in gold.relationships:
        if rel.source not in concept_names:
            result.add_error(
                f"Relationship source '{rel.source}' does not exist in concepts"
            )
        if rel.target not in concept_names:
            result.add_error(
                f"Relationship target '{rel.target}' does not exist in concepts"
            )

    # 8. Learning path references resolve
    for concept_name in gold.learning_path:
        if concept_name not in concept_names:
            result.add_error(
                f"Learning path entry '{concept_name}' does not exist in concepts"
            )

    # 9. Enrichment completeness warnings
    concepts_with_formulas = sum(1 for c in gold.concepts if c.required_formulas)
    concepts_with_figures = sum(1 for c in gold.concepts if c.required_figures)
    concepts_with_proofs = sum(1 for c in gold.concepts if c.required_proofs)

    if not concepts_with_formulas:
        result.add_warning("No concepts have required_formulas annotations")
    if not concepts_with_figures:
        result.add_warning("No concepts have required_figures annotations")
    if not concepts_with_proofs:
        result.add_warning("No concepts have required_proofs annotations")
    if not gold.learning_path:
        result.add_warning("No learning_path is defined")

    return result
