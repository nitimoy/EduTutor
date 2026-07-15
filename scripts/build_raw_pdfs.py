"""Rebuild data/raw/*.pdf from the chapter-wise NCERT zip files in data/.

NCERT publishes each book part as a zip of separate per-chapter PDFs (prelims,
numbered chapters, appendices, answers) rather than one combined file. The
compiler pipeline (backend/compiler/pipeline.py) expects one PDF per book part
(matching data/manifest.json's `suggested_filename`), so this script merges
each zip's chapter PDFs, in reading order, into a single book PDF under
data/raw/.

Usage:
    python scripts/build_raw_pdfs.py

Rerun this whenever a new/updated `data/<ncert_code>dd.zip` is added; it is
idempotent and safe to run repeatedly.
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path

import fitz

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_PATH = DATA_DIR / "manifest.json"

_CHAPTER_RE = re.compile(r"^\d+$")
_APPENDIX_RE = re.compile(r"^a(\d+)$")


def _sort_key(pdf_path: Path, code: str) -> tuple[int, int]:
    """Order chapter-wise PDFs as: prelims -> chapters -> appendices -> answers."""
    suffix = pdf_path.stem[len(code):]
    if suffix == "ps":
        return (0, 0)
    if _CHAPTER_RE.match(suffix):
        return (1, int(suffix))
    match = _APPENDIX_RE.match(suffix)
    if match:
        return (2, int(match.group(1)))
    if suffix == "an":
        return (3, 0)
    return (4, 0)  # unknown suffix: keep at the end, stable order


def build_book(code: str, zip_path: Path, output_path: Path) -> None:
    """Extract `zip_path` and merge its chapter PDFs into `output_path`."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        chapter_pdfs = sorted(tmp_dir.glob(f"{code}*.pdf"), key=lambda p: _sort_key(p, code))
        if not chapter_pdfs:
            logger.warning("No PDFs found in %s", zip_path)
            return

        merged = fitz.open()
        for pdf_path in chapter_pdfs:
            with fitz.open(pdf_path) as chapter:
                merged.insert_pdf(chapter)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        merged.save(output_path)
        merged.close()
        logger.info("Built %s from %d chapter files (%s)", output_path, len(chapter_pdfs), zip_path.name)


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for book in manifest["books"]:
        code = book["ncert_code"]
        zip_path = DATA_DIR / f"{code}dd.zip"
        output_path = RAW_DIR / book["suggested_filename"]
        if not zip_path.exists():
            logger.warning("Skipping %s: %s not found", book["book"], zip_path)
            continue
        build_book(code, zip_path, output_path)


if __name__ == "__main__":
    main()
