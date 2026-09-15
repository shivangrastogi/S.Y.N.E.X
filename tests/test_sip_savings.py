"""SIP maturity + savings goal (pure finance math, offline)."""

from __future__ import annotations

from core.finance_math import sip_calculator, savings_goal


class TestSip:
    def test_maturity_matches_formula(self):
        # 5000/month, 12%, 10y -> ~11,61,695
        out = sip_calculator("5000 monthly 12% 10 saal sip")
        assert "1,161,695" in out and "gain" in out

    def test_invested_shown(self):
        out = sip_calculator("10000 per month 10% 15 years")
        assert "Invested 1,800,000" in out

    def test_no_years(self):
        assert "monthly amount" in sip_calculator("sip 12%").lower()

    def test_no_rate_returns_none(self):
        assert sip_calculator("5000 monthly 10 saal") is None


class TestSavingsGoal:
    def test_simple_division(self):
        # 5 lakh / 24 = 20833
        out = savings_goal("5 lakh 2 saal me")
        assert "20,833" in out and "bina interest" in out

    def test_with_return(self):
        out = savings_goal("500000 3 saal 8%")
        assert "12,253" in out

    def test_prompt(self):
        assert "Target amount aur time" in savings_goal("paise jodne hain")


class TestSkills:
    def test_sip_skill(self):
        from skills.finance_skill import sip_calculator as s
        assert "maturity" in s({"raw_text": "5000 monthly 12% 10 saal sip"})

    def test_savings_skill(self):
        from skills.finance_skill import savings_goal as g
        assert "month" in g({"raw_text": "5 lakh 2 saal me kitna monthly bachau"})
