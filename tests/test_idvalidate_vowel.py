"""ID format validation + vowel/consonant count (offline)."""

from __future__ import annotations

from core.dev_format import id_validate
from core.text_fun import vowel_consonant


class TestIdValidate:
    def test_valid_pan(self):
        assert "valid PAN" in id_validate("ABCDE1234F PAN valid hai kya")

    def test_invalid_pan(self):
        assert "nahi lag raha" in id_validate("ABCD1234 pan check")

    def test_valid_ifsc(self):
        assert "valid IFSC" in id_validate("SBIN0001234 ifsc check karo")

    def test_invalid_ifsc_fifth_char(self):
        # 5th char must be 0
        assert "nahi lag raha" in id_validate("SBIN1001234 ifsc valid")

    def test_valid_pin(self):
        assert "valid PIN code" in id_validate("110001 pincode sahi hai")

    def test_invalid_pin_leading_zero(self):
        assert "nahi lag raha" in id_validate("012345 pin check")

    def test_prompt(self):
        assert "Number/code batao" in id_validate("validate karo")


class TestVowelConsonant:
    def test_counts(self):
        out = vowel_consonant("hello world me kitne vowels")
        assert "3 vowels" in out and "7 consonants" in out

    def test_quoted_with_digits(self):
        out = vowel_consonant('"Programming 101"')
        assert "3 digits" in out

    def test_prompt(self):
        assert "Kaunsa text" in vowel_consonant("vowels batao")


class TestSkills:
    def test_id_skill(self):
        from skills.dev_format_skill import id_validate as i
        assert "PAN" in i({"raw_text": "ABCDE1234F pan valid hai kya"})

    def test_vowel_skill(self):
        from skills.text_fun_skill import vowel_consonant as v
        assert "vowels" in v({"raw_text": "hello world me kitne vowels"})
