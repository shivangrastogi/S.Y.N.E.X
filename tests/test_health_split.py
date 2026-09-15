"""BMI + bill-split (offline)."""

from __future__ import annotations

import re

import pytest

from core.health_calc import bmi
from core.finance_math import bill_split


def _bmi_val(s: str) -> float:
    return float(re.search(r"BMI = ([\d.]+)", s).group(1))


class TestBMI:
    def test_normal(self):
        out = bmi("height 170 weight 70 bmi")
        assert abs(_bmi_val(out) - 24.2) < 0.1 and "normal" in out

    def test_order_independent(self):
        out = bmi("weight 90 height 175")
        assert "175cm" in out and "90kg" in out and "overweight" in out

    def test_metres_height(self):
        out = bmi("height 1.8 weight 65")
        assert "180cm" in out

    def test_feet_inches(self):
        out = bmi("5'9 height weight 70 bmi")
        assert "175cm" in out

    def test_units_in_text(self):
        out = bmi("70 kg 170 cm bmi")
        assert abs(_bmi_val(out) - 24.2) < 0.1

    def test_single_number_none(self):
        # can't be both height and weight
        assert bmi("height 170") is None

    def test_no_numbers_none(self):
        assert bmi("bmi calculate karo") is None

    def test_ht_in_weight_not_confused(self):
        # regression: "ht" inside "weight" must not parse as height
        out = bmi("weight 80 height 180")
        assert "180cm" in out and "80kg" in out


class TestBillSplit:
    def test_basic(self):
        out = bill_split("1200 ka bill 4 log me baato")
        assert "300 per person" in out

    def test_with_tip(self):
        out = bill_split("1000 ka bill 5 logon me 10% tip ke sath")
        assert "220 per person" in out and "10% tip" in out

    def test_people_variants(self):
        assert "250 per person" in bill_split("500 bill 2 people")

    def test_no_people_none(self):
        assert bill_split("1200 ka bill") is None

    def test_no_numbers_none(self):
        assert bill_split("bill baato") is None


class TestSkills:
    def test_bmi_skill_prompt(self):
        from skills.health_split_skill import bmi_calc
        assert "Height aur weight" in bmi_calc({"raw_text": "bmi nikalo"})

    def test_split_skill(self):
        from skills.health_split_skill import bill_split as skill
        assert "300 per person" in skill(
            {"raw_text": "1200 ka bill 4 log me baato"})
