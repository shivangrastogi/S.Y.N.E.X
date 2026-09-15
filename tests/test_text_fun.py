"""Morse + palindrome + anagram (offline)."""

from __future__ import annotations

import pytest

from core.text_fun import (morse, to_morse, from_morse,
                          is_palindrome, are_anagram)


class TestMorse:
    def test_encode(self):
        assert to_morse("sos") == "... --- ..."

    def test_decode(self):
        assert from_morse("... --- ...") == "sos"

    def test_word_separator(self):
        assert "/" in to_morse("hi there")
        assert from_morse(".... .. / - .... . .-. .") == "hi there"

    def test_auto_detect_encode(self):
        assert morse("hello") == to_morse("hello")

    def test_auto_detect_decode(self):
        assert morse("... --- ...") == "sos"

    def test_roundtrip(self):
        for w in ("aeris", "shivang123", "hello world"):
            assert from_morse(to_morse(w)) == w

    def test_empty_none(self):
        assert morse("") is None
        assert to_morse("€£¥") is None      # all unknown (no morse mapping)

    def test_bad_morse_none(self):
        assert from_morse("hello") is None


class TestPalindrome:
    @pytest.mark.parametrize("text,is_pal", [
        ("madam", True),
        ("racecar", True),
        ("A man a plan a canal Panama", True),
        ("121", True),
        ("hello", False),
        ("world", False),
    ])
    def test_palindrome(self, text, is_pal):
        out = is_palindrome(text)
        assert ("Haan" in out) == is_pal

    def test_empty_none(self):
        assert is_palindrome("") is None
        assert is_palindrome("!!!") is None


class TestAnagram:
    @pytest.mark.parametrize("a,b,yes", [
        ("listen", "silent", True),
        ("dormitory", "dirty room", True),
        ("hello", "world", False),
        ("Elvis", "Lives", True),
    ])
    def test_anagram(self, a, b, yes):
        out = are_anagram(a, b)
        assert ("Haan" in out) == yes

    def test_empty_none(self):
        assert are_anagram("", "x") is None


class TestSkills:
    def test_morse_text_before_command(self):
        from skills.text_fun_skill import morse_code
        assert morse_code({"raw_text": "sos ko morse me karo"}) == "... --- ..."

    def test_morse_decode(self):
        from skills.text_fun_skill import morse_code
        assert morse_code({"raw_text": "... --- ... kya hai morse"}) == "sos"

    def test_palindrome_skill(self):
        from skills.text_fun_skill import palindrome_check
        assert "Haan" in palindrome_check({"raw_text": "madam palindrome hai kya"})

    def test_anagram_skill_word_order(self):
        from skills.text_fun_skill import anagram_check
        out = anagram_check({"raw_text": "listen aur silent anagram hain kya"})
        assert "Haan" in out

    def test_anagram_needs_two(self):
        from skills.text_fun_skill import anagram_check
        assert "Do words" in anagram_check({"raw_text": "anagram check karo"})


class TestTransform:
    def test_reverse(self):
        from core.text_fun import transform
        assert transform("hello", "reverse") == "olleh"

    def test_cases(self):
        from core.text_fun import transform
        assert transform("aeris", "upper") == "AERIS"
        assert transform("HELLO", "lower") == "hello"
        assert transform("hello world", "title") == "Hello World"
        assert transform("hello", "alternating") == "HeLlO"

    def test_reverse_words(self):
        from core.text_fun import transform
        assert transform("a b c", "reverse_words") == "c b a"

    def test_empty_none(self):
        from core.text_fun import transform
        assert transform("", "reverse") is None


class TestCountChars:
    def test_specific_letter(self):
        from core.text_fun import count_chars
        assert "3 baar" in count_chars("hello world", "l")

    def test_vowels_consonants(self):
        from core.text_fun import count_chars
        out = count_chars("aeris")
        assert "3 vowels" in out and "2 consonants" in out

    def test_empty_none(self):
        from core.text_fun import count_chars
        assert count_chars("") is None


class TestTransformSkills:
    def test_transform_reverse(self):
        from skills.text_fun_skill import text_transform
        assert text_transform({"raw_text": "reverse karo hello world"}) == "dlrow olleh"

    def test_transform_upper(self):
        from skills.text_fun_skill import text_transform
        assert text_transform({"raw_text": "capital letters me likho aeris"}) == "AERIS"

    def test_count_target_not_leaked(self):
        from skills.text_fun_skill import count_chars
        # regression: the "l" in "kitne l hain" must not be counted
        assert "'l' 3 baar" in count_chars({"raw_text": "hello world me kitne l hain"})

    def test_count_vowels(self):
        from skills.text_fun_skill import count_chars
        assert "vowels" in count_chars({"raw_text": "aeris me vowels kitne hain"})


class TestAcronym:
    def test_basic(self):
        from core.text_fun import acronym
        assert acronym("Ready Aim Fire") == "Ready Aim Fire = RAF"

    def test_skips_joining_words(self):
        from core.text_fun import acronym
        assert acronym("as soon as possible").endswith("ASAP")

    def test_empty_none(self):
        from core.text_fun import acronym
        assert acronym("") is None and acronym("!!!") is None

    def test_skill(self):
        from skills.text_fun_skill import acronym_maker
        out = acronym_maker({"raw_text": "ready aim fire ka acronym banao"})
        assert out.endswith("RAF")
