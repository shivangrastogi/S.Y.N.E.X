"""Everyday money math + password strength (offline, deterministic)."""

from __future__ import annotations

import re

import pytest

from core import finance_math as fm


def _emi_value(s: str) -> float:
    """Pull the per-month EMI figure (after 'EMI ~') from the reply."""
    return float(re.search(r"EMI ~([\d,]+(?:\.\d+)?)", s)
                 .group(1).replace(",", ""))


class TestDiscount:
    def test_basic(self):
        out = fm.discount("1500 pe 20 percent off")
        assert "discount 300" in out and "final price 1,200" in out

    def test_word_order_independent(self):
        out = fm.discount("20% off on 1500")
        assert "1,200" in out

    def test_none_without_pct(self):
        assert fm.discount("1500 rupaye") is None


class TestGstTip:
    def test_gst_adds(self):
        out = fm.add_percent("2000 pe 18% gst", "GST")
        assert "GST 360" in out and "total 2,360" in out

    def test_tip(self):
        out = fm.tip("800 pe 10% tip")
        assert "tip 80" in out and "880" in out


class TestSimpleInterest:
    def test_with_years_word(self):
        out = fm.simple_interest("10000 pe 8% 3 saal")
        assert "2,400" in out and "12,400" in out

    def test_needs_two_numbers(self):
        assert fm.simple_interest("10000 pe 8%") is None


class TestEMI:
    def test_months(self):
        out = fm.emi("500000 loan 12% 24 months")
        # standard EMI for 5L @12%/24mo ≈ 23537
        assert abs(_emi_value(out) - 23537) < 5

    def test_years_converted(self):
        out = fm.emi("500000 loan 10% 5 saal")
        assert abs(_emi_value(out) - 10624) < 5

    def test_zero_rate(self):
        out = fm.emi("120000 loan 0% 12 months")
        assert "10,000" in out          # 120000/12

    def test_missing_tenure_none(self):
        assert fm.emi("500000 loan 12%") is None


class TestPasswordStrength:
    def test_common_word_penalised(self):
        assert "KAMZOR" in fm.password_strength("shivang123")

    def test_repeated_chars_penalised(self):
        assert "KAMZOR" in fm.password_strength("aaabbbccc")

    def test_strong(self):
        out = fm.password_strength("Tr0ub4dor&3xK!99")
        assert "STRONG" in out and "4/4" in out

    def test_short_weak(self):
        assert "WEAK" in fm.password_strength("Ab1!")

    def test_empty(self):
        assert "nahi mila" in fm.password_strength("")

    def test_entropy_reported(self):
        assert "bits entropy" in fm.password_strength("SomeP@ss123")


class TestSkills:
    def test_discount_skill(self):
        from skills.finance_skill import discount_calc
        assert "1,200" in discount_calc({"raw_text": "1500 pe 20% off"})

    def test_emi_skill_prompt(self):
        from skills.finance_skill import emi_calc
        assert "months" in emi_calc({"raw_text": "emi calculate karo"})

    def test_password_skill_strips_prefix(self, monkeypatch):
        from skills.security_skill import password_strength
        out = password_strength(
            {"raw_text": "password strength check karo Tr0ub4dor&3xK!99"})
        assert "STRONG" in out

    def test_password_skill_no_pw(self):
        from skills.security_skill import password_strength
        assert "Kaunsa password" in password_strength(
            {"raw_text": "password strength check karo"})

    def test_gst_skill_tax_label(self):
        from skills.finance_skill import gst_calc
        out = gst_calc({"raw_text": "2000 pe 10% tax add karo"})
        assert "Tax" in out
