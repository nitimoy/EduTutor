"""Teaching-style presets — formatting and tone only, **zero educational content**.

A preset maps each :class:`SectionKind` to a :class:`StyleDirective` that expresses *how*
to phrase a section, never *what* it says. All knowledge comes from the ``TutorPlan``; these
templates only carry presentation guidance (tone, layout, length). ``test_style.py`` guards
that no directive string contains subject vocabulary.
"""

from __future__ import annotations

from backend.generation.models import StyleDirective
from backend.tutor.models import SectionKind

# The neutral fallback directive when a preset omits a kind.
_DEFAULT_DIRECTIVE = StyleDirective(tone="clear and encouraging", format="short paragraphs")

# Per-kind directives. Every string is pure formatting/tone — no domain terms.
_DEFAULT_PRESET: dict[SectionKind, StyleDirective] = {
    SectionKind.PREREQUISITES: StyleDirective(
        tone="supportive", format="a short bulleted list"),
    SectionKind.MAIN_EXPLANATION: StyleDirective(
        tone="clear and encouraging", format="short paragraphs"),
    SectionKind.FORMULA: StyleDirective(
        tone="precise", format="display each item on its own line"),
    SectionKind.WORKED_EXAMPLE: StyleDirective(
        tone="step-by-step and patient", format="numbered steps"),
    SectionKind.PROOF: StyleDirective(
        tone="rigorous but readable", format="numbered logical steps"),
    SectionKind.EXERCISE: StyleDirective(
        tone="encouraging", format="a numbered list of prompts"),
    SectionKind.COMPARISON: StyleDirective(
        tone="objective and structured",
        format="a markdown comparison table with columns: Aspect, Concept A, Concept B"),
    SectionKind.RELATED_CONCEPTS: StyleDirective(
        tone="brief", format="a short inline list"),
    SectionKind.NEXT_TOPICS: StyleDirective(
        tone="forward-looking", format="a numbered ordered list"),
    SectionKind.SUMMARY: StyleDirective(
        tone="concise and reassuring", format="two to three sentences", max_sentences=3),
    SectionKind.GROUNDED_FACTS: StyleDirective(
        tone="honest and precise",
        format="disclaimer paragraph followed by a bulleted fact list"),
}

# A terser preset (same vocabulary-free guarantee).
_CONCISE_PRESET: dict[SectionKind, StyleDirective] = {
    kind: StyleDirective(tone="concise", format=d.format, max_sentences=2)
    for kind, d in _DEFAULT_PRESET.items()
}

STYLE_PRESETS: dict[str, dict[SectionKind, StyleDirective]] = {
    "default": _DEFAULT_PRESET,
    "concise": _CONCISE_PRESET,
}


def directive_for(preset: str, kind: SectionKind) -> StyleDirective:
    """Return the style directive for a section kind under a preset (neutral fallback)."""
    return STYLE_PRESETS.get(preset, _DEFAULT_PRESET).get(kind, _DEFAULT_DIRECTIVE)
