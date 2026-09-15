"""Screen PPI + thunder distance (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import ppi_calculator, thunder_distance


class TestPpi:
    def test_laptop(self):
        # 1920x1080, 15.6" -> ~141 PPI
        assert "141 PPI" in ppi_calculator("1920x1080 15.6 inch laptop")

    def test_phone_retina(self):
        out = ppi_calculator("2532x1170 6.1 inch iphone")
        assert "457 PPI" in out and "retina" in out

    def test_4k_monitor(self):
        assert "163 PPI" in ppi_calculator("3840x2160 27 inch")

    def test_prompt(self):
        assert "Resolution aur screen size" in ppi_calculator("ppi batao")


class TestThunder:
    def test_5_seconds(self):
        # 5 * 343 = 1715 m = 1.72 km
        assert "1.72 km" in thunder_distance("5 second baad thunder")

    def test_10_seconds(self):
        assert "3.43 km" in thunder_distance("bijli ke 10 seconds baad gadgadahat")

    def test_prompt(self):
        assert "gap tha" in thunder_distance("thunder kitni door")


class TestSkills:
    def test_ppi_skill(self):
        from skills.misc_calc_skill import ppi_calculator as p
        assert "PPI" in p({"raw_text": "1920x1080 15.6 inch ppi"})

    def test_thunder_skill(self):
        from skills.misc_calc_skill import thunder_distance as t
        assert "km" in t({"raw_text": "bijli ke 5 second baad thunder kitni door"})
