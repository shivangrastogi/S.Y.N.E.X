"""Marks-percentage + sleep-cycle (pure math, offline)."""

from __future__ import annotations

from core.life_calc import marks_percentage, sleep_cycle, _grade


class TestMarks:
    def test_out_of(self):
        assert "90.00%" in marks_percentage("450 out of 500")

    def test_hindi_me_se(self):
        # "500 me se 450" -> total 500, obtained 450
        assert "90.00%" in marks_percentage("500 me se 450")

    def test_slash(self):
        assert "70.00%" in marks_percentage("35/50")

    def test_grade_boundaries(self):
        assert _grade(90).startswith("A+")
        assert _grade(33).startswith("E")
        assert _grade(32) == "fail"

    def test_swaps_when_reversed(self):
        # obtained > total -> swap
        assert "80.00%" in marks_percentage("35 out of 28")

    def test_prompt(self):
        assert "Marks aur total" in marks_percentage("percentage batao")


class TestSleep:
    def test_bedtime_mode(self):
        out = sleep_cycle("raat 11 baje soun to kab uthu")
        assert "11:00 PM" in out and "8:15 AM" in out  # 6 cycles

    def test_wake_mode(self):
        out = sleep_cycle("6 am uthna hai to kab soun")
        assert "6:00 AM" in out and "8:45 PM" in out    # 6 cycles back

    def test_night_context(self):
        # "raat" must push 10 baje to 10 PM
        assert "10:00 PM" in sleep_cycle("shaam 10 baje soun")

    def test_prompt(self):
        assert "Time batao" in sleep_cycle("sleep cycle batao")


class TestSkills:
    def test_marks_skill(self):
        from skills.life_calc_skill import marks_percentage as m
        assert "%" in m({"raw_text": "450 out of 500 percentage"})

    def test_sleep_skill(self):
        from skills.life_calc_skill import sleep_cycle as s
        assert "cycle" in s({"raw_text": "raat 11 baje soun to kab uthu"})
