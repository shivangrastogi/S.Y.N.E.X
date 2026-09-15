"""Prime list + z-score (pure math, offline)."""

from __future__ import annotations

from core.number_props import prime_list, z_score


class TestPrimeList:
    def test_range(self):
        out = prime_list("primes between 10 and 30")
        assert "11, 13, 17, 19, 23, 29" in out and "6 primes" in out

    def test_first_n(self):
        assert "2, 3, 5, 7, 11, 13, 17, 19, 23, 29" in prime_list("first 10 primes")

    def test_no_primes_in_range(self):
        assert "koi prime nahi" in prime_list("primes between 90 and 96")

    def test_prompt(self):
        assert "Range ya count" in prime_list("prime batao")


class TestZScore:
    def test_positive(self):
        assert "z-score = 1.5" in z_score("value 85 mean 70 std 10")

    def test_negative(self):
        assert "z-score = -2" in z_score("score 60 mean 70 sigma 5")

    def test_bare_numbers(self):
        assert "z-score = 1.5" in z_score("85 70 10")

    def test_prompt(self):
        assert "Value, mean aur std" in z_score("z score batao")


class TestSkills:
    def test_prime_skill(self):
        from skills.number_props_skill import prime_list as p
        assert "primes" in p({"raw_text": "10 aur 30 ke beech primes"})

    def test_zscore_skill(self):
        from skills.number_props_skill import z_score as z
        assert "z-score" in z({"raw_text": "value 85 mean 70 std 10 z score"})
