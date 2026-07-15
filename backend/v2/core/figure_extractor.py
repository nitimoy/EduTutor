"""Extract figures from NCERT PDFs and save them for serving.

This script extracts images from the source PDFs and saves them
to data/figures/ for display in the chat interface.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # PyMuPDF


def extract_figures(
    raw_dir: str = "data/raw",
    output_dir: str = "data/figures",
    compiled_dir: str = "data/compiled",
) -> dict:
    """Extract all figures from NCERT PDFs.

    Returns stats about the extraction process.
    """
    raw_path = Path(raw_dir)
    output_path = Path(output_dir)
    compiled_path = Path(compiled_dir)

    stats = {"books_processed": 0, "figures_extracted": 0, "total_pages": 0}

    # Process each subject/book
    for subject_dir in sorted(compiled_path.iterdir()):
        if not subject_dir.is_dir():
            continue
        for book_dir in sorted(subject_dir.iterdir()):
            if not book_dir.is_dir():
                continue

            # Find corresponding PDF
            pdf_path = raw_path / (book_dir.name + ".pdf")

            if not pdf_path.exists():
                continue

            # Extract figures
            book_output = output_path / subject_dir.name / book_dir.name
            book_output.mkdir(parents=True, exist_ok=True)

            count = _extract_from_pdf(pdf_path, book_dir, book_output)
            stats["figures_extracted"] += count
            stats["books_processed"] += 1
            print(f"Extracted {count} figures from {pdf_path.name}")

    return stats


def _extract_from_pdf(
    pdf_path: Path,
    book_dir: Path,
    output_dir: Path,
) -> int:
    """Extract figures from a single PDF using PyMuPDF's image detection."""
    # Open the PDF
    doc = fitz.open(str(pdf_path))
    extracted = 0
    seen_images = set()  # Avoid duplicate extractions

    # Load figure metadata for caption mapping
    figures_path = book_dir / "figures.json"
    figures = json.loads(figures_path.read_text()) if figures_path.exists() else []

    # Build page -> figures mapping
    page_figures = {}
    for fig in figures:
        page_num = fig.get("page", 0)
        if page_num not in page_figures:
            page_figures[page_num] = []
        page_figures[page_num].append(fig)

    # Extract figures from each page
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_rect = page.rect

        # Get image blocks from PyMuPDF's text extraction
        blocks = page.get_text("dict")["blocks"]
        image_blocks = [b for b in blocks if b.get("type") == 1]

        # Also get embedded images
        embedded_images = page.get_images()

        # Extract each image block (skip full-page images)
        for block in image_blocks:
            bbox = block.get("bbox", [0, 0, 0, 0])
            x0, y0, x1, y1 = bbox

            # Skip full-page images (covering > 80% of page)
            block_area = (x1 - x0) * (y1 - y0)
            page_area = page_rect.width * page_rect.height
            if page_area > 0 and block_area / page_area > 0.80:
                continue

            # Skip very small images (< 50x50)
            if (x1 - x0) < 50 or (y1 - y0) < 50:
                continue

            # Create a unique key for deduplication
            img_key = f"{page_num}_{int(x0)}_{int(y0)}_{int(x1)}_{int(y1)}"
            if img_key in seen_images:
                continue
            seen_images.add(img_key)

            # Find the best matching figure from metadata
            best_fig_id = f"page{page_num+1}_fig{int(x0)}_{int(y0)}"
            best_overlap = 0
            for fig in page_figures.get(page_num + 1, []):
                fig_bb = fig.get("bounding_box", {})
                if fig_bb:
                    fx0, fy0 = fig_bb.get("x0", 0), fig_bb.get("y0", 0)
                    fx1, fy1 = fig_bb.get("x1", 0), fig_bb.get("y1", 0)
                    # Calculate overlap
                    ix0 = max(x0, fx0)
                    iy0 = max(y0, fy0)
                    ix1 = min(x1, fx1)
                    iy1 = min(y1, fy1)
                    if ix1 > ix0 and iy1 > iy0:
                        overlap = (ix1 - ix0) * (iy1 - iy0)
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_fig_id = fig.get("id", best_fig_id)

            # Render the figure region
            rect = fitz.Rect(x0, y0, x1, y1)
            mat = fitz.Matrix(2, 2)  # 2x zoom for quality
            try:
                clip = page.get_pixmap(matrix=mat, clip=rect)
                output_file = output_dir / f"{best_fig_id}.png"
                clip.save(str(output_file))
                extracted += 1
            except Exception:
                continue

    doc.close()
    return extracted


def get_figure_path(fig_id: str, subject: str, book: str) -> Optional[str]:
    """Get the path to a figure image file."""
    # Check multiple possible locations
    possible_paths = [
        Path(f"data/figures/{subject}/{book}/{fig_id}.png"),
        Path(f"data/figures/{subject}/{book}/{fig_id}.jpg"),
        Path(f"data/figures/{fig_id}.png"),
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return None


if __name__ == "__main__":
    stats = extract_figures()
    print(f"\nBooks processed: {stats['books_processed']}")
    print(f"Figures extracted: {stats['figures_extracted']}")
