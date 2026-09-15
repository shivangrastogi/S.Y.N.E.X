"""Triangle area + 3D volume (pure math, offline)."""

from __future__ import annotations

from core.geometry import triangle_area, volume_calc


class TestTriangle:
    def test_heron(self):
        out = triangle_area("3 4 5 triangle area")
        assert "area 6" in out and "perimeter 12" in out

    def test_base_height(self):
        assert "30 area" in triangle_area("base 10 height 6 triangle")

    def test_invalid_triangle(self):
        assert "ban hi nahi sakta" in triangle_area("1 2 10 triangle")

    def test_prompt(self):
        assert "3 sides do" in triangle_area("triangle area")


class TestVolume:
    def test_sphere(self):
        assert "523.60" in volume_calc("sphere radius 5 volume")

    def test_cube(self):
        assert "volume 64" in volume_calc("cube side 4")

    def test_cylinder(self):
        assert "282.74" in volume_calc("cylinder radius 3 height 10")

    def test_cone(self):
        assert "84.82" in volume_calc("cone radius 3 height 9")

    def test_no_shape(self):
        assert "Kaunsa shape" in volume_calc("volume batao")


class TestSkills:
    def test_triangle_skill(self):
        from skills.geometry_skill import triangle_area as t
        assert "area" in t({"raw_text": "3 4 5 triangle ka area"})

    def test_volume_skill(self):
        from skills.geometry_skill import volume_calc as v
        assert "volume" in v({"raw_text": "sphere radius 5 ka volume"})
