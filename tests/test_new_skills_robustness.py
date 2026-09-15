"""Robustness guard for the /loop standalone abilities.

32+ new pure-compute skills share helpers (normalizer, parsers, fmt).
A change to one helper can silently break another's empty/garbage-input
handling. This guard calls every SAFE (no side effect, no heavy IO)
handler with empty slots and with garbage text, asserting each returns a
non-empty string and never raises. Side-effecting skills (keep_awake,
empty_recycle_bin, app launch, disk walks) are deliberately excluded.
"""

from __future__ import annotations

import importlib

import pytest

# (module, handler) pairs — pure compute / text only.
_SAFE = [
    ("skills.datetime_skill", "world_time"),
    ("skills.datetime_skill", "date_math"),
    ("skills.datetime_skill", "days_until"),
    ("skills.datetime_skill", "age_calc"),
    ("skills.datetime_skill", "day_of_week"),
    ("skills.datetime_skill", "time_until"),
    ("skills.datetime_skill", "timezone_convert"),
    ("skills.text_stats_skill", "text_stats"),
    ("skills.text_fun_skill", "morse_code"),
    ("skills.text_fun_skill", "palindrome_check"),
    ("skills.text_fun_skill", "anagram_check"),
    ("skills.text_fun_skill", "text_transform"),
    ("skills.text_fun_skill", "count_chars"),
    ("skills.text_fun_skill", "acronym_maker"),
    ("skills.number_props_skill", "number_properties"),
    ("skills.number_props_skill", "caesar_cipher"),
    ("skills.gcd_ratio_skill", "gcd_lcm"),
    ("skills.gcd_ratio_skill", "simplify_ratio"),
    ("skills.gcd_ratio_skill", "number_stats"),
    ("skills.gcd_ratio_skill", "factorial_power"),
    ("skills.shopping_recipe_skill", "unit_price_compare"),
    ("skills.calendar_word_skill", "leap_year_check"),
    ("skills.calendar_word_skill", "days_in_month"),
    ("skills.gen_tools_skill", "password_generate"),
    ("skills.gen_tools_skill", "text_hash"),
    ("skills.gen_tools_skill", "uuid_generate"),
    ("skills.codec_tools_skill", "hex_convert"),
    ("skills.codec_tools_skill", "reading_time"),
    ("skills.dev_format_skill", "json_format"),
    ("skills.dev_format_skill", "url_convert"),
    ("skills.dev_format_skill", "slugify"),
    ("skills.finance_skill", "compound_interest"),
    ("skills.health_split_skill", "bmr_calorie"),
    ("skills.misc_calc_skill", "zodiac_sign"),
    ("skills.misc_calc_skill", "running_pace"),
    ("skills.fuel_water_skill", "fuel_trip_cost"),
    ("skills.fuel_water_skill", "water_intake"),
    ("skills.life_calc_skill", "marks_percentage"),
    ("skills.life_calc_skill", "sleep_cycle"),
    ("skills.life_calc_skill", "cgpa_percentage"),
    ("skills.misc_calc_skill", "numerology"),
    ("skills.finance_skill", "profit_loss"),
    ("skills.misc_calc_skill", "heat_index"),
    ("skills.misc_calc_skill", "travel_time"),
    ("skills.finance_skill", "discount_stack"),
    ("skills.group_calc_skill", "team_split"),
    ("skills.group_calc_skill", "calories_burned"),
    ("skills.festival_zodiac_skill", "festival_countdown"),
    ("skills.festival_zodiac_skill", "chinese_zodiac"),
    ("skills.fun_calc_skill", "weekend_countdown"),
    ("skills.fun_calc_skill", "scrabble_score"),
    ("skills.misc_calc_skill", "area_calc"),
    ("skills.health_split_skill", "ideal_weight"),
    ("skills.finance_skill", "electricity_bill"),
    ("skills.health_split_skill", "body_fat"),
    ("skills.misc_calc_skill", "wind_chill"),
    ("skills.fun_calc_skill", "week_number"),
    ("skills.finance_skill", "overtime_pay"),
    ("skills.misc_calc_skill", "dew_point"),
    ("skills.misc_calc_skill", "download_time"),
    ("skills.misc_calc_skill", "paint_quantity"),
    ("skills.misc_calc_skill", "tile_count"),
    ("skills.misc_calc_skill", "recipe_scale"),
    ("skills.misc_calc_skill", "ppi_calculator"),
    ("skills.misc_calc_skill", "thunder_distance"),
    ("skills.misc_calc_skill", "ohms_law"),
    ("skills.misc_calc_skill", "battery_life"),
    ("skills.finance_skill", "appliance_power_cost"),
    ("skills.misc_calc_skill", "frequency_wavelength"),
    ("skills.geometry_skill", "circle_calc"),
    ("skills.geometry_skill", "pythagoras"),
    ("skills.geometry_skill", "triangle_area"),
    ("skills.geometry_skill", "volume_calc"),
    ("skills.number_props_skill", "combinations_permutations"),
    ("skills.number_props_skill", "quadratic_solver"),
    ("skills.number_props_skill", "trig_calc"),
    ("skills.number_props_skill", "log_calc"),
    ("skills.number_props_skill", "sequence_calc"),
    ("skills.number_props_skill", "fibonacci"),
    ("skills.number_props_skill", "variance_std"),
    ("skills.misc_calc_skill", "led_resistor"),
    ("skills.geometry_skill", "coordinate_distance"),
    ("skills.number_props_skill", "weighted_average"),
    ("skills.number_props_skill", "prime_list"),
    ("skills.number_props_skill", "z_score"),
    ("skills.number_props_skill", "percent_error"),
    ("skills.number_props_skill", "scientific_notation"),
    ("skills.fractions_skill", "fraction_convert"),
    ("skills.fractions_skill", "fraction_math"),
    ("skills.number_props_skill", "proportion_solve"),
    ("skills.number_props_skill", "rounding_sigfig"),
    ("skills.fractions_skill", "mixed_number"),
    ("skills.misc_calc_skill", "beaufort_scale"),
    ("skills.misc_calc_skill", "aqi_category"),
    ("skills.number_props_skill", "modulo_calc"),
    ("skills.misc_calc_skill", "decibel_scale"),
    ("skills.misc_calc_skill", "richter_scale"),
    ("skills.health_split_skill", "heart_rate_zones"),
    ("skills.misc_calc_skill", "uv_index"),
    ("skills.health_split_skill", "one_rep_max"),
    ("skills.health_split_skill", "calorie_deficit"),
    ("skills.number_props_skill", "base_arithmetic"),
    ("skills.health_split_skill", "protein_needs"),
    ("skills.misc_calc_skill", "average_speed"),
    ("skills.misc_calc_skill", "work_rate"),
    ("skills.physics_skill", "force_calc"),
    ("skills.physics_skill", "energy_calc"),
    ("skills.physics_skill", "density_calc"),
    ("skills.physics_skill", "pressure_calc"),
    ("skills.physics_skill", "momentum_calc"),
    ("skills.physics_skill", "work_power"),
    ("skills.finance_skill", "sip_calculator"),
    ("skills.finance_skill", "savings_goal"),
    ("skills.finance_skill", "inflation_adjust"),
    ("skills.finance_skill", "rule_of_72"),
    ("skills.finance_skill", "cagr"),
    ("skills.finance_skill", "down_payment"),
    ("skills.finance_skill", "break_even"),
    ("skills.finance_skill", "markup_margin"),
    ("skills.finance_skill", "gst_inclusive"),
    ("skills.codec_tools_skill", "ascii_value"),
    ("skills.dev_format_skill", "id_validate"),
    ("skills.text_fun_skill", "vowel_consonant"),
    ("skills.fun_calc_skill", "ordinal_number"),
    ("skills.fun_calc_skill", "duration_humanize"),
    ("skills.fun_calc_skill", "next_birthday"),
    ("skills.dev_format_skill", "luhn_check"),
    ("skills.random_skill", "coin_toss"),
    ("skills.random_skill", "dice_roll"),
    ("skills.random_skill", "random_number"),
    ("skills.random_skill", "random_pick"),
    ("skills.unit_convert_skill", "unit_convert"),
    ("skills.finance_skill", "discount_calc"),
    ("skills.finance_skill", "gst_calc"),
    ("skills.finance_skill", "tip_calc"),
    ("skills.finance_skill", "emi_calc"),
    ("skills.finance_skill", "simple_interest"),
    ("skills.finance_skill", "percent_change"),
    ("skills.health_split_skill", "bmi_calc"),
    ("skills.health_split_skill", "bill_split"),
    ("skills.security_skill", "password_strength"),
    ("skills.number_words_skill", "number_to_words"),
    ("skills.dev_tools_skill", "base_convert"),
    ("skills.dev_tools_skill", "phonetic_spell"),
    ("skills.color_roman_skill", "color_convert"),
    ("skills.color_roman_skill", "roman_convert"),
    ("skills.stopwatch_skill", "stopwatch_check"),   # in-memory, safe
    ("skills.stopwatch_skill", "stopwatch_stop"),
]

