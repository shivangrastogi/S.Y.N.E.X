"""One-rep-max + calorie deficit (pure math, offline)."""

from __future__ import annotations

from core.health_calc import one_rep_max, calorie_deficit


class TestOneRepMax:
    def test_epley(self):
        # 100*(1+5/30) = 116.67
        out = one_rep_max("100 kg 5 reps")
        assert "116.7" in out and "90%" in out

    def test_other(self):
        assert "101.3" in one_rep_max("80 kg for 8 reps")

    def test_prompt(self):
        assert "Weight aur reps" in one_rep_max("bench press")


class TestCalorieDeficit:
    def test_timeline(self):
        # 5*7700/500 = 77 days ~ 11 weeks
        out = calorie_deficit("lose 5 kg 500 cal deficit")
        assert "77 din" in out and "11.0 hafte" in out

    def test_faster(self):
        assert "33 din" in calorie_deficit("3 kg 700 calorie")

    def test_prompt(self):
        assert "Kitna weight ghatana" in calorie_deficit("weight loss batao")


class TestSkills:
    def test_orm_skill(self):
        from skills.health_split_skill import one_rep_max as o
        assert "1RM" in o({"raw_text": "100 kg 5 reps ka 1rm"})

    def test_deficit_skill(self):
        from skills.health_split_skill import calorie_deficit as c
        assert "din" in c({"raw_text": "5 kg lose karne me kitne din 500 deficit"})
