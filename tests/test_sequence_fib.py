"""Arithmetic/geometric sequence + Fibonacci (pure math, offline)."""

from __future__ import annotations

from core.number_props import sequence_calc, fibonacci


class TestSequence:
    def test_arithmetic(self):
        out = sequence_calc("first 2 difference 3 10 terms")
        assert "nth term 29" in out and "sum 155" in out

    def test_geometric(self):
        out = sequence_calc("first 2 ratio 3 5 terms")
        assert "nth term 162" in out and "sum 242" in out

    def test_negative_diff(self):
        out = sequence_calc("first 5 diff -2 4 terms")
        assert "nth term -1" in out and "sum 8" in out

    def test_prompt(self):
        assert "First term" in sequence_calc("sequence batao")


class TestFibonacci:
    def test_nth(self):
        assert "34" in fibonacci("10th fibonacci")

    def test_first_n(self):
        assert "0, 1, 1, 2, 3, 5, 8, 13" in fibonacci("first 8 fibonacci")

    def test_first_term(self):
        assert "= 0" in fibonacci("fibonacci 1")

    def test_prompt(self):
        assert "Kaunsa term" in fibonacci("fibonacci batao")


class TestSkills:
    def test_seq_skill(self):
        from skills.number_props_skill import sequence_calc as s
        assert "sum" in s({"raw_text": "first 2 difference 3 10 terms ka sum"})

    def test_fib_skill(self):
        from skills.number_props_skill import fibonacci as f
        assert "34" in f({"raw_text": "10th fibonacci number kya hai"})
