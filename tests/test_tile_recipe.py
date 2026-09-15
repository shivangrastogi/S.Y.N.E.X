"""Tile count + recipe scaling (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import tile_count, recipe_scale


class TestTileCount:
    def test_feet_tiles_wastage_integer(self):
        # 200/4 = 50 tiles, +10% = 55 (no float 56 bug)
        assert "50 tiles, 55 with" in tile_count("200 sqft floor 2x2 feet tiles")

    def test_inch_tiles(self):
        assert "300 tiles, 330" in tile_count("300 sqft 12x12 inch tiles")

    def test_mm_tiles(self):
        assert "43 with" in tile_count("150 sqft 600x600 mm tiles")

    def test_no_area_prompt(self):
        assert "Floor area" in tile_count("2x2 feet tiles")


class TestRecipeScale:
    def test_serving_ratio(self):
        assert "1.5x" in recipe_scale("4 log ki recipe 6 ke liye")

    def test_double_keyword(self):
        assert "2x" in recipe_scale("double the recipe")

    def test_half_keyword(self):
        assert "0.5x" in recipe_scale("recipe half karni hai")

    def test_prompt(self):
        assert "Original aur target" in recipe_scale("recipe scale karo")


class TestSkills:
    def test_tile_skill(self):
        from skills.misc_calc_skill import tile_count as t
        assert "tiles" in t({"raw_text": "200 sqft floor 2x2 feet tiles kitne"})

    def test_recipe_skill(self):
        from skills.misc_calc_skill import recipe_scale as r
        assert "x" in r({"raw_text": "4 log ki recipe 6 ke liye scale karo"})
