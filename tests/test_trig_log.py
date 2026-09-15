"""Trigonometry + logarithm (pure math, offline)."""

from __future__ import annotations

from core.number_props import trig_calc, log_calc


class TestTrig:
    def test_sin_30(self):
        assert trig_calc("sin 30").endswith("0.5000.")

    def test_cos_60(self):
        assert "0.5000" in trig_calc("cos 60")

    def test_tan_45(self):
        assert "= 1.0000" in trig_calc("tan 45")

    def test_tan_90_undefined(self):
        assert "undefined" in trig_calc("tan 90")

    def test_radians(self):
        assert "0.8415" in trig_calc("sin 1 radian")

    def test_prompt(self):
        assert "Function aur angle" in trig_calc("trig batao")


class TestLog:
    def test_log10(self):
        assert "log10(100) = 2.0000" in log_calc("log 100")

    def test_ln(self):
        assert "1.0000" in log_calc("ln 2.718281828")

    def test_log_base(self):
        assert "base 2 of 8 = 3.0000" in log_calc("log 8 base 2")

    def test_nonpositive(self):
        assert "positive numbers" in log_calc("log 0")

    def test_prompt(self):
        assert "Number do" in log_calc("logarithm batao")


class TestSkills:
    def test_trig_skill(self):
        from skills.number_props_skill import trig_calc as t
        assert "0.5000" in t({"raw_text": "sin 30 kitna hota hai"})

    def test_log_skill(self):
        from skills.number_props_skill import log_calc as l
        assert "2.0000" in l({"raw_text": "log 100 kitna hota hai"})
