"""Combinations/permutations + quadratic solver (pure math, offline)."""

from __future__ import annotations

from core.number_props import combinations_permutations, quadratic_solver


class TestCombiPerm:
    def test_combination(self):
        assert "5C3 (combinations) = 10" in combinations_permutations("5 me se 3")

    def test_combination_larger(self):
        assert "10C2 (combinations) = 45" in combinations_permutations("10 choose 2")

    def test_permutation(self):
        assert "5P3 (permutations) = 60" in combinations_permutations("5 permutations 3")

    def test_prompt(self):
        assert "Do numbers do" in combinations_permutations("choose batao")


class TestQuadratic:
    def test_two_real_roots(self):
        out = quadratic_solver("2 3 -5 quadratic")
        assert "x = 1 aur -2.5" in out

    def test_labelled_coeffs(self):
        # x^2 - 3x + 2 -> roots 2, 1
        out = quadratic_solver("a=1 b=-3 c=2")
        assert "2 aur 1" in out

    def test_repeated_root(self):
        assert "repeated root x = 2" in quadratic_solver("1 -4 4")

    def test_complex_roots(self):
        assert "+/- 1i" in quadratic_solver("1 0 1")

    def test_a_zero(self):
        assert "zero nahi" in quadratic_solver("a=0 b=2 c=3")

    def test_prompt(self):
        assert "a, b, c do" in quadratic_solver("solve karo")


class TestSkills:
    def test_combi_skill(self):
        from skills.number_props_skill import combinations_permutations as c
        assert "10" in c({"raw_text": "5 me se 3 kitne tarike se chun sakte"})

    def test_quad_skill(self):
        from skills.number_props_skill import quadratic_solver as q
        assert "root" in q({"raw_text": "2 3 -5 quadratic roots"})
