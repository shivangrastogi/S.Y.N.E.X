"""Offline unit conversion by voice — length, weight, temp, volume, speed, data.

100% local arithmetic (core/unit_convert). Separate from currency_convert
(which needs live rates) — physical units never change, so no network.
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="unit_convert",
    description="Convert between physical units offline (km↔mile, kg↔lb, °C↔°F, litre↔gallon, GB↔MB…).",
    patterns=[
        "10 km me kitne mile", "5 kg me kitne pound",
        "100 fahrenheit me kitne celsius", "2 mile kitne km hote hain",
        "50 celsius kitne fahrenheit", "1 gallon me kitne litre",
        "unit convert karo", "ye convert kar do",
        "miles to km convert karo", "kg ko pound me badlo",
        "10 gb me kitne mb", "60 kmph me kitne mph",
    ],
    required_entities=[],
)
def unit_convert(slots: dict) -> str:
    from core.unit_convert import parse_and_convert
    text = slots.get("raw_text") or slots.get("text") or ""
    out = parse_and_convert(text)
    if out:
        return out
    return ("Kya se kya convert karun, sir? Jaise: '10 km me kitne mile' "
            "ya '5 kg to pound' ya '100 f in c'. (Length, weight, temp, "
            "volume, speed, data — sab offline.)")
