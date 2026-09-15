"""Number properties + Caesar/ROT13 cipher (offline)."""

from __future__ import annotations

import pytest

from core.number_props import (properties, cipher, caesar,
                              _is_prime, _factors, _prime_factorisation)


class TestPrimality:
    @pytest.mark.parametrize("n,is_p", [
        (2, True), (3, True), (17, True), (97, True), (7919, True),
        (0, False), (1, False), (4, False), (24, False), (100, False),
    ])
    def test_is_prime(self, n, is_p):
        assert _is_prime(n) == is_p


class TestFactors:
    def test_factors(self):
        assert _factors(24) == [1, 2, 3, 4, 6, 8, 12, 24]

    def test_prime_factorisation(self):
        assert _prime_factorisation(24) == [2, 2, 2, 3]
        assert _prime_factorisation(100) == [2, 2, 5, 5]
        assert _prime_factorisation(17) == [17]


class TestProperties:
    def test_prime_odd(self):
        out = properties("17 prime hai kya")
        assert "odd" in out and "prime" in out and "not prime" not in out

    def test_composite_even(self):
        out = properties("24 ke factors")
        assert "even" in out and "not prime" in out and "2 x 2 x 2 x 3" in out

    def test_one_and_zero(self):
        assert "odd" in properties("1")
        assert "even" in properties("0")

    def test_negative(self):
        assert "even" in properties("-8 even ya odd")

    def test_no_number_none(self):
        assert properties("kuch bhi") is None


class TestCipher:
    def test_rot13(self):
        assert cipher("hello") == "uryyb"

    def test_rot13_roundtrip(self):
        assert cipher(cipher("Secret Msg 123!")) == "Secret Msg 123!"

    def test_caesar_shift(self):
        assert caesar("abc", 5) == "fgh"
        assert caesar("xyz", 3) == "abc"       # wraps

    def test_preserves_non_letters(self):
        assert cipher("a1 b!") == "n1 o!"

    def test_empty_none(self):
        assert cipher("") is None


class TestSkills:
    def test_properties_skill(self):
        from skills.number_props_skill import number_properties
        assert "48:" in number_properties({"raw_text": "48 ke factors batao"})

    def test_cipher_encode(self):
        from skills.number_props_skill import caesar_cipher
        out = caesar_cipher({"raw_text": "rot13 karo hello world"})
        assert "uryyb jbeyq" in out

    def test_cipher_decode(self):
        from skills.number_props_skill import caesar_cipher
        out = caesar_cipher({"raw_text": "rot13 decode karo uryyb"})
        assert "hello" in out and "decoded" in out

    def test_cipher_custom_shift(self):
        from skills.number_props_skill import caesar_cipher
        out = caesar_cipher({"raw_text": "5 shift karo secret"})
        assert "xjhwjy" in out and "ROT5" in out


class TestGcdLcm:
    def test_two_numbers(self):
        from core.number_props import gcd_lcm
        out = gcd_lcm("gcd lcm 12 aur 18")
        assert "GCD/HCF = 6" in out and "LCM = 36" in out

    def test_three_numbers(self):
        from core.number_props import gcd_lcm
        out = gcd_lcm("24 36 48")
        assert "= 12" in out and "144" in out

    def test_coprime(self):
        from core.number_props import gcd_lcm
        assert "GCD/HCF = 1" in gcd_lcm("7 aur 13")

    def test_single_none(self):
        from core.number_props import gcd_lcm
        assert gcd_lcm("sirf 5") is None


class TestSimplifyRatio:
    def test_simplify(self):
        from core.number_props import simplify_ratio
        assert "2:3" in simplify_ratio("8 12 ratio")

    def test_already_simplest(self):
        from core.number_props import simplify_ratio
        assert "simplest" in simplify_ratio("7 13 ratio")

    def test_zero_guard(self):
        from core.number_props import simplify_ratio
        assert "zero" in simplify_ratio("5 0 ratio")

    def test_single_none(self):
        from core.number_props import simplify_ratio
        assert simplify_ratio("8") is None


class TestGcdRatioSkills:
    def test_gcd_skill(self):
        from skills.gcd_ratio_skill import gcd_lcm
        assert "GCD/HCF = 6" in gcd_lcm({"raw_text": "gcd lcm nikalo 12 aur 18"})

    def test_ratio_skill(self):
        from skills.gcd_ratio_skill import simplify_ratio
        assert "2:3" in simplify_ratio({"raw_text": "ratio simplify karo 8 12"})


class TestStats:
    def test_average_sum(self):
        from core.number_props import stats
        out = stats("average 10 20 30")
        assert "sum 60" in out and "average 20" in out and "median 20" in out

    def test_median_even_count(self):
        from core.number_props import stats
        assert "median 12.5" in stats("5 10 15 20")

    def test_min_max(self):
        from core.number_props import stats
        out = stats("3 1 4 1 5")
        assert "min 1" in out and "max 5" in out

    def test_single_none(self):
        from core.number_props import stats
        assert stats("sirf 5") is None


class TestFactorialPower:
    def test_factorial(self):
        from core.number_props import factorial
        assert factorial("5 factorial") == "5! = 120"
        assert factorial("0 factorial") == "0! = 1"

    def test_factorial_cap(self):
        from core.number_props import factorial
        assert "bada" in factorial("2000 factorial")

    def test_power(self):
        from core.number_props import power
        assert power("2 power 10") == "2 power 10 = 1024"

    def test_square_cube(self):
        from core.number_props import power
        assert power("5 ka square") == "5 square = 25"
        assert power("3 cube") == "3 cube = 27"

    def test_power_cap(self):
        from core.number_props import power
        assert "mushkil" in power("5 power 999")

    def test_no_power_none(self):
        from core.number_props import power
        assert power("just text") is None


class TestStatsFactorialSkills:
    def test_stats_skill(self):
        from skills.gcd_ratio_skill import number_stats
        assert "average 25" in number_stats({"raw_text": "average 10 20 30 40"})

    def test_factorial_skill(self):
        from skills.gcd_ratio_skill import factorial_power
        assert "720" in factorial_power({"raw_text": "6 factorial"})

    def test_power_skill(self):
        from skills.gcd_ratio_skill import factorial_power
        assert "1024" in factorial_power({"raw_text": "2 power 10"})
