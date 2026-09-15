"""Normalizer v2 — shorthand canonicalization + NO-corruption guarantees.

The corruption tests are the important half: a bad expansion silently
poisons every utterance carrying that token, so digits, real words, URLs,
and math must survive untouched.
"""

from __future__ import annotations

import json
import os

import pytest

from core.normalizer import HinglishNormalizer

norm = HinglishNormalizer()


class TestShorthandExpansion:
    @pytest.mark.parametrize("raw,expect", [
        ("chrome kro", "chrome karo"),
        ("file dhund kr do", "file dhund kar do"),
        ("gana chala kro", "gaana chala karo"),
        ("time kya h", "time kya hai"),
        ("volume badha do yr", "volume badha do yaar"),
        ("chrome kholo na plz", "chrome kholo na please"),
        ("screenshot le lo jldy", "screenshot le lo jaldi"),
        ("krdo band", "kardo band"),
        ("nhi karna", "nahi karna"),
        ("msg bhejo", "message bhejo"),
    ])
    def test_expands(self, raw, expect):
        assert norm.clean(raw) == expect

    def test_elongation_collapsed(self):
        assert norm.clean("haaaan bilkul") == "haan bilkul"
        assert norm.clean("plsss karo") == "please karo"
        assert norm.clean("okkkk") == "okk"        # letters only, then no map


class TestNoCorruption:
    def test_digits_never_shrink(self):
        # The elongation collapse must ignore digits (1000 != 100).
        assert norm.clean("1000 rupaye") == "1000 rupaye"
        assert norm.clean("500000 ka loan") == "500000 ka loan"
        assert norm.clean("add karo 1000 shopping") == "add karo 1000 shopping"

    def test_kaha_said_not_confused_with_where(self):
        # "kaha" (said) must NOT become "kahan" (where).
        assert "kahan" not in norm.clean("tumne kya kaha")
        assert norm.clean("kya kaha tha") == "kya kaha tha"

    def test_urls_preserved(self):
        assert norm.clean("https://github.com/x kholo") == \
               "https://github.com/x kholo"

    def test_paths_preserved(self):
        out = norm.clean(r"C:/Users/x/file.pdf ka summary do")
        assert "c:/users/x/file.pdf" in out

    def test_real_words_untouched(self):
        for w in ("karo", "kholo", "chalao", "batao", "screenshot",
                  "notepad", "hai", "nahi", "kaisa", "please"):
            assert w in norm.clean(f"{w} test").split()

    def test_idempotent(self):
        for s in ["chrome kro", "time kya h", "1000 rupaye", "haaaan"]:
            once = norm.clean(s)
            assert norm.clean(once) == once


class TestExactMatchSymmetry:
    """A pattern and a shorthand query must meet at the same key — the
    whole point of running the normalizer on both sides."""

    def test_shorthand_query_matches_canonical_pattern(self):
        assert norm.clean("chrome kholo") == norm.clean("chrome kholo")
        # "kro" query collapses onto a "karo" pattern
        assert norm.clean("notepad band kro") == norm.clean("notepad band karo")

    def test_corpus_has_no_digit_regressions(self):
        """Full-corpus guard: no pattern loses/gains a digit under v2."""
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "data", "training_corpus.json")
        if not os.path.exists(path):
            pytest.skip("no exported corpus")
        corpus = json.load(open(path, encoding="utf-8"))
        for cfg in corpus.values():
            for p in cfg.get("patterns", []):
                raw_digits = re.sub(r"\D", "", p)
                clean_digits = re.sub(r"\D", "", norm.clean(p))
                assert raw_digits == clean_digits, f"digit change in {p!r}"
