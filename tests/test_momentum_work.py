"""Physics — momentum + work/power (pure math, offline)."""

from __future__ import annotations

from core.physics_calc import momentum_calc, work_power


class TestMomentum:
    def test_momentum_from_m_v(self):
        assert "= 50 kg.m/s" in momentum_calc("mass 5 kg velocity 10")

    def test_mass_from_p_v(self):
        assert "= 5 kg" in momentum_calc("momentum 50 velocity 10")

    def test_prompt(self):
        assert "Do values do" in momentum_calc("mass 5")


class TestWorkPower:
    def test_work(self):
        assert "= 50 J" in work_power("force 10 N distance 5")

    def test_work_and_power(self):
        out = work_power("force 10 distance 5 time 2")
        assert "50 J" in out and "25 W" in out

    def test_power_from_work_time(self):
        assert "= 5 W" in work_power("work 100 J time 20")

    def test_work_from_power_time(self):
        assert "= 200 J" in work_power("power 50 time 4")

    def test_prompt(self):
        assert "Force + distance" in work_power("kuch nahi")


class TestSkills:
    def test_momentum_skill(self):
        from skills.physics_skill import momentum_calc as m
        assert "Momentum" in m({"raw_text": "mass 5 velocity 10 momentum"})

    def test_work_skill(self):
        from skills.physics_skill import work_power as w
        assert "Work" in w({"raw_text": "force 10 distance 5 work"})
