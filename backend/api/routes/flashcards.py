"""Chapter-wise flashcard generation endpoint.

Generates flashcards from the knowledge index for a specific chapter.
Each flashcard is a question/answer pair extracted from definitions,
formulas, and examples in the compiled data.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/v1", tags=["flashcards"])


class Flashcard(BaseModel):
    """A single flashcard with question and answer."""
    question: str
    answer: str
    concept_name: str
    concept_id: str
    chapter: str
    subject: str
    card_type: str  # "definition", "formula", "example"


class FlashcardDeck(BaseModel):
    """A deck of flashcards for a chapter."""
    subject: str
    chapter: str
    total_cards: int
    cards: list[Flashcard]


def _extract_definition_cards(doc: dict) -> list[Flashcard]:
    """Extract flashcards from definition texts.

    Uses the concept name as question and finds the most relevant definition.
    """
    cards = []
    concept_name = doc.get("name", "")
    import re

    # Skip non-educational concepts
    skip_concepts = {"remarks", "notes", "summary", "example", "exercise", "answers"}
    if concept_name.lower() in skip_concepts:
        return cards

    # Skip very short or very long concept names
    if len(concept_name) < 3 or len(concept_name) > 60:
        return cards

    # Find the best definition that matches this concept
    best_definition = None
    best_score = 0

    for text in doc.get("definition_texts", []):
        text = text.strip()
        if len(text) < 30:
            continue

        # Skip formatting artifacts
        if text.startswith(("Reprint", "©", "ISBN", "Price")):
            continue
        if re.search(r'[═║─┌┐└┘├┤┬┴┼]', text):
            continue
        if re.search(r'^\d+\s+\d+\s+\d+', text):
            continue

        # Score based on relevance to concept name
        score = 0
        text_lower = text.lower()
        concept_lower = concept_name.lower()

        # Check if concept name appears in the definition
        if concept_lower in text_lower:
            score += 20

        # Check for definition patterns
        if any(phrase in text_lower for phrase in ['is called', 'is defined', 'is said to be', 'is known as']):
            score += 10

        # Check for quality indicators
        if len(text) > 50 and len(text) < 400:
            score += 5

        # Penalize if it contains section numbers or other concepts
        if re.search(r'^\d+\.?\d+', text):
            score -= 5
        if 'Definition' in text[:20]:
            score -= 3

        if score > best_score:
            best_score = score
            best_definition = text

    if best_definition and best_score > 0:
        # Clean up the definition
        answer = best_definition
        # Remove section numbers at the start
        answer = re.sub(r'^\d+\.?\d*\s*', '', answer)
        # Remove "Definition N" prefix
        answer = re.sub(r'^Definition\s+\d+\s*:?\s*', '', answer)
        # Remove leading "(vii)" style numbering
        answer = re.sub(r'^\([ivx]+\)\s*', '', answer)
        # Limit length
        if len(answer) > 300:
            answer = answer[:300] + "..."

        cards.append(Flashcard(
            question=f"Define: {concept_name}",
            answer=answer,
            concept_name=concept_name,
            concept_id=doc.get("concept_id", ""),
            chapter=doc.get("chapter", ""),
            subject=doc.get("subject", ""),
            card_type="definition",
        ))

    return cards


def _extract_formula_cards(doc: dict) -> list[Flashcard]:
    """Extract flashcards from formula texts."""
    cards = []
    for formula in doc.get("formula_latex", []):
        formula = formula.strip()
        if len(formula) < 5:
            continue

        # Create a flashcard for each formula
        cards.append(Flashcard(
            question=f"What is the formula for {doc.get('name', 'this concept')}?",
            answer=formula,
            concept_name=doc.get("name", ""),
            concept_id=doc.get("concept_id", ""),
            chapter=doc.get("chapter", ""),
            subject=doc.get("subject", ""),
            card_type="formula",
        ))

    return cards


def _extract_example_cards(doc: dict) -> list[Flashcard]:
    """Extract flashcards from example texts."""
    cards = []
    examples = doc.get("example_texts", [])
    concept_name = doc.get("name", "")

    # Take up to 2 high-quality examples per concept
    count = 0
    for example in examples:
        if count >= 2:
            break

        example = example.strip()
        if len(example) < 50:  # Skip very short examples
            continue

        # Skip if example is just formatting
        if example.startswith(("Reprint", "©", "ISBN")):
            continue

        # Try to find a clear question/solution split
        import re

        # Pattern: "Example N: <problem>" followed by solution
        example_match = re.match(r'Example\s*\d+[.:]\s*(.+)', example, re.IGNORECASE)
        if example_match:
            problem = example_match.group(1).strip()
            # Find solution after "Solution" keyword or after the problem
            solution_match = re.search(r'(?:Solution|Answer|Solution:)\s*(.+)', example, re.IGNORECASE)
            if solution_match:
                solution = solution_match.group(1).strip()[:500]
                if len(problem) > 10 and len(solution) > 10:
                    cards.append(Flashcard(
                        question=f"Solve: {problem}",
                        answer=solution,
                        concept_name=concept_name,
                        concept_id=doc.get("concept_id", ""),
                        chapter=doc.get("chapter", ""),
                        subject=doc.get("subject", ""),
                        card_type="example",
                    ))
                    count += 1
                    continue

        # Pattern: Look for "Find", "Calculate", "Determine", "Show that"
        problem_match = re.match(r'((?:Find|Calculate|Determine|Show\s+that|Evaluate|Prove)\s+.+?)(?:\.|$)', example, re.IGNORECASE)
        if problem_match:
            problem = problem_match.group(1).strip()
            # Find solution after this
            rest = example[problem_match.end():].strip()
            solution_match = re.search(r'(?:Solution|Answer|Solution:)\s*(.+)', rest, re.IGNORECASE)
            if solution_match:
                solution = solution_match.group(1).strip()[:500]
                if len(problem) > 10 and len(solution) > 10:
                    cards.append(Flashcard(
                        question=f"Solve: {problem}",
                        answer=solution,
                        concept_name=concept_name,
                        concept_id=doc.get("concept_id", ""),
                        chapter=doc.get("chapter", ""),
                        subject=doc.get("subject", ""),
                        card_type="example",
                    ))
                    count += 1

    return cards


def _generate_flashcards_for_chapter(
    subject: str,
    chapter: str,
    compiled_dir: str = "data/compiled",
) -> FlashcardDeck:
    """Generate flashcards for a specific chapter from the knowledge index."""
    compiled = Path(compiled_dir)
    all_cards: list[Flashcard] = []

    # Find the right book for this subject
    subject_dir = compiled / subject
    if not subject_dir.exists():
        raise HTTPException(status_code=404, detail=f"Subject '{subject}' not found")

    for book_dir in subject_dir.iterdir():
        if not book_dir.is_dir():
            continue

        ki_path = book_dir / "knowledge_index.json"
        if not ki_path.exists():
            continue

        ki_data = json.loads(ki_path.read_text())

        # Filter concepts by chapter
        for doc in ki_data.get("documents", []):
            doc_chapter = doc.get("chapter", "")
            if doc_chapter.lower() != chapter.lower():
                continue

            # Extract cards from each concept
            all_cards.extend(_extract_definition_cards(doc))
            all_cards.extend(_extract_formula_cards(doc))
            all_cards.extend(_extract_example_cards(doc))

    if not all_cards:
        raise HTTPException(
            status_code=404,
            detail=f"No flashcards found for {subject} / {chapter}",
        )

    # Shuffle cards for variety
    random.shuffle(all_cards)

    return FlashcardDeck(
        subject=subject,
        chapter=chapter,
        total_cards=len(all_cards),
        cards=all_cards,
    )


@router.get("/flashcards/{subject}/{chapter}", response_model=FlashcardDeck)
def get_chapter_flashcards(
    subject: str,
    chapter: str,
) -> FlashcardDeck:
    """Generate flashcards for a specific chapter.

    Returns a deck of flashcards with definitions, formulas, and examples
    extracted from the compiled knowledge index.
    """
    return _generate_flashcards_for_chapter(subject, chapter)


@router.get("/flashcards/{subject}")
def list_chapter_flashcards(
    subject: str,
) -> dict:
    """List available chapters for flashcard generation."""
    compiled = Path("data/compiled")
    subject_dir = compiled / subject

    if not subject_dir.exists():
        raise HTTPException(status_code=404, detail=f"Subject '{subject}' not found")

    chapters = set()
    for book_dir in subject_dir.iterdir():
        if not book_dir.is_dir():
            continue

        ki_path = book_dir / "knowledge_index.json"
        if not ki_path.exists():
            continue

        ki_data = json.loads(ki_path.read_text())
        for doc in ki_data.get("documents", []):
            chapter = doc.get("chapter", "")
            if chapter:
                chapters.add(chapter)

    return {
        "subject": subject,
        "chapters": sorted(chapters),
        "total_chapters": len(chapters),
    }
