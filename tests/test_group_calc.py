"""Team/group split + calories burned (pure math, offline)."""

from __future__ import annotations

from core.group_calc import team_split, calories_burned


class TestTeamSplit:
    def test_even_teams(self):
        assert "har team 5 log" in team_split("10 log 2 teams")

    def test_uneven_teams(self):
        # 11 into 2 -> one team of 6, one of 5
        out = team_split("11 players 2 teams")
        assert "of 6" in out and "of 5" in out

    def test_fixed_size_groups(self):
        out = team_split("15 log 4 ke groups")
        assert "3 full group" in out and "group of 3" in out

    def test_groups_of_english(self):
        out = team_split("20 students groups of 6")
        assert "3 full group" in out and "group of 2" in out

    def test_prompt(self):
        assert "kitne log" in team_split("teams bana do")


class TestCalories:
    def test_steps_default_weight(self):
        # 8000 * 0.0005 * 65 = 260
        assert "260 kcal" in calories_burned("8000 steps")

    def test_steps_with_weight(self):
        assert "400 kcal" in calories_burned("10000 kadam weight 80")

    def test_distance_walk(self):
        # 0.53 * 65 * 5 = 172.25 -> 172
        assert "172 kcal" in calories_burned("5 km walk")

    def test_distance_run(self):
        # 1.0 * 70 * 10 = 700
        assert "700 kcal" in calories_burned("10 km running weight 70")

    def test_prompt(self):
        assert "Steps ya distance" in calories_burned("calorie batao")


class TestSkills:
    def test_team_skill(self):
        from skills.group_calc_skill import team_split as t
        assert "team" in t({"raw_text": "10 log 2 teams me baato"})

    def test_cal_skill(self):
        from skills.group_calc_skill import calories_burned as c
        assert "kcal" in c({"raw_text": "8000 steps me kitni calorie"})
