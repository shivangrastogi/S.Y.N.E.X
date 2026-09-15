"""Average speed (harmonic) + time-and-work (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import average_speed, work_rate


class TestAverageSpeed:
    def test_classic(self):
        # 2*60*40/100 = 48, not simple 50
        out = average_speed("60 kmph gaye 40 kmph aaye")
        assert "48.00 km/h" in out and "NOT simple 50" in out

    def test_other(self):
        assert "96.00 km/h" in average_speed("80 and 120 kmph")

    def test_prompt(self):
        assert "Do speeds do" in average_speed("speed batao")


class TestWorkRate:
    def test_hours(self):
        # 1/(1/6+1/4) = 2.4
        assert "2.40 ghante" in work_rate("A 6 ghante B 4 ghante")

    def test_days(self):
        # 1/(1/12+1/6) = 4
        assert "4.00 din" in work_rate("12 din aur 6 din")

    def test_prompt(self):
        assert "Do (ya zyada) times" in work_rate("kaam batao")


class TestSkills:
    def test_speed_skill(self):
        from skills.misc_calc_skill import average_speed as a
        assert "average speed" in a({"raw_text": "60 kmph gaye 40 kmph aaye average speed"})

    def test_work_skill(self):
        from skills.misc_calc_skill import work_rate as w
        assert "poora" in w({"raw_text": "A 6 ghante B 4 ghante saath me kitna"})
