"""Prompt snapshot tests: golden serialized neutral PromptDocuments.

Snapshots live under tests/snapshots/generation/, one JSON per unit_id. On first run (or
with SNAPSHOT_UPDATE=1) missing snapshots are written; thereafter the built documents must
match byte-for-byte. Because documents are deterministic and provider-independent, these
goldens lock both determinism and provider-neutrality.
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.generation.models import GenerationConfig
from backend.generation.renderer import Renderer

SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "generation"


def _snapshot_path(unit_id: str) -> Path:
    safe = unit_id.replace("::", "__").replace("/", "_")
    return SNAPSHOT_DIR / f"{safe}.json"


def test_prompt_document_snapshots(tutor_plan):
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    update = os.environ.get("SNAPSHOT_UPDATE") == "1"
    docs = Renderer().build_prompt_documents(tutor_plan, GenerationConfig())
    assert docs, "expected at least one prompt document"

    for doc in docs:
        path = _snapshot_path(doc.unit_id)
        serialized = doc.model_dump_json(indent=2) + "\n"
        if update or not path.exists():
            path.write_text(serialized)
            continue
        assert path.read_text() == serialized, (
            f"prompt snapshot drift for {doc.unit_id}; re-run with SNAPSHOT_UPDATE=1 if intended")


def test_snapshots_are_stable_across_two_builds(tutor_plan):
    r = Renderer()
    a = [d.model_dump_json() for d in r.build_prompt_documents(tutor_plan, GenerationConfig())]
    b = [d.model_dump_json() for d in r.build_prompt_documents(tutor_plan, GenerationConfig())]
    assert a == b
