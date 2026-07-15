"""Link formulas to concepts and inject into knowledge index.

Formulas in formulas.json are linked to paragraphs via linked_paragraph_id.
Concepts have definition_ids that reference those same paragraphs.
This script bridges the gap: finds formulas linked to concept definitions
and injects them into formula_ids (concept_index) and formula_latex (knowledge_index).
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def is_real_formula(text: str) -> bool:
    """Check if text contains actual mathematical content (not noise)."""
    text_lower = text.lower().strip()

    # Skip obvious noise
    noise_patterns = [
        'first edition', 'copyright', 'reprinted', 'revised edition',
        'no part of this publication', 'this book is sold',
        'the correct price', 'any revised price',
        'trade, be lent', 'prior permission',
    ]
    if any(noise in text_lower for noise in noise_patterns):
        return False

    # Skip very short text
    if len(text) < 10:
        return False

    # Check for mathematical content indicators
    math_indicators = [
        '=', '∈', '⊂', '∪', '∩', '∀', '∃',
        'a_', 'b_', 'x_', 'y_', 'n_',
        'a′', "a'", 'A′', "A'",
        '[', ']', '(', ')',
        '×', '→', '↦',
        'matrix', 'determinant', 'inverse',
        'function', 'relation',
        'sum', 'product', 'integral',
        'cos', 'sin', 'tan', 'log', 'ln',
    ]

    return any(indicator in text for indicator in math_indicators)


def link_formulas_to_concepts(compiled_dir: str = "data/compiled") -> dict:
    """Link formulas to concepts across all books.

    Returns stats about the linking process.
    """
    compiled = Path(compiled_dir)
    total_linked = 0
    total_formulas_found = 0

    for subject_dir in sorted(compiled.iterdir()):
        if not subject_dir.is_dir():
            continue

        for book_dir in sorted(subject_dir.iterdir()):
            if not book_dir.is_dir():
                continue

            stats = _link_formulas_in_book(book_dir)
            total_linked += stats["linked"]
            total_formulas_found += stats["formulas_found"]

    return {
        "total_linked": total_linked,
        "total_formulas_found": total_formulas_found,
    }


def _link_formulas_in_book(book_dir: Path) -> dict:
    """Link formulas to concepts in a single book."""
    ci_path = book_dir / "concept_index.json"
    formulas_path = book_dir / "formulas.json"
    ki_path = book_dir / "knowledge_index.json"

    if not all(p.exists() for p in [ci_path, formulas_path, ki_path]):
        return {"linked": 0, "formulas_found": 0}

    # Load data
    ci_data = json.loads(ci_path.read_text())
    formulas = json.loads(formulas_path.read_text())
    ki_data = json.loads(ki_path.read_text())

    # Build formula lookup by linked_paragraph_id
    paragraph_to_formulas: dict[str, list[dict]] = {}
    for f in formulas:
        linked_id = f.get("linked_paragraph_id")
        if linked_id:
            if linked_id not in paragraph_to_formulas:
                paragraph_to_formulas[linked_id] = []
            paragraph_to_formulas[linked_id].append(f)

    # Build knowledge index lookup by concept_id
    ki_by_concept = {doc["concept_id"]: doc for doc in ki_data.get("documents", [])}

    linked_count = 0
    formulas_found = 0

    # Process each concept
    for concept in ci_data.get("concepts", []):
        concept_id = concept["id"]
        definition_ids = concept.get("definition_ids", [])

        # Find formulas linked to this concept's definitions
        concept_formulas = []
        for def_id in definition_ids:
            if def_id in paragraph_to_formulas:
                for f in paragraph_to_formulas[def_id]:
                    if is_real_formula(f.get("latex", "")):
                        concept_formulas.append(f)
                        formulas_found += 1

        if concept_formulas:
            # Update concept_index.json
            concept["formula_ids"] = [f["id"] for f in concept_formulas]
            linked_count += 1

            # Update knowledge_index.json
            if concept_id in ki_by_concept:
                ki_doc = ki_by_concept[concept_id]
                # Extract LaTeX content from formulas
                formula_latex = []
                for f in concept_formulas:
                    latex = f.get("latex", "").strip()
                    if latex and latex not in formula_latex:
                        formula_latex.append(latex)
                ki_doc["formula_latex"] = formula_latex

    # Save updated files
    ci_path.write_text(json.dumps(ci_data, indent=2, ensure_ascii=False))
    ki_path.write_text(json.dumps(ki_data, indent=2, ensure_ascii=False))

    return {"linked": linked_count, "formulas_found": formulas_found}


if __name__ == "__main__":
    stats = link_formulas_to_concepts()
    print(f"Linked formulas to {stats['total_linked']} concepts")
    print(f"Total formula references found: {stats['total_formulas_found']}")
