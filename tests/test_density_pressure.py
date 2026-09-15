"""Physics — density + pressure (pure math, offline)."""

from __future__ import annotations

from core.physics_calc import density_calc, pressure_calc


class TestDensity:
    def test_density_from_m_v(self):
        assert "= 5 (units" in density_calc("mass 10 kg volume 2")

    def test_mass_from_d_v(self):
        assert "= 20" in density_calc("density 5 volume 4")

    def test_volume_from_m_d(self):
        assert "= 10" in density_calc("mass 100 density 10")

    def test_prompt(self):
        assert "Do values do" in density_calc("mass 5")


class TestPressure:
    def test_pressure_from_f_a(self):
        assert "= 50 Pa" in pressure_calc("force 100 N area 2")

    def test_force_from_p_a(self):
        assert "= 200 N" in pressure_calc("pressure 50 area 4")

    def test_area_from_f_p(self):
        assert "= 5 m2" in pressure_calc("force 200 pressure 40")

    def test_prompt(self):
        assert "Do values do" in pressure_calc("kuch nahi")


class TestSkills:
    def test_density_skill(self):
        from skills.physics_skill import density_calc as d
        assert "Density" in d({"raw_text": "mass 10 volume 2 density"})

    def test_pressure_skill(self):
        from skills.physics_skill import pressure_calc as p
        assert "Pressure" in p({"raw_text": "force 100 area 2 pressure"})
