"""Date/time intelligence + random toolkit (fast lane, deterministic base)."""

from __future__ import annotations

import datetime as dt

import pytest

from core import datetime_tools as dtt

BASE = dt.date(2026, 7, 19)   # a Sunday


class TestWorldTime:
    def test_known_cities_resolve(self):
        for city in ("london", "new york", "tokyo", "dubai", "delhi"):
            out = dtt.world_time(city)
            assert out and city.split()[0].title() in out

    def test_offset_direction(self):
        assert "ahead of India" in dtt.world_time("tokyo")
        assert "behind India" in dtt.world_time("new york")
        assert "same as India" in dtt.world_time("kolkata")

    def test_unknown_place_none(self):
        assert dtt.world_time("narnia") is None
        assert dtt.world_time("") is None

    def test_fuzzy_iana_city(self):
        # a city not in the curated map but present in the IANA DB
        assert dtt.world_time("kolkata") is not None


class TestParseDate:
    @pytest.mark.parametrize("text,expect", [
        ("15 august", dt.date(2026, 8, 15)),
        ("august 15", dt.date(2026, 8, 15)),
        ("25/12", dt.date(2026, 12, 25)),
        ("1 jan 2027", dt.date(2027, 1, 1)),
        ("christmas", dt.date(2026, 12, 25)),
        ("republic day", dt.date(2027, 1, 26)),   # 26 Jan 2026 already passed
    ])
    def test_parses(self, text, expect):
        assert dtt.parse_date(text, BASE) == expect

    def test_past_date_rolls_to_next_year(self):
        # 1 January is before base → next year
        assert dtt.parse_date("1 january", BASE) == dt.date(2027, 1, 1)

    def test_invalid_returns_none(self):
        assert dtt.parse_date("31/02", BASE) is None
        assert dtt.parse_date("gibberish", BASE) is None


class TestDateMath:
    def test_days_forward(self):
        assert "02 September 2026" in dtt.date_math("aaj se 45 din baad", BASE)

    def test_weeks(self):
        assert "09 August 2026" in dtt.date_math("3 hafte baad", BASE)

    def test_months_calendar_arithmetic(self):
        assert "19 September 2026" in dtt.date_math("2 mahine baad", BASE)

    def test_years(self):
        assert "19 July 2027" in dtt.date_math("1 saal baad", BASE)

    def test_backwards(self):
        out = dtt.date_math("10 din pehle", BASE)
        assert "09 July 2026" in out and "pehle" in out

    def test_month_end_clamp(self):
        # 31 Jan + 1 month must clamp to 28/29 Feb, not overflow
        out = dtt.date_math("1 mahine baad", dt.date(2026, 1, 31))
        assert "28 February 2026" in out

    def test_word_number(self):
        assert dtt.date_math("teen din baad", BASE) is not None

    def test_no_number_none(self):
        assert dtt.date_math("kuch din baad", BASE) is None


class TestDaysUntil:
    def test_future_countdown(self):
        out = dtt.days_until("15 august", BASE)
        assert "27 din" in out

    def test_today(self):
        assert "aaj hi" in dtt.days_until("19 july", BASE)

    def test_tomorrow(self):
        assert "kal" in dtt.days_until("20 july", BASE)

    def test_unparseable_none(self):
        assert dtt.days_until("kabhi bhi", BASE) is None


class TestRandom:
    def test_coin_toss(self):
        from skills.random_skill import coin_toss
        assert coin_toss({}).split()[0] in ("Heads", "Tails")

    def test_dice_default_and_dN(self):
        from skills.random_skill import dice_roll
        for _ in range(20):
            out = dice_roll({"raw_text": "dice roll karo"})
            n = int(out.split()[0])
            assert 1 <= n <= 6
        out = dice_roll({"raw_text": "d20 roll karo"})
        assert "d20" in out

    def test_multi_dice_sum(self):
        from skills.random_skill import dice_roll
        out = dice_roll({"raw_text": "2 dice feko"})
        assert "=" in out and "2×d6" in out

    def test_random_number_range(self):
        from skills.random_skill import random_number
        for _ in range(30):
            out = random_number({"raw_text": "1 se 6 ke beech number"})
            n = int(out.split()[0])
            assert 1 <= n <= 6

    def test_random_number_default(self):
        from skills.random_skill import random_number
        out = random_number({"raw_text": "koi number bolo"})
        assert "1-100" in out

    def test_pick_from_list(self):
        from skills.random_skill import random_pick
        for _ in range(20):
            out = random_pick({"raw_text": "in me se ek chuno chai ya coffee ya juice"})
            assert any(x in out for x in ("chai", "coffee", "juice"))

    def test_pick_needs_two_options(self):
        from skills.random_skill import random_pick
        assert "Options do" in random_pick({"raw_text": "ek chuno"})


class TestDayOfWeek:
    BASE = __import__("datetime").date(2026, 7, 21)   # Tuesday

    def test_future_date(self):
        from core.datetime_tools import day_of_week
        out = day_of_week("15 august 2027 kaunsa din", self.BASE)
        assert "Sunday" in out and "hoga" in out

    def test_past_date(self):
        from core.datetime_tools import day_of_week
        out = day_of_week("1 jan 2020 kaunsa din tha", self.BASE)
        assert "Wednesday" in out and "tha" in out

    def test_today(self):
        from core.datetime_tools import day_of_week
        assert "aaj hi" in day_of_week("21 july 2026 kaunsa din", self.BASE)

    def test_bare_year_none(self):
        from core.datetime_tools import day_of_week
        assert day_of_week("2027 kaunsa din", self.BASE) is None


class TestTimeUntil:
    import datetime as _d
    NOW = _d.datetime(2026, 7, 21, 14, 30)   # 2:30 pm

    def test_bare_hour_picks_soonest_future(self):
        from core.datetime_tools import time_until
        out = time_until("5 baje tak kitna time hai", self.NOW)
        assert "5:00 PM" in out and "2 ghante 30 minute" in out

    def test_explicit_pm(self):
        from core.datetime_tools import time_until
        assert "8:00 PM" in time_until("8 pm tak kitni der", self.NOW)

    def test_past_time_rolls_tomorrow(self):
        from core.datetime_tools import time_until
        out = time_until("2 pm tak kitna time", self.NOW)
        assert "kal" in out

    def test_no_time_none(self):
        from core.datetime_tools import time_until
        assert time_until("kuch bhi", self.NOW) is None


class TestTimezoneConvert:
    def test_two_cities_text_order(self):
        from core.datetime_tools import convert_time_zone
        out = convert_time_zone("3pm india london me kitne baje")
        assert "3:00 PM India" in out and "10:30 AM London" in out

    def test_default_source_india(self):
        from core.datetime_tools import convert_time_zone
        out = convert_time_zone("5pm ko tokyo me kitne baje")
        assert "India" in out and "Tokyo" in out

    def test_next_day_marked(self):
        from core.datetime_tools import convert_time_zone
        out = convert_time_zone("11pm india new york me kitne baje")
        assert out is not None

    def test_none_without_zone(self):
        from core.datetime_tools import convert_time_zone
        assert convert_time_zone("5pm tak kitna time") is None

    def test_none_without_time(self):
        from core.datetime_tools import convert_time_zone
        assert convert_time_zone("london ka time") is None
