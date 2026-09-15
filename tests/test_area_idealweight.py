"""Room area + ideal weight (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import area_calc
from core.health_calc import ideal_weight


class TestArea:
    def test_feet(self):
        out = area_calc("10 by 12 feet room area")
        assert "120 sq.ft" in out and "44ft perimeter" in out

    def test_x_separator(self):
        assert "180 sq.ft" in area_calc("12x15 room")

    def test_metre(self):
        out = area_calc("5 by 4 meter area")
        assert "20 sq.m" in out and "18m perimeter" in out

    def test_prompt(self):
        assert "Do dimensions" in area_calc("area batao")


class TestIdealWeight:
    def test_cm(self):
        # 175cm -> 18.5*1.75^2=56.6 .. 24.9*1.75^2=76.2 -> 57-76
        out = ideal_weight("height 175 ideal weight")
        assert "57-76 kg" in out

    def test_feet(self):
        assert "175cm" in ideal_weight("5 foot 9 ideal weight")

    def test_bare_cm(self):
        assert "47-64 kg" in ideal_weight("meri height 160 hai ideal weight")

    def test_prompt(self):
        assert "height batao" in ideal_weight("ideal weight batao")


class TestSkills:
    def test_area_skill(self):
        from skills.misc_calc_skill import area_calc as a
        assert "sq.ft" in a({"raw_text": "10 by 12 feet room ka area"})

    def test_ideal_skill(self):
        from skills.health_split_skill import ideal_weight as w
        assert "kg" in w({"raw_text": "height 175 ideal weight"})
