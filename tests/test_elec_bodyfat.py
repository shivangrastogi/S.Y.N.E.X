"""Electricity bill + body-fat estimate (pure math, offline)."""

from __future__ import annotations

from core.finance_math import electricity_bill
from core.health_calc import body_fat


class TestElectricity:
    def test_flat_rate(self):
        # 350 * 8 = 2800
        assert "2,800" in electricity_bill("350 units 8 rupee")

    def test_slab_estimate(self):
        # 100*4 + 100*5.5 + 150*7 = 2000
        assert "2,000" in electricity_bill("350 units")

    def test_low_units_slab(self):
        # 100*4 + 20*5.5 = 510
        assert "510" in electricity_bill("120 units")

    def test_prompt(self):
        assert "Kitne units" in electricity_bill("bijli bill batao")


class TestBodyFat:
    def test_male_deurenberg(self):
        # BMI 22.86 -> BF 17.7
        out = body_fat("weight 70 height 175 age 28 male")
        assert "17.7%" in out and "male" in out

    def test_female_lower_sex_term(self):
        out = body_fat("vajan 60 lambai 165 age 30 female")
        assert "female" in out and "%" in out

    def test_missing_prompts(self):
        assert "weight, height aur age" in body_fat("body fat batao")


class TestSkills:
    def test_elec_skill(self):
        from skills.finance_skill import electricity_bill as e
        assert "units" in e({"raw_text": "350 units 8 rupee bill"})

    def test_bodyfat_skill(self):
        from skills.health_split_skill import body_fat as b
        assert "Body fat" in b({"raw_text": "weight 70 height 175 age 28 male"})
