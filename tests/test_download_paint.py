"""Download time + paint quantity (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import download_time, paint_quantity


class TestDownload:
    def test_2gb_20mbps(self):
        # 2000 MB * 8 / 20 = 800s = 13 min 20 sec
        assert "13 min 20 sec" in download_time("2 GB 20 mbps")

    def test_mb(self):
        assert "9 min 20 sec" in download_time("700 mb 10 mbps")

    def test_hours(self):
        assert "22 hr" in download_time("1 tb 100 mbps")

    def test_prompt(self):
        assert "File size aur speed" in download_time("kitni der download")


class TestPaint:
    def test_sqft_two_coats(self):
        # 500/110*2 = 9.09 -> 9.1
        assert "9.1 litre" in paint_quantity("500 sqft paint")

    def test_dimensions_three_coats(self):
        # 120/110*3 = 3.27 -> 3.3
        assert "3.3 litre" in paint_quantity("10 by 12 feet wall 3 coat")

    def test_prompt(self):
        assert "area ya dimensions" in paint_quantity("paint kitna")


class TestSkills:
    def test_download_skill(self):
        from skills.misc_calc_skill import download_time as d
        assert "Mbps" in d({"raw_text": "2 gb file 20 mbps me kitni der"})

    def test_paint_skill(self):
        from skills.misc_calc_skill import paint_quantity as p
        assert "litre" in p({"raw_text": "500 sqft wall ke liye kitna paint"})
