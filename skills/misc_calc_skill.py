"""Zodiac sign + running pace. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="zodiac_sign",
    description="Western zodiac sign from a birth date (offline).",
    patterns=[
        "mera zodiac sign kya hai", "15 august ka zodiac", "rashi batao",
        "star sign kya hai", "mera sun sign batao", "zodiac sign nikaalo",
        "kaunsi rashi hai meri",
    ],
    required_entities=[],
)
def zodiac_sign(slots: dict) -> str:
    from core.misc_calc import zodiac_sign as _zs
    return _zs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="running_pace",
    description="Running pace (min/km) and speed from distance + time (offline).",
    patterns=[
        "5 km 25 min pace", "running pace nikaalo", "mera pace kya tha",
        "10 km 55 minute pace batao", "pace calculate karo",
        "kitni speed thi run me", "per km pace nikaalo",
    ],
    required_entities=[],
)
def running_pace(slots: dict) -> str:
    from core.misc_calc import running_pace as _rp
    return _rp(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="numerology",
    description="Life-path number from a birth date (numerology, for fun, offline).",
    patterns=[
        "mera life path number kya hai", "numerology nikaalo",
        "15/08/1998 ka numerology", "meri janam tareekh se number batao",
        "life path number calculate karo", "numerology number kya hai mera",
    ],
    required_entities=[],
)
def numerology(slots: dict) -> str:
    from core.misc_calc import numerology as _nm
    return _nm(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="heat_index",
    description="'Feels-like' temperature from air temp + humidity (offline).",
    patterns=[
        "35 degree 60% humidity feels like", "feels like temperature batao",
        "heat index nikaalo", "kitna garm feel hoga humidity ke saath",
        "real feel temperature kya hai", "temp 38 humidity 65 feels like",
    ],
    required_entities=[],
)
def heat_index(slots: dict) -> str:
    from core.misc_calc import heat_index as _hi
    return _hi(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="travel_time",
    description="Solve distance/speed/time when any two are given (offline).",
    patterns=[
        "120 km 60 kmph kitni der lagegi", "travel time nikaalo",
        "300 km 5 ghante me speed", "kitni der lagegi pahunchne me",
        "80 kmph se 2 ghante me kitna door", "distance speed time nikaalo",
    ],
    required_entities=[],
)
def travel_time(slots: dict) -> str:
    from core.misc_calc import travel_time as _tt
    return _tt(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="area_calc",
    description="Room/plot area and perimeter from length x width (offline).",
    patterns=[
        "10 by 12 feet room ka area", "area nikaalo dimensions se",
        "12x15 room area kitna", "kamre ka area batao",
        "square feet nikaalo", "plot ka area aur perimeter",
    ],
    required_entities=[],
)
def area_calc(slots: dict) -> str:
    from core.misc_calc import area_calc as _ac
    return _ac(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="wind_chill",
    description="'Feels-like cold' from temperature + wind speed (offline).",
    patterns=[
        "5 degree 30 kmph wind feels like", "wind chill nikaalo",
        "kitni thand feel hogi hawa ke saath", "wind chill temperature batao",
        "feels like cold kya hai", "0 degree 40 kmph wind chill",
    ],
    required_entities=[],
)
def wind_chill(slots: dict) -> str:
    from core.misc_calc import wind_chill as _wc
    return _wc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="dew_point",
    description="Dew point from temperature + humidity (Magnus formula, offline).",
    patterns=[
        "30 degree 70% humidity dew point", "dew point nikaalo",
        "kitna chipchipa lagega humidity se", "dew point temperature batao",
        "os bindu kya hai", "25 degree 50 percent dew point",
    ],
    required_entities=[],
)
def dew_point(slots: dict) -> str:
    from core.misc_calc import dew_point as _dp
    return _dp(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="download_time",
    description="Estimate download time from file size and internet speed (offline).",
    patterns=[
        "2 gb file 20 mbps me kitni der", "download time nikaalo",
        "700 mb download hone me kitna time", "kitni der me download hoga",
        "100 mbps pe 1 gb kitna time", "file download time batao",
    ],
    required_entities=[],
)
def download_time(slots: dict) -> str:
    from core.misc_calc import download_time as _dt
    return _dt(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="paint_quantity",
    description="Litres of paint needed for a wall area (offline).",
    patterns=[
        "500 sqft wall ke liye kitna paint", "paint quantity nikaalo",
        "kitne litre paint chahiye", "10 by 12 wall paint kitna",
        "wall paint calculate karo", "kitna rang lagega deewar pe",
    ],
    required_entities=[],
)
def paint_quantity(slots: dict) -> str:
    from core.misc_calc import paint_quantity as _pq
    return _pq(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="tile_count",
    description="How many floor tiles are needed (with wastage) for an area (offline).",
    patterns=[
        "200 sqft floor 2x2 feet tiles kitne", "tile count nikaalo",
        "kitni tiles lagengi floor pe", "300 sqft ke liye 12x12 tiles",
        "floor tiling ke liye kitni tiles", "tiles calculate karo",
    ],
    required_entities=[],
)
def tile_count(slots: dict) -> str:
    from core.misc_calc import tile_count as _tc
    return _tc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="recipe_scale",
    description="Scale a recipe by serving ratio (offline).",
    patterns=[
        "4 log ki recipe 6 ke liye scale karo", "recipe scale karo",
        "recipe double karni hai", "servings badhani hai recipe ki",
        "kitna ingredient lagega zyada logon ke liye", "recipe adjust karo",
    ],
    required_entities=[],
)
def recipe_scale(slots: dict) -> str:
    from core.misc_calc import recipe_scale as _rs
    return _rs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="ppi_calculator",
    description="Screen pixel density (PPI) from resolution and diagonal size (offline).",
    patterns=[
        "1920x1080 15.6 inch ppi", "pixel density nikaalo",
        "screen ka ppi kitna hai", "ppi calculate karo resolution se",
        "kitni sharp hai screen", "pixels per inch batao",
    ],
    required_entities=[],
)
def ppi_calculator(slots: dict) -> str:
    from core.misc_calc import ppi_calculator as _pc
    return _pc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="thunder_distance",
    description="How far lightning was from the flash-to-thunder gap (offline).",
    patterns=[
        "bijli ke 5 second baad thunder kitni door", "thunder distance nikaalo",
        "lightning kitni door thi", "gadgadahat se distance batao",
        "kitni door girli bijli", "flash to thunder distance",
    ],
    required_entities=[],
)
def thunder_distance(slots: dict) -> str:
    from core.misc_calc import thunder_distance as _td
    return _td(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="ohms_law",
    description="Ohm's law: find voltage, current or resistance from the other two (offline).",
    patterns=[
        "5 volt 2 amp resistance kitni", "ohms law calculate karo",
        "12 volt 4 ohm current", "voltage current resistance nikaalo",
        "2 amp 10 ohm pe voltage", "ohm law se power batao",
    ],
    required_entities=[],
)
def ohms_law(slots: dict) -> str:
    from core.misc_calc import ohms_law as _ol
    return _ol(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="battery_life",
    description="Estimate battery runtime from capacity (mAh) and draw (mA) (offline).",
    patterns=[
        "3000 mah battery 500 ma draw kitne ghante", "battery life nikaalo",
        "kitni der chalegi battery", "mah se runtime batao",
        "battery kitne ghante chalegi", "power bank kitna chalega",
    ],
    required_entities=[],
)
def battery_life(slots: dict) -> str:
    from core.misc_calc import battery_life as _bl
    return _bl(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="frequency_wavelength",
    description="Convert EM frequency to wavelength or back (c = f x lambda) (offline).",
    patterns=[
        "100 MHz ka wavelength kitna", "frequency wavelength convert karo",
        "2.4 ghz wifi wavelength", "wavelength se frequency nikaalo",
        "500 nm light ki frequency", "radio wave wavelength batao",
    ],
    required_entities=[],
)
def frequency_wavelength(slots: dict) -> str:
    from core.misc_calc import frequency_wavelength as _fw
    return _fw(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="led_resistor",
    description="Series resistor for an LED from supply, LED voltage and current (offline).",
    patterns=[
        "5V supply 2V LED 20mA resistor", "led resistor nikaalo",
        "led ke liye kaunsa resistor", "series resistor calculate karo",
        "led current limiting resistor", "resistor value for led",
    ],
    required_entities=[],
)
def led_resistor(slots: dict) -> str:
    from core.misc_calc import led_resistor as _lr
    return _lr(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="beaufort_scale",
    description="Beaufort wind-force number and description from wind speed (offline).",
    patterns=[
        "45 kmph wind kaunsa beaufort", "beaufort scale batao",
        "20 knots wind force", "hawa kitni tez hai beaufort me",
        "wind speed ko beaufort me", "beaufort number nikaalo",
    ],
    required_entities=[],
)
def beaufort_scale(slots: dict) -> str:
    from core.misc_calc import beaufort_scale as _bs
    return _bs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="aqi_category",
    description="Air Quality Index category and health advice (CPCB scale, offline).",
    patterns=[
        "aqi 180 kaunsi category", "air quality index category batao",
        "aqi 350 matlab kya", "hawa ki quality kaisi hai aqi se",
        "aqi number ka matlab", "pollution level batao aqi se",
    ],
    required_entities=[],
)
def aqi_category(slots: dict) -> str:
    from core.misc_calc import aqi_category as _aq
    return _aq(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="decibel_scale",
    description="Loudness category and safe hearing-exposure time for a dB level (offline).",
    patterns=[
        "85 db kitna loud hota hai", "decibel level ka matlab",
        "100 db safe hai kya", "sound kitna khatarnak hai db se",
        "hearing damage kitne db pe", "decibel scale batao",
    ],
    required_entities=[],
)
def decibel_scale(slots: dict) -> str:
    from core.misc_calc import decibel_scale as _ds
    return _ds(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="richter_scale",
    description="Earthquake severity from a Richter magnitude (offline).",
    patterns=[
        "richter 6.5 kitna khatarnak", "earthquake magnitude ka matlab",
        "magnitude 7 se kitna nuksaan", "richter scale batao",
        "bhukamp kitna tez tha magnitude se", "earthquake severity nikaalo",
    ],
    required_entities=[],
)
def richter_scale(slots: dict) -> str:
    from core.misc_calc import richter_scale as _rs
    return _rs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="uv_index",
    description="UV index category and sun-protection advice from a UV number (offline).",
    patterns=[
        "uv index 8 kitna khatarnak", "uv index category batao",
        "sunscreen chahiye kya uv se", "uv 11 matlab kya",
        "sun protection kitni zaroori", "uv index ka matlab",
    ],
    required_entities=[],
)
def uv_index(slots: dict) -> str:
    from core.misc_calc import uv_index as _uv
    return _uv(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="average_speed",
    description="Average speed over equal distance at two speeds (harmonic mean, offline).",
    patterns=[
        "60 kmph gaye 40 kmph aaye average speed", "average speed nikaalo",
        "jaate 80 aate 120 average", "round trip average speed",
        "do speed ka average kya hoga", "average velocity batao",
    ],
    required_entities=[],
)
def average_speed(slots: dict) -> str:
    from core.misc_calc import average_speed as _as
    return _as(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="work_rate",
    description="Time to finish a job when people work together (time-and-work, offline).",
    patterns=[
        "A 6 ghante B 4 ghante saath me kitna", "time and work solve karo",
        "do log saath kaam karein to kitna time", "work rate nikaalo",
        "12 din aur 6 din wale saath", "kitne time me kaam hoga together",
    ],
    required_entities=[],
)
def work_rate(slots: dict) -> str:
    from core.misc_calc import work_rate as _wr
    return _wr(slots.get("raw_text") or slots.get("text") or "")
