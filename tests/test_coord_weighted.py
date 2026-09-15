"""Coordinate distance + weighted average (pure math, offline)."""

from __future__ import annotations

from core.geometry import coordinate_distance
from core.number_props import weighted_average


class TestCoordinate:
    def test_distance_midpoint_slope(self):
        out = coordinate_distance("0 0 se 3 4")
        assert "distance 5" in out and "midpoint (1.50,2)" in out and "slope 1.33" in out

    def test_paren_form(self):
        assert "distance 5" in coordinate_distance("(1,2) to (4,6)")

    def test_vertical_undefined_slope(self):
        assert "undefined" in coordinate_distance("point 2 3 and 2 8")

    def test_prompt(self):
        assert "Do points do" in coordinate_distance("distance batao")


class TestWeightedAverage:
    def test_three_items(self):
        # (80*3 + 90*2 + 70*1) / 6 = 490/6 = 81.67
        out = weighted_average("80 weight 3, 90 weight 2, 70 weight 1")
        assert "81.67" in out and "total weight 6" in out

    def test_credits(self):
        # (85*4 + 90*3) / 7 = 610/7 = 87.14
        assert "87.14" in weighted_average("85 credit 4, 90 credit 3")

    def test_prompt(self):
        assert "Value-weight pairs" in weighted_average("sirf 80")


class TestSkills:
    def test_coord_skill(self):
        from skills.geometry_skill import coordinate_distance as c
        assert "distance" in c({"raw_text": "0 0 se 3 4 distance"})

    def test_weighted_skill(self):
        from skills.number_props_skill import weighted_average as w
        assert "average" in w({"raw_text": "80 weight 3 90 weight 2 weighted average"})
