"""Shared text classification and semantic-linking helpers for parser adapters.

Every adapter (marker, docling, pymupdf) turns its own native representation
(markdown lines, layout items, PDF blocks) into a stream of ``EducationalObject``
instances. The *type* a piece of text is assigned, and the parent/child links
that connect worked examples, proofs, and their sub-parts, are policy that
should not be duplicated per-parser. This module is that shared policy.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from backend.compiler.models import EducationalObject, ObjectType

# --- Heuristic patterns for educational object classification. -------------

_EXAMPLE_RE = re.compile(r"^(Example\s+\d+(\.\d+)?)\b", re.IGNORECASE)
_SOLUTION_RE = re.compile(r"^(Solution)\b", re.IGNORECASE)
_DEFINITION_RE = re.compile(
    r"^(Definition|Define)\b"
    r"|\bis (?:defined|called|known|referred|termed|said (?:to be )?|considered) as\b"
    r"|\bis said to be\b"
    r"|\bif it has\b"
    r"|refers to\b"
    r"|defined as\b"
    r"|means that\b"
    r"|can be (?:defined|described|expressed|written|stated|represented)\b"
    r"|is (?:given|expressed|written|stated|represented) by\b"
    r"|is (?:essentially|basically|fundamentally)\b"
    r"|consists of\b"
    r"|involves\b"
    r"|comprises\b",
    re.IGNORECASE,
)
_PROPERTY_RE = re.compile(r"^(Property)\b", re.IGNORECASE)
_THEOREM_RE = re.compile(r"^(Theorem)\b", re.IGNORECASE)
_PROOF_RE = re.compile(r"^(Proof)\b", re.IGNORECASE)
_NOTE_RE = re.compile(r"^(Note|Remark)\b", re.IGNORECASE)
_WARNING_RE = re.compile(r"^(Warning|Caution)\b", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"^(Summary)\b", re.IGNORECASE)
_SIDEBAR_RE = re.compile(r"^(Did You Know|Box\s*\d)\b", re.IGNORECASE)
_CONCEPT_RE = re.compile(r"^(Concept|Key Concept)\b", re.IGNORECASE)
_INTEXT_RE = re.compile(r"^(Intext Questions?|In-text Questions?)\b", re.IGNORECASE)
_EXERCISE_RE = re.compile(r"^(Exercise\s+\d+\.\d+)", re.IGNORECASE)
_CAPTION_RE = re.compile(r"^(Fig(?:ure)?\.?\s*\d+(\.\d+)*|Table\s+\d+(\.\d+)*)\b", re.IGNORECASE)
_HEADING_RE = re.compile(r"^(\d+(\.\d+)*\s+[A-Z]|[A-Z][A-Z\s\-]{3,}$)")
_FINAL_ANSWER_RE = re.compile(r"^(Therefore|Hence|Thus|So,|∴)\b", re.IGNORECASE)
_FOOTNOTE_RE = re.compile(r"^(\*|\d+\s*[\.\)])\s?[a-z]")
_EXERCISE_ANSWER_RE = re.compile(r"^(Ans(?:wer)?\s*[:.])", re.IGNORECASE)
_REFERENCE_RE = re.compile(r"(?:See|Refer(?:\s+to)?|cf\.?)\s+(?:Example|Section|Chapter|Table|Fig(?:ure)?)\.?\s*\d+", re.IGNORECASE)
_CHAPTER_UNIT_RE = re.compile(r"^(?:Unit|Chapter)\s+(?:\d+|One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)", re.IGNORECASE)


def make_id(*parts: Any) -> str:
    """Create a deterministic ID from parts."""
    payload = "|".join(str(p) for p in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def extract_latex_fragments(text: str) -> list[str]:
    """Extract simple inline math markers and formula-like tokens."""
    fragments: list[str] = []
    for line in text.splitlines():
        if any(sym in line for sym in ("∫", "dx", "d", "Σ", "π", "θ", "α", "β", "√", "²", "³", "⁴")):
            fragments.append(line.strip())
    return fragments


class ParseState:
    """Mutable classification context carried across a single document parse.

    Tracks the currently "open" theorem/property and worked example so that
    subsequent blocks (proofs, example questions/solutions/steps) can be
    linked to the object they logically belong to via ``parent_id`` /
    ``children_ids`` instead of being flattened into one paragraph.
    """

    def __init__(self) -> None:
        self.current_theorem: EducationalObject | None = None
        self.current_example: EducationalObject | None = None
        self.current_example_solution: EducationalObject | None = None
        self.current_exercise: EducationalObject | None = None

    def reset_context(self) -> None:
        """Clear open theorem/example context, e.g. on a heading boundary."""
        self.current_theorem = None
        self.current_example = None
        self.current_example_solution = None
        self.current_exercise = None


def classify_block(text: str, prev_type: ObjectType, state: ParseState) -> ObjectType:
    """Classify a block of text into an educational object type.

    Order matters: more specific patterns are checked before generic ones.
    Ambiguous continuation text falls back to whatever open context
    (`state.current_example` / `state.current_example_solution`) implies.
    """
    stripped = text.strip()
    if not stripped:
        return "paragraph"

    if _CAPTION_RE.match(stripped) and len(stripped) < 160:
        return "caption"
    if _EXAMPLE_RE.match(stripped):
        return "worked_example"
    if _SOLUTION_RE.match(stripped):
        return "example_solution"
    if _DEFINITION_RE.search(stripped):
        return "definition"
    if _PROPERTY_RE.match(stripped):
        return "property"
    if _THEOREM_RE.match(stripped):
        return "theorem"
    if _PROOF_RE.match(stripped):
        return "proof"
    if _WARNING_RE.match(stripped):
        return "warning"
    if _SUMMARY_RE.match(stripped):
        return "summary"
    if _SIDEBAR_RE.match(stripped):
        return "sidebar"
    if _CONCEPT_RE.match(stripped):
        return "concept"
    if _NOTE_RE.match(stripped):
        return "important_note"
    if _INTEXT_RE.match(stripped):
        return "in_text_question"
    if _EXERCISE_ANSWER_RE.match(stripped):
        return "exercise_answer"
    if _EXERCISE_RE.match(stripped):
        return "exercise"
    if _REFERENCE_RE.search(stripped) and len(stripped) < 200:
        return "reference"
    
    if (_HEADING_RE.match(stripped) or _CHAPTER_UNIT_RE.match(stripped)) and len(stripped) < 80:
        # Many exercise questions are bold and numbered (e.g., "2.1 Calculate...")
        lower_text = stripped.lower()
        if not any(lower_text.split(" ", 1)[-1].startswith(q) for q in ("calculate", "find", "what", "how", "why", "describe", "explain", "determine", "prove")):
            return "heading"

    if state.current_example_solution is not None:
        return "final_answer" if _FINAL_ANSWER_RE.match(stripped) else "calculation_step"
    if state.current_example is not None:
        return "example_question"
    if state.current_exercise is not None:
        return "exercise_question"

    NON_BLEEDING_TYPES = {"heading", "caption", "concept", "footnote", "calculation_step", "final_answer", "reference"}
    return prev_type if prev_type not in NON_BLEEDING_TYPES else "paragraph"


def apply_semantic_links(obj: EducationalObject, state: ParseState) -> None:
    """Link ``obj`` to its logical parent (theorem/example) and update state.

    Must be called once per object, immediately after the object is
    constructed and appended to its structural container.
    """
    obj_type = obj.type

    if obj_type == "heading":
        state.reset_context()
        return

    if obj_type in ("theorem", "property"):
        state.current_theorem = obj
        return

    if obj_type == "proof" and state.current_theorem is not None:
        obj.parent_id = state.current_theorem.id
        state.current_theorem.children_ids.append(obj.id)
        return

    if obj_type == "worked_example":
        state.current_example = obj
        state.current_example_solution = None
        return

    if obj_type == "example_question" and state.current_example is not None:
        obj.parent_id = state.current_example.id
        state.current_example.children_ids.append(obj.id)
        return

    if obj_type == "example_solution" and state.current_example is not None:
        obj.parent_id = state.current_example.id
        state.current_example.children_ids.append(obj.id)
        state.current_example_solution = obj
        return

    if obj_type in ("calculation_step", "final_answer") and state.current_example_solution is not None:
        obj.parent_id = state.current_example_solution.id
        state.current_example_solution.children_ids.append(obj.id)
        return

    if obj_type == "exercise":
        state.reset_context()
        state.current_exercise = obj
        return

    if obj_type == "exercise_question" and state.current_exercise is not None:
        obj.parent_id = state.current_exercise.id
        state.current_exercise.children_ids.append(obj.id)
        return

    if obj_type == "exercise_answer" and state.current_exercise is not None:
        obj.parent_id = state.current_exercise.id
        state.current_exercise.children_ids.append(obj.id)
        return

    if obj_type == "in_text_question":
        state.reset_context()


def link_reading_order(objects: list[EducationalObject]) -> None:
    """Populate `previous_id`/`next_id` as a document-order linked list."""
    ordered = sorted(objects, key=lambda o: (o.page, o.reading_order))
    for i, obj in enumerate(ordered):
        obj.previous_id = ordered[i - 1].id if i > 0 else None
        obj.next_id = ordered[i + 1].id if i < len(ordered) - 1 else None
