"""Zodiac sign + running pace (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import zodiac_sign, running_pace, _sign


class TestZodiac:
    def test_boundaries(self):
        assert _sign(8, 22) == "Leo" and _sign(8, 23) == "Virgo"
        assert _sign(3, 20) == "Pisces" and _sign(3, 21) == "Aries"
        assert _sign(1, 19) == "Capricorn" and _sign(1, 20) == "Aquarius"

    def test_month_name(self):
        assert "Leo" in zodiac_sign("15 august")

    def test_numeric_date(self):
        assert "Leo" in zodiac_sign("15/08")

    def test_prompt_when_unparseable(self):
        assert "Janamdin" in zodiac_sign("meri rashi batao")


class TestPace:
    def test_min_km(self):
        out = running_pace("5 km 25 min")
        assert "5:00 /km" in out and "12.0 km/h" in out

    def test_clock_form(self):
        out = running_pace("10 km 55:30")
        assert "5:33 /km" in out

    def test_mile_converts(self):
        out = running_pace("3 mile 24 min")
        assert "4.83 km" in out

    def test_missing_time(self):
        assert "Time bhi do" in running_pace("5 km")

    def test_missing_distance(self):
        assert "Distance aur time" in running_pace("25 min bhaga")


class TestSkills:
    def test_zodiac_skill(self):
        from skills.misc_calc_skill import zodiac_sign as z
        assert "Virgo" in z({"raw_text": "25 august ka zodiac"})

    def test_pace_skill(self):
        from skills.misc_calc_skill import running_pace as p
        assert "/km" in p({"raw_text": "5 km 25 min pace"})
