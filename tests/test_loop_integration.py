"""End-to-end integration for the /loop standalone abilities.

Handler unit tests prove the LOGIC; this proves the WIRING: every new
intent's own first pattern must route back to that intent through the
LIVE IntentClassifier's exact-match path (registry → intent_loader →
normalizer → exact lookup). Exact-match needs no encoder, so this stays
fast. Catches: a pattern that collides/normalises onto another intent, a
skill that failed to register, a normalizer change that breaks a phrase.
"""

from __future__ import annotations

import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The abilities added across the /loop iterations.
_NEW_INTENTS = [
    "world_time", "date_math", "days_until", "age_calc", "day_of_week",
    "time_until", "timezone_convert",
    "coin_toss", "dice_roll", "random_number", "random_pick",
    "unit_convert", "discount_calc", "gst_calc", "tip_calc", "emi_calc",
    "simple_interest", "percent_change", "bmi_calc", "bill_split",
    "password_strength", "number_to_words", "base_convert", "phonetic_spell",
    "color_convert", "roman_convert", "stopwatch_start", "stopwatch_check",
    "stopwatch_stop", "folder_stats", "find_large_files", "read_file_aloud",
    "disk_space", "top_process", "system_uptime", "keep_awake_on",
    "keep_awake_off", "empty_recycle_bin", "text_stats", "morse_code",
    "palindrome_check", "anagram_check", "text_transform", "count_chars",
    "acronym_maker", "number_properties", "caesar_cipher",
    "gcd_lcm", "simplify_ratio", "number_stats", "factorial_power",
    "fix_grammar", "brainstorm_ideas", "explain_simply",
    "make_title", "shorten_text", "define_word",
    "pros_cons", "how_to_steps",
    "write_poem", "motivate_me", "tell_joke",
    "tell_story", "tell_riddle",
    "synonyms_antonyms", "rephrase_text",
    "fun_fact", "give_compliment",
    "unit_price_compare", "recipe_suggest",
    "leap_year_check", "days_in_month", "rhyming_words",
    "password_generate", "text_hash", "uuid_generate",
    "hex_convert", "reading_time",
    "json_format", "url_convert", "slugify",
    "compound_interest", "bmr_calorie",
    "zodiac_sign", "running_pace",
    "fuel_trip_cost", "water_intake",
    "marks_percentage", "sleep_cycle",
    "cgpa_percentage", "numerology",
    "profit_loss", "heat_index",
    "travel_time", "discount_stack",
    "team_split", "calories_burned",
    "festival_countdown", "chinese_zodiac",
    "weekend_countdown", "scrabble_score",
    "area_calc", "ideal_weight",
    "electricity_bill", "body_fat",
    "wind_chill", "week_number",
    "overtime_pay", "dew_point",
    "download_time", "paint_quantity",
    "tile_count", "recipe_scale",
    "sip_calculator", "savings_goal",
    "inflation_adjust", "rule_of_72",
    "cagr", "down_payment",
    "break_even", "markup_margin",
    "gst_inclusive", "ascii_value",
    "id_validate", "vowel_consonant",
    "ordinal_number", "duration_humanize",
    "next_birthday", "luhn_check",
    "ppi_calculator", "thunder_distance",
    "ohms_law", "battery_life",
    "appliance_power_cost", "frequency_wavelength",
    "circle_calc", "pythagoras",
    "triangle_area", "volume_calc",
    "combinations_permutations", "quadratic_solver",
    "trig_calc", "log_calc",
    "sequence_calc", "fibonacci",
    "variance_std", "led_resistor",
    "coordinate_distance", "weighted_average",
    "prime_list", "z_score",
    "percent_error", "scientific_notation",
    "fraction_convert", "fraction_math",
    "proportion_solve", "rounding_sigfig",
    "mixed_number", "beaufort_scale",
    "aqi_category", "modulo_calc",
    "decibel_scale", "richter_scale",
    "heart_rate_zones", "uv_index",
    "one_rep_max", "calorie_deficit",
    "base_arithmetic", "protein_needs",
    "average_speed", "work_rate",
    "activate_mode", "deactivate_mode", "list_modes", "reload_modes",
    "force_calc", "energy_calc",
    "density_calc", "pressure_calc",
    "momentum_calc", "work_power",
]


@pytest.fixture(scope="module")
def classifier():
    from core.intent_classifier import IntentClassifier
    clf = IntentClassifier(
        intents_path=os.path.join(_ROOT, "data", "intents.json"),
        models_dir=os.path.join(_ROOT, "data", "models"),
        lazy=True,
    )
    clf._build_exact_lookup()
    return clf


@pytest.fixture(scope="module")
def merged():
    from core.intent_loader import load_all_intents
    return load_all_intents()


def test_all_new_intents_present(merged):
    missing = [i for i in _NEW_INTENTS if i not in merged]
    assert not missing, f"intents missing from merged corpus: {missing}"


def test_every_new_intent_has_patterns(merged):
    empty = [i for i in _NEW_INTENTS if not merged.get(i, {}).get("patterns")]
    assert not empty, f"intents with no patterns: {empty}"


def test_first_pattern_exact_matches_its_own_intent(classifier, merged):
    """Each new intent's first pattern, spoken verbatim, must route back to
    that intent via exact match — the real end-to-end wiring."""
    mismatches = []
    for intent in _NEW_INTENTS:
        pats = merged.get(intent, {}).get("patterns") or []
        if not pats:
            continue
        phrase = pats[0]
        routed = classifier.exact_match(phrase)
        if routed != intent:
            mismatches.append((intent, phrase, routed))
    assert not mismatches, (
        "patterns that don't exact-match their own intent:\n"
        + "\n".join(f"  {i}: {p!r} -> {r}" for i, p, r in mismatches))


def test_no_new_pattern_collides_across_intents(merged):
    """No two of our new intents share a normalised pattern (would make the
    exact-match owner nondeterministic)."""
    from core.normalizer import HinglishNormalizer
    norm = HinglishNormalizer()
    owner = {}
    clashes = []
    for intent in _NEW_INTENTS:
        for p in merged.get(intent, {}).get("patterns", []):
            key = norm.clean(p)
            if key in owner and owner[key] != intent:
                clashes.append((key, owner[key], intent))
            else:
                owner[key] = intent
    assert not clashes, f"cross-intent pattern clashes: {clashes}"
