"""CGPA<->percentage + numerology life-path (pure math, offline)."""

from __future__ import annotations

from core.life_calc import cgpa_percentage
from core.misc_calc import numerology, _reduce


class TestCgpa:
    def test_cgpa_to_pct(self):
        assert "80.75%" in cgpa_percentage("8.5 cgpa to percentage")

    def test_pct_to_cgpa(self):
        assert "8 CGPA" in cgpa_percentage("76 percent to cgpa")

    def test_bare_cgpa(self):
        assert "87.4" in cgpa_percentage("mera cgpa 9.2 hai")

    def test_out_of_range(self):
        assert "0-10" in cgpa_percentage("12 cgpa")

    def test_prompt(self):
        assert "CGPA ya percentage" in cgpa_percentage("cgpa batao")


class TestNumerology:
    def test_reduce(self):
        assert _reduce(41) == 5
        assert _reduce(11) == 11    # master preserved
        assert _reduce(38) == 11    # 3+8=11 -> master, kept
        assert _reduce(19) == 1     # 1+9=10 -> 1

    def test_slash_date(self):
        assert "Life-path number: 5" in numerology("15/08/1998")

    def test_month_name(self):
        assert "Life-path number" in numerology("2 january 2000 numerology")

    def test_prompt(self):
        assert "janam" in numerology("numerology batao")


class TestSkills:
    def test_cgpa_skill(self):
        from skills.life_calc_skill import cgpa_percentage as c
        assert "%" in c({"raw_text": "8.5 cgpa to percentage"})

    def test_numerology_skill(self):
        from skills.misc_calc_skill import numerology as n
        assert "Life-path" in n({"raw_text": "15/08/1998 ka numerology"})
