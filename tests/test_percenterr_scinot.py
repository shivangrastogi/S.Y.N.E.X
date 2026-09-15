"""Percent error + scientific notation (pure math, offline)."""

from __future__ import annotations

from core.number_props import percent_error, scientific_notation


class TestPercentError:
    def test_basic(self):
        assert "error = 5%" in percent_error("measured 95 actual 100")

    def test_keywords(self):
        out = percent_error("experimental 9.8 true 9.81")
        assert "0.1019%" in out

    def test_bare(self):
        assert "error = 2%" in percent_error("102 100")

    def test_prompt(self):
        assert "Measured aur actual" in percent_error("error batao")


class TestScientific:
    def test_to_scientific(self):
        assert "1.23 x 10^5" in scientific_notation("123000 scientific")

    def test_small_number(self):
        assert "4.2 x 10^-4" in scientific_notation("0.00042 in scientific")

    def test_expand(self):
        assert "= 123000" in scientific_notation("1.23e5 normal")

    def test_expand_exact_large(self):
        # no float artefacts
        assert "= 602000000000000000000000" in scientific_notation("6.02 x 10^23")

    def test_prompt(self):
        assert "Number do" in scientific_notation("scientific batao")


class TestSkills:
    def test_error_skill(self):
        from skills.number_props_skill import percent_error as p
        assert "error" in p({"raw_text": "measured 95 actual 100 percent error"})

    def test_sci_skill(self):
        from skills.number_props_skill import scientific_notation as s
        assert "10^" in s({"raw_text": "123000 ko scientific notation me likho"})