# Garbage inputs that must never crash a parser.
_GARBAGE = [
    "", "   ", "!!!", "aaaa bbbb cccc", "123 456 789 000",
    "\n\t", "kya kaise kyun", "%%% ### @@@", "0", "-", ".",
    "12.34.56", "9" * 200, "😀 emoji test", "SELECT * FROM x",
]


def _handler(mod_name, fn_name):
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


@pytest.mark.parametrize("mod_name,fn_name", _SAFE,
                         ids=[f"{m.split('.')[-1]}.{f}" for m, f in _SAFE])
class TestEmptyAndGarbage:
    def test_empty_slots(self, mod_name, fn_name):
        fn = _handler(mod_name, fn_name)
        out = fn({})
        assert isinstance(out, str) and out.strip(), \
            f"{fn_name} returned empty on {{}}"

    def test_no_raw_text_key(self, mod_name, fn_name):
        fn = _handler(mod_name, fn_name)
        out = fn({"something_else": "x"})
        assert isinstance(out, str) and out.strip()

    def test_garbage_inputs(self, mod_name, fn_name):
        fn = _handler(mod_name, fn_name)
        for g in _GARBAGE:
            out = fn({"raw_text": g})
            assert isinstance(out, str) and out.strip(), \
                f"{fn_name} failed on {g!r}"


class TestFileSkillsGracefulOnBadPath:
    """File skills must degrade cleanly on a nonexistent path (no crash,
    no real disk walk of the user's home)."""

    def test_folder_stats(self):
        from skills.file_tools_skill import folder_stats
        out = folder_stats({"raw_text": r"stats C:\no\such\folder\zzz"})
        assert isinstance(out, str) and out.strip()

    def test_find_large_files_bad_path(self):
        from skills.file_tools_skill import find_large_files
        out = find_large_files({"raw_text": r"bade files C:\no\such\zzz"})
        assert "nahi mila" in out

    def test_read_file_aloud_missing(self):
        from skills.file_tools_skill import read_file_aloud
        out = read_file_aloud({"raw_text": r"padho C:\no\such\file.txt"})
        assert isinstance(out, str) and out.strip()


class TestRegistrationIntegrity:
    """Every /loop skill is registered exactly once and has patterns."""

    def test_all_registered_with_patterns(self):
        from core.skill_registry import discover_skills, REGISTRY
        discover_skills("skills")
        for _mod, fn_name in _SAFE:
            assert fn_name in REGISTRY, f"{fn_name} not registered"
            assert REGISTRY[fn_name].patterns, f"{fn_name} has no patterns"
