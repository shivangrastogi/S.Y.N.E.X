"""Unit-price comparison (pure math, offline)."""

from __future__ import annotations

from core.shopping_math import compare


class TestCompare:
    def test_volume_cheaper(self):
        out = compare("500ml 40 vs 1 litre 70")
        assert "1litre" in out and "cheaper" in out
        assert "70/litre" in out and "80/litre" in out

    def test_weight_cheaper(self):
        out = compare("250g 30 vs 1kg 100")
        assert "1kg" in out and "100/kg" in out and "120/kg" in out

    def test_dimension_mismatch(self):
        assert "compare nahi" in compare("500ml 40 vs 500g 30")

    def test_single_option_none(self):
        assert compare("sirf 500ml 40") is None

    def test_no_numbers_none(self):
        assert compare("kaunsa sasta hai") is None

    def test_pieces(self):
        out = compare("6 pcs 60 vs 12 pcs 100")
        assert "12pcs" in out or "12 pcs" in out.replace("pcs", " pcs")


class TestSkill:
    def test_price_skill(self):
        from skills.shopping_recipe_skill import unit_price_compare
        out = unit_price_compare(
            {"raw_text": "kaunsa sasta hai 500ml 40 vs 1 litre 70"})
        assert "cheaper" in out

    def test_price_skill_prompt(self):
        from skills.shopping_recipe_skill import unit_price_compare
        assert "Do options" in unit_price_compare({"raw_text": "sasta kaunsa"})
