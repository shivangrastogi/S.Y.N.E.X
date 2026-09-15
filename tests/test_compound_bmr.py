"""Compound interest + BMR/calorie (pure formula, offline)."""

from __future__ import annotations

from core.finance_math import compound_interest
from core.health_calc import bmr_calorie


class TestCompound:
    def test_yearly_matches_formula(self):
        out = compound_interest("100000 pe 8% 5 saal compound")
        # 100000*1.08^5 = 146932.81
        assert "146,932" in out and "yearly" in out

    def test_quarterly_higher(self):
        out = compound_interest("100000 pe 8% 5 saal quarterly compound")
        assert "quarterly" in out and "148,594" in out

    def test_monthly(self):
        assert "monthly" in compound_interest("50000 pe 10% 2 saal monthly compound")

    def test_no_rate_none(self):
        assert compound_interest("compound interest nikalo") is None


class TestBMR:
    def test_male_matches_mifflin(self):
        # 10*70 + 6.25*175 - 5*28 + 5 = 1658.75 -> 1659
        out = bmr_calorie("weight 70 height 175 age 28 male")
        assert "1659" in out and "male" in out

    def test_female_uses_offset(self):
        # 10*60 + 6.25*165 - 5*30 - 161 = 1320.25 -> 1320
        out = bmr_calorie("vajan 60 lambai 165 age 30 female")
        assert "1320" in out and "female" in out

    def test_activity_detected(self):
        out = bmr_calorie("bmr 80 kg 180 cm 25 saal active")
        assert "active" in out

    def test_missing_age_prompts(self):
        assert "age" in bmr_calorie("weight 70 height 175")


class TestSkills:
    def test_compound_skill(self):
        from skills.finance_skill import compound_interest as c
        assert "Maturity" in c({"raw_text": "100000 pe 8% 5 saal compound"})

    def test_bmr_skill(self):
        from skills.health_split_skill import bmr_calorie as b
        assert "BMR" in b({"raw_text": "weight 70 height 175 age 28 male"})
