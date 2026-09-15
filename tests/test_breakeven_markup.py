"""Break-even + markup/margin (pure business math, offline)."""

from __future__ import annotations

from core.finance_math import break_even, markup_margin


class TestBreakEven:
    def test_units(self):
        # 50000/(200-120) = 625
        out = break_even("fixed 50000 price 200 variable cost 120")
        assert "625 units" in out and "125,000" in out

    def test_other_numbers(self):
        assert "500 units" in break_even(
            "fixed cost 100000 selling 500 per unit cost 300")

    def test_price_below_cost(self):
        out = break_even("fixed 10000 price 100 variable cost 150")
        assert "zyada honi chahiye" in out

    def test_prompt(self):
        assert "Fixed cost" in break_even("break even batao")


class TestMarkupMargin:
    def test_markup(self):
        # cost 100 markup 25% -> sell 125, margin 20%
        out = markup_margin("cost 100 markup 25%")
        assert "125" in out and "20.0%" in out

    def test_margin(self):
        # cost 100 margin 20% -> sell 125, markup 25%
        out = markup_margin("cost 100 margin 20%")
        assert "125" in out and "25.0%" in out

    def test_prompt(self):
        assert "Cost aur markup" in markup_margin("markup batao")


class TestSkills:
    def test_be_skill(self):
        from skills.finance_skill import break_even as b
        assert "units" in b({"raw_text": "fixed 50000 price 200 variable cost 120 break even"})

    def test_mm_skill(self):
        from skills.finance_skill import markup_margin as m
        assert "selling price" in m({"raw_text": "cost 100 markup 25% selling price"})
