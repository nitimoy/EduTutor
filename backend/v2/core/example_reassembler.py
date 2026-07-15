"""Reassemble fragmented worked examples in compiled NCERT data.

The compiler splits worked examples into fragments (worked_example, example_question,
example_solution, calculation_step). This script reassembles them into complete
worked examples with problem + solution.
"""

from __future__ import annotations

import json
from pathlib import Path


def reassemble_worked_examples(compiled_dir: str = "data/compiled") -> dict:
    """Reassemble fragmented worked examples across all books.

    Returns stats about the reassembly process.
    """
    compiled = Path(compiled_dir)
    stats = {"books_processed": 0, "examples_reassembled": 0, "total_examples": 0}

    for subject_dir in sorted(compiled.iterdir()):
        if not subject_dir.is_dir():
            continue
        for book_dir in sorted(subject_dir.iterdir()):
            if not book_dir.is_dir():
                continue
            _reassemble_in_book(book_dir, stats)

    return stats


def _reassemble_in_book(book_dir: Path, stats: dict):
    """Reassemble worked examples in a single book."""
    ir_path = book_dir / "educational_ir.json"
    if not ir_path.exists():
        return

    ir = json.loads(ir_path.read_text())
    objects = ir.get("book", {}).get("objects", [])

    # Build object map by ID
    object_map = {obj["id"]: obj for obj in objects}

    # Find all worked_example objects and their associated fragments
    worked_examples = []
    i = 0
    while i < len(objects):
        obj = objects[i]
        if obj.get("type") == "worked_example":
            # Found a worked example header - collect all fragments until next worked_example or exercise
            example = {
                "id": obj["id"],
                "page": obj.get("page", 0),
                "problem_text": obj.get("text", ""),
                "solution_text": "",
                "fragment_ids": [obj["id"]],
            }

            # Look ahead for example_question, example_solution, calculation_step
            j = i + 1
            while j < len(objects):
                next_obj = objects[j]
                next_type = next_obj.get("type", "")

                # Stop at next worked_example, exercise, or new chapter content
                if next_type in ("worked_example", "exercise") and j > i + 1:
                    break
                if next_type == "exercise" and "EXERCISE" in next_obj.get("text", "").upper():
                    break

                # Collect example fragments
                if next_type in ("example_question", "example_solution", "calculation_step", "definition"):
                    text = next_obj.get("text", "")
                    if text.strip():
                        if next_type == "example_solution":
                            example["solution_text"] += text + " "
                        else:
                            # Check if this is part of the solution (after "Solution" appears)
                            if "solution" in example["solution_text"].lower() or "we have" in text.lower():
                                example["solution_text"] += text + " "
                            else:
                                example["problem_text"] += " " + text
                    example["fragment_ids"].append(next_obj["id"])
                elif next_type == "paragraph":
                    # Some paragraphs are part of the example (like matrix values)
                    text = next_obj.get("text", "")
                    if text.strip() and len(text) < 200:  # Short paragraphs are likely part of example
                        if "solution" in example["solution_text"].lower():
                            example["solution_text"] += text + " "
                        else:
                            example["problem_text"] += " " + text
                    example["fragment_ids"].append(next_obj["id"])

                j += 1

            # Clean up the assembled text
            example["problem_text"] = _clean_text(example["problem_text"])
            example["solution_text"] = _clean_text(example["solution_text"])

            # Create the complete worked example text
            if example["solution_text"]:
                example["complete_text"] = (
                    f"{example['problem_text']}\n\n"
                    f"Solution: {example['solution_text']}"
                )
            else:
                example["complete_text"] = example["problem_text"]

            worked_examples.append(example)
            stats["total_examples"] += 1
            i = j
        else:
            i += 1

    # Save the reassembled examples as a separate file
    if worked_examples:
        output_path = book_dir / "worked_examples.json"
        output_path.write_text(json.dumps(worked_examples, indent=2, ensure_ascii=False))
        stats["examples_reassembled"] += len(worked_examples)
        stats["books_processed"] += 1


def _clean_text(text: str) -> str:
    """Clean up assembled text."""
    # Remove excessive whitespace
    text = " ".join(text.split())
    # Remove common OCR artifacts
    text = text.replace("Reprint 2026-27", "")
    text = text.replace("Reprint 2025-26", "")
    # Remove page headers
    for header in ["MATHEMATICS", "PHYSICS", "CHEMISTRY"]:
        text = text.replace(f"{header} 57", "").replace(f"{header} 58", "")
        text = text.replace(f"{header} 59", "").replace(f"{header} 60", "")
    return text.strip()


def get_complete_example(book_dir: Path, example_number: int) -> str | None:
    """Get a complete worked example by number (e.g., 19 for Example 19)."""
    examples_path = book_dir / "worked_examples.json"
    if not examples_path.exists():
        return None

    examples = json.loads(examples_path.read_text())
    for ex in examples:
        if f"Example {example_number}" in ex.get("problem_text", ""):
            return ex.get("complete_text")
    return None


if __name__ == "__main__":
    stats = reassemble_worked_examples()
    print(f"Books processed: {stats['books_processed']}")
    print(f"Examples reassembled: {stats['examples_reassembled']}")
    print(f"Total examples found: {stats['total_examples']}")
