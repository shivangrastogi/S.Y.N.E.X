"""CAGR + down payment (pure finance math, offline)."""

from __future__ import annotations

from core.finance_math import cagr, down_payment


class TestCagr:
    def test_doubling(self):
        # (2/1)^(1/5)-1 = 14.87%
        out = cagr("1 lakh se 2 lakh 5 saal me")
        assert "14.87%" in out and "100.0%" in out

    def test_tripling(self):
        assert "44.22%" in cagr("50000 se 150000 3 years")

    def test_prompt(self):
        assert "Start value" in cagr("cagr batao")


class TestDownPayment:
    def test_lakh(self):
        out = down_payment("50 lakh ghar 20% down payment")
        assert "1,000,000 down" in out and "4,000,000 loan" in out

    def test_plain_number(self):
        out = down_payment("8000000 home 15% down")
        assert "1,200,000 down" in out and "6,800,000 loan" in out

    def test_prompt(self):
        assert "Price aur down" in down_payment("down payment kitna")


class TestSkills:
    def test_cagr_skill(self):
        from skills.finance_skill import cagr as c
        assert "CAGR" in c({"raw_text": "1 lakh se 2 lakh 5 saal cagr"})

    def test_dp_skill(self):
        from skills.finance_skill import down_payment as d
        assert "loan" in d({"raw_text": "50 lakh ghar 20% down payment kitna"})
