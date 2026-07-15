"""Tests for teaching-style presets and template purity."""

import re

from backend.generation.style import STYLE_PRESETS, directive_for
from backend.tutor.models import SectionKind

_WORD_RE = re.compile(r"[a-z]+")
_FORBIDDEN = {
    "electric", "charge", "matrix", "matrices", "osmosis", "coulomb", "dipole",
    "function", "solution", "physics", "chemistry", "mathematics", "theorem",
}


def test_default_preset_covers_every_section_kind():
    preset = STYLE_PRESETS["default"]
    for kind in SectionKind:
        assert kind in preset


def test_directive_for_falls_back_gracefully():
    d = directive_for("nonexistent-preset", SectionKind.SUMMARY)
    assert d.tone and d.format  # neutral fallback, no crash


def test_presets_resolve_per_kind():
    d = directive_for("default", SectionKind.WORKED_EXAMPLE)
    assert "step" in d.format.lower()


def test_template_purity_no_educational_terms():
    words = set()
    for preset in STYLE_PRESETS.values():
        for directive in preset.values():
            words |= set(_WORD_RE.findall(directive.tone.lower()))
            words |= set(_WORD_RE.findall(directive.format.lower()))
    assert not (words & _FORBIDDEN)


def test_concise_preset_bounds_sentences():
    assert directive_for("concise", SectionKind.MAIN_EXPLANATION).max_sentences == 2
