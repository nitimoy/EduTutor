"""Figure serving endpoints for displaying textbook images."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/api/v1", tags=["figures"])

FIGURES_DIR = Path("data/figures")


@router.get("/figures/{subject}/{book}/{figure_id}")
async def get_figure(subject: str, book: str, figure_id: str):
    """Serve a figure image from the compiled data.

    Args:
        subject: Subject name (e.g., mathematics, physics, chemistry)
        book: Book name (e.g., mathematics_part_1)
        figure_id: Figure ID (e.g., 4b436c138494552e)
    """
    # Try different file extensions
    for ext in ["png", "jpg", "jpeg"]:
        file_path = FIGURES_DIR / subject / book / f"{figure_id}.{ext}"
        if file_path.exists():
            return FileResponse(
                path=str(file_path.absolute()),
                media_type=f"image/{ext}",
                filename=f"{figure_id}.{ext}",
            )

    raise HTTPException(status_code=404, detail="Figure not found")


@router.get("/figures/{subject}/{book}")
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

    return {
        "subject": subject,
        "book": book,
        "count": len(figures),
        "figures": figures,
    }


@router.get("/figures")
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
