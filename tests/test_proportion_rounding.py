"""Proportion solve + rounding/sig-figs (pure math, offline)."""

from __future__ import annotations

from core.number_props import proportion_solve, rounding_sigfig


class TestProportion:
    def test_unknown_third(self):
        assert "x = 8" in proportion_solve("2:3 = x:12")

    def test_unknown_last(self):
        assert "x = 12" in proportion_solve("2:3 = 8:x")

    def test_unknown_first(self):
        assert "x = 2" in proportion_solve("x:5 = 4:10")

    def test_prompt(self):
        assert "Proportion do" in proportion_solve("ratio batao")


class TestRounding:
    def test_decimals(self):
        assert "= 3.14" in rounding_sigfig("3.14159 to 2 decimals")

    def test_sig_figs(self):
        assert "= 3.14" in rounding_sigfig("3.14159 to 3 sig figs")

    def test_sig_figs_large(self):
        assert "= 12000" in rounding_sigfig("12345 to 2 sig figs")

    def test_default_dp(self):
        assert "= 2.72" in rounding_sigfig("2.71828 rounded")

    def test_prompt(self):
        assert "Number aur precision" in rounding_sigfig("round batao")


class TestSkills:
    def test_proportion_skill(self):
        from skills.number_props_skill import proportion_solve as p
        assert "x =" in p({"raw_text": "2:3 = x:12 me x nikaalo"})

    def test_rounding_skill(self):
        from skills.number_props_skill import rounding_sigfig as r
        assert "3.14" in r({"raw_text": "3.14159 ko 2 decimal tak round karo"})
