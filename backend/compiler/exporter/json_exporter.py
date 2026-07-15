"""Export Educational IR to JSON files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.compiler.models import EducationalIR

logger = logging.getLogger(__name__)


class JsonExporter:
    """Write the Educational IR and its assets to a directory."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, ir: EducationalIR) -> dict[str, Path]:
        """Export IR to JSON files and return paths."""
        paths: dict[str, Path] = {}

        ir_path = self.output_dir / "educational_ir.json"
        ir_path.write_text(ir.model_dump_json(indent=2), encoding="utf-8")
        paths["educational_ir"] = ir_path
        logger.info("Wrote Educational IR to %s", ir_path)

        formulas_path = self.output_dir / "formulas.json"
        formulas_path.write_text(
            json.dumps([f.model_dump() for f in ir.formulas], indent=2),
            encoding="utf-8",
        )
        paths["formulas"] = formulas_path

        tables_path = self.output_dir / "tables.json"
        tables_path.write_text(
            json.dumps([t.model_dump() for t in ir.tables], indent=2),
            encoding="utf-8",
        )
        paths["tables"] = tables_path

        figures_path = self.output_dir / "figures.json"
        figures_path.write_text(
            json.dumps([f.model_dump() for f in ir.figures], indent=2),
            encoding="utf-8",
        )
        paths["figures"] = figures_path

        metadata_path = self.output_dir / "metadata.json"
        metadata = {
            "book": ir.book.model_dump(),
            "schema_version": ir.schema_version,
            "generated_at": ir.generated_at.isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        paths["metadata"] = metadata_path

        return paths
