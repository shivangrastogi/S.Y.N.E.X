"""Profit/loss + heat-index feels-like (pure math, offline)."""

from __future__ import annotations

from core.finance_math import profit_loss
from core.misc_calc import heat_index


class TestProfitLoss:
    def test_profit(self):
        out = profit_loss("kharida 100 becha 150")
        assert "Profit" in out and "50.00%" in out

    def test_loss(self):
        out = profit_loss("cost 200 sold 150")
        assert "Loss" in out and "25.00%" in out

    def test_breakeven(self):
        assert "No profit no loss" in profit_loss("bought at 500 sold at 500")

    def test_bare_numbers(self):
        out = profit_loss("80 100")
        assert "Profit" in out and "25.00%" in out

    def test_prompt(self):
        assert "Cost price" in profit_loss("profit batao")


class TestHeatIndex:
    def test_hot_humid(self):
        out = heat_index("35 degree 60% humidity")
        assert "feels like" in out and "45" in out

    def test_humidity_after_keyword(self):
        # regression: 'humidity 70' must not grab the temp number
        out = heat_index("temp 30 humidity 70")
        assert "70% humidity" in out

    def test_reversed_order(self):
        out = heat_index("humidity 65 temp 38")
        assert "38" in out and "65% humidity" in out

    def test_mild_same(self):
        assert "same" in heat_index("20 degree 40% humidity")

    def test_prompt(self):
        assert "Temperature aur humidity" in heat_index("garmi kaisi hai")


class TestSkills:
    def test_profit_skill(self):
        from skills.finance_skill import profit_loss as p
        assert "%" in p({"raw_text": "kharida 100 becha 150"})

    def test_heat_skill(self):
        from skills.misc_calc_skill import heat_index as h
        assert "feels" in h({"raw_text": "35 degree 60% humidity feels like"})
