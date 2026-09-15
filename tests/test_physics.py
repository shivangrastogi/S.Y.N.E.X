"""Physics — F=ma + energy (pure math, offline)."""

from __future__ import annotations

from core.physics_calc import force_calc, energy_calc


class TestForce:
    def test_force_from_m_a(self):
        assert "= 50 N" in force_calc("mass 5 kg acceleration 10")

    def test_accel_from_f_m(self):
        assert "= 5 m/s2" in force_calc("force 100 N mass 20 kg")

    def test_mass_from_f_a(self):
        assert "= 5 kg" in force_calc("force 100 N acceleration 20")

    def test_prompt(self):
        assert "Do values do" in force_calc("mass 5")


class TestEnergy:
    def test_kinetic(self):
        # 0.5*5*100 = 250
        assert "= 250 J" in energy_calc("mass 5 kg velocity 10")

    def test_potential(self):
        # 2*9.8*10 = 196
        assert "= 196 J" in energy_calc("mass 2 kg height 10 potential")

    def test_potential_auto(self):
        # height present, no velocity -> PE
        assert "= 147 J" in energy_calc("mass 3 height 5")

    def test_prompt(self):
        assert "Mass do" in energy_calc("energy batao")


class TestSkills:
    def test_force_skill(self):
        from skills.physics_skill import force_calc as f
        assert "N" in f({"raw_text": "mass 5 kg acceleration 10 force"})

    def test_energy_skill(self):
        from skills.physics_skill import energy_calc as e
        assert "J" in e({"raw_text": "mass 5 velocity 10 kinetic energy"})
