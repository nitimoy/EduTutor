"""Tests for the deterministic verification tokenizer."""

from backend.verification.tokenizer import STOP_WORDS, content_word_set, content_words


def test_drops_stop_and_function_words():
    words = content_words("The dipole, therefore, is a pair.")
    assert "the" not in words and "therefore" not in words and "is" not in words
    assert "dipole" in words and "pair" in words


def test_strips_punctuation_and_lowercases():
    assert content_words("Alpha-Beta! (gamma)") == ("alpha", "beta", "gamma")


def test_single_chars_dropped():
    assert "a" not in content_words("a big x thing")


def test_deterministic():
    assert content_words("Compute alpha carefully") == content_words("Compute alpha carefully")


def test_content_word_set():
    assert content_word_set("alpha alpha beta") == frozenset({"alpha", "beta"})


def test_no_content_noun_in_stopwords():
    # Guard: stopwords must not hide content-bearing words used in tests.
    for w in ("alpha", "beta", "vectors", "compute", "dipole", "step", "summary"):
        assert w not in STOP_WORDS
