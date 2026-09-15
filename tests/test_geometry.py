"""Geometry — circle + Pythagoras (pure math, offline)."""

from __future__ import annotations

from core.geometry import circle_calc, pythagoras


class TestCircle:
    def test_radius(self):
        out = circle_calc("radius 5 circle")
        assert "area 78.54" in out and "circumference 31.42" in out

    def test_diameter(self):
        # diameter 10 -> r 5 -> same as above
        assert "area 78.54" in circle_calc("diameter 10 ka circle")

    def test_prompt(self):
        assert "Radius ya diameter" in circle_calc("circle batao")


class TestPythagoras:
    def test_find_hypotenuse(self):
        assert "hypotenuse 5" in pythagoras("3 4 legs hypotenuse nikaalo")

    def test_find_hyp_end_word(self):
        assert "hypotenuse 10" in pythagoras("legs 6 and 8 hypotenuse")

    def test_given_hyp_find_leg(self):
        assert "doosri leg 4" in pythagoras("hypotenuse 5 aur ek leg 3")

    def test_given_hyp_13_5(self):
        assert "doosri leg 12" in pythagoras("hypotenuse 13 leg 5")

    def test_prompt(self):
        assert "Do sides do" in pythagoras("hypotenuse batao")


class TestSkills:
    def test_circle_skill(self):
        from skills.geometry_skill import circle_calc as c
        assert "area" in c({"raw_text": "radius 5 circle ka area"})

    def test_pythagoras_skill(self):
        from skills.geometry_skill import pythagoras as p
        assert "hypotenuse" in p({"raw_text": "3 4 ka hypotenuse kya hai"})
