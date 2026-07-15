"""Health, readiness, version, config, and root info endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import json

from backend.api.config import ServiceConfig
from backend.api.deps import get_config, get_factory
from backend.api.factory import EngineFactory

router = APIRouter(tags=["health"])

FIGURES_DIR = Path("data/figures")


@router.get("/")
def root(config: ServiceConfig = Depends(get_config)) -> dict[str, str]:
    """Service discovery: name, version, and useful paths."""
    return {
        "service": "NCERT Educational Tutor API",
        "version": config.api_version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@router.get("/api/v1/health")
def health() -> dict[str, str]:
    """Liveness probe: the server process is alive."""
    return {"status": "ok"}


@router.get("/api/v1/ready")
def ready(factory: EngineFactory = Depends(get_factory)) -> dict[str, object]:
    """Readiness probe: the engine is successfully initialized.

    Accesses the factory's lazy engines to confirm they can be constructed
    without error. Returns ``ready: false`` with an error message if
    construction fails.
    """
    try:
        # Touch the lazy properties to trigger construction.
        _ = factory.tutor_engine
        _ = factory.session_engine
        return {"ready": True}
    except Exception as exc:  # noqa: BLE001 - readiness must never crash
        return {"ready": False, "error": str(exc)}


@router.get("/api/v1/version")
def version(config: ServiceConfig = Depends(get_config)) -> dict[str, str]:
    """API version information."""
    return {"version": config.api_version, "phase": "8.0"}


@router.get("/api/v1/config")
def config_info(config: ServiceConfig = Depends(get_config)) -> dict[str, object]:
    """Non-secret configuration summary."""
    return config.public_summary()


# === Figure serving endpoints ===

@router.get("/api/v1/figures/{subject}/{book}/{figure_id}")
async def get_figure(subject: str, book: str, figure_id: str):
    """Serve a figure image from the compiled data."""
    # Strip extension from figure_id if present (URL might include .png)
    clean_id = figure_id.split(".")[0] if "." in figure_id else figure_id

    for ext in ["png", "jpg", "jpeg"]:
        file_path = FIGURES_DIR / subject / book / f"{clean_id}.{ext}"
        if file_path.exists():
            return FileResponse(
                path=str(file_path.absolute()),
                media_type=f"image/{ext}",
                filename=f"{clean_id}.{ext}",
            )
    raise HTTPException(status_code=404, detail="Figure not found")


@router.get("/api/v1/figures/{subject}/{book}")
async def list_figures(subject: str, book: str):
    """List all figures for a specific book."""
    book_dir = FIGURES_DIR / subject / book
    if not book_dir.exists():
        raise HTTPException(status_code=404, detail="Book not found")

    figures = []
    for file_path in sorted(book_dir.glob("*.png")):
        figures.append({
            "id": file_path.stem,
            "path": f"/api/v1/figures/{subject}/{book}/{file_path.stem}",
        })

    return {"subject": subject, "book": book, "count": len(figures), "figures": figures}


@router.get("/api/v1/figures")
async def list_all_figures():
    """List all available figures across all books."""
    result = {}
    if FIGURES_DIR.exists():
        for subject_dir in sorted(FIGURES_DIR.iterdir()):
            if not subject_dir.is_dir():
                continue
            for book_dir in sorted(subject_dir.iterdir()):
                if not book_dir.is_dir():
                    continue
                figure_count = len(list(book_dir.glob("*.png")))
                if figure_count > 0:
                    key = f"{subject_dir.name}/{book_dir.name}"
                    result[key] = {
                        "count": figure_count,
                        "path": f"/api/v1/figures/{subject_dir.name}/{book_dir.name}",
                    }
    return {"total_books": len(result), "books": result}


@router.get("/api/v1/concept-names")
async def get_concept_names():
    """Get concept ID to name mapping from compiled data."""
    concept_names_path = Path("data/concept_names.json")
    if concept_names_path.exists():
        return json.loads(concept_names_path.read_text())
    return {}


@router.get("/api/v1/chapters")
async def list_chapters(subject: str = None):
    """List all chapters, optionally filtered by subject."""
    from backend.v2.core.chapter_index import get_chapter_index
    index = get_chapter_index()
    return index.get_chapters(subject)


@router.get("/api/v1/chapters/{subject}/{chapter}")
async def get_chapter(subject: str, chapter: str):
    """Get topics in a specific chapter."""
    from backend.v2.core.chapter_index import get_chapter_index
    index = get_chapter_index()
    data = index.get_chapter_topics(subject, chapter)
    if not data:
        return {"error": "Chapter not found"}
    return data


@router.get("/api/v1/chapters/{subject}/number/{chapter_num}")
async def get_chapter_by_number(subject: str, chapter_num: int):
    """Get chapter by number (e.g., chapter 13)."""
    from backend.v2.core.chapter_index import get_chapter_index
    index = get_chapter_index()
    data = index.get_chapter_by_number(subject, chapter_num)
    if not data:
        return {"error": "Chapter not found"}
    return data
