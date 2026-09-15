"""Geometry — circle + Pythagoras. Pure math, offline."""
from __future__ import annotations

import math
import re
from typing import Optional


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"


def circle_calc(text: str) -> Optional[str]:
    """Area, circumference, diameter from a radius or diameter."""
    t = (text or "").lower()
    dm = re.search(r"(?:diameter|vyaas|\bd\b)\s*(\d+(?:\.\d+)?)", t)
    rm = re.search(r"(?:radius|trijya|\br\b)\s*(\d+(?:\.\d+)?)", t)
    if dm:
        r = float(dm.group(1)) / 2
    elif rm:
        r = float(rm.group(1))
    else:
        m = re.search(r"(\d+(?:\.\d+)?)", t)
        if not m:
            return ("Radius ya diameter do — jaise 'radius 5 circle' — main "
                    "area aur circumference bata dunga.")
        r = float(m.group(1))       # bare number treated as radius
    if r <= 0:
        return "Radius positive honi chahiye."
    if r > 1e9:
        return "Radius bahut badi hai — chhoti value do."
    area = math.pi * r * r
    circ = 2 * math.pi * r
    return (f"Circle r={_fmt(r)}: area {_fmt(area)}, circumference "
            f"{_fmt(circ)}, diameter {_fmt(2 * r)}.")


def pythagoras(text: str) -> Optional[str]:
    """Right triangle: two legs -> hypotenuse, or hyp + leg -> other leg."""
    t = (text or "").lower()
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if len(nums) < 2:
        return ("Do sides do — jaise '3 4 hypotenuse' ya '5 hypotenuse 3 leg' "
                "— main teesri side nikaal dunga.")
    if any(n > 1e9 for n in nums):
        return "Sides bahut badi hain — chhoti values do."
    # hypotenuse is GIVEN only in the explicit "hypotenuse <num>" form, and
    # only if that number isn't itself labelled a leg/side. Anything else
    # ("hypotenuse nikaalo", "legs 6 and 8 hypotenuse") means: find it.
    hg = re.search(r"(?:hypotenuse|hypo|karan)\s*(?:hai|is|=|:)?\s*"
                   r"(\d+(?:\.\d+)?)", t)
    if hg:
        hyp = float(hg.group(1))
        legs = [n for n in nums if abs(n - hyp) > 1e-9] or [n for n in nums if n != hyp]
        leg = legs[0] if legs else min(nums)
        if leg >= hyp:
            return "Hypotenuse sabse badi side honi chahiye."
        other = math.sqrt(hyp * hyp - leg * leg)
        return (f"Right triangle: hypotenuse {_fmt(hyp)}, ek leg {_fmt(leg)} "
                f"-> doosri leg {_fmt(other)}.")
    a, b = nums[0], nums[1]
    hyp = math.sqrt(a * a + b * b)
    return (f"Right triangle legs {_fmt(a)} & {_fmt(b)} -> hypotenuse "
            f"{_fmt(hyp)}.")


def triangle_area(text: str) -> Optional[str]:
    """Heron's formula from 3 sides, or 0.5*base*height."""
    t = (text or "").lower()
    bm = re.search(r"(?:base|aadhaar)\s*(\d+(?:\.\d+)?)", t)
    hm = re.search(r"(?:height|height|unchai| height)\s*(\d+(?:\.\d+)?)", t)
    if bm and hm:
        b, h = float(bm.group(1)), float(hm.group(1))
        if b <= 0 or h <= 0:
            return "Base aur height positive honi chahiye."
        return f"Triangle base {_fmt(b)} x height {_fmt(h)} / 2 = {_fmt(0.5*b*h)} area."
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if len(nums) < 3:
        return ("3 sides do (ya base+height) — jaise '3 4 5 triangle' — "
                "main area nikaal dunga.")
    if any(n > 1e9 for n in nums):
        return "Sides bahut badi hain — chhoti values do."
    a, b, c = nums[0], nums[1], nums[2]
    if a + b <= c or b + c <= a or a + c <= b:
        return f"{_fmt(a)}, {_fmt(b)}, {_fmt(c)} se triangle ban hi nahi sakta."
    s = (a + b + c) / 2
    area = math.sqrt(s * (s - a) * (s - b) * (s - c))
    return (f"Triangle sides {_fmt(a)},{_fmt(b)},{_fmt(c)}: area {_fmt(area)} "
            f"(Heron), perimeter {_fmt(a+b+c)}.")


def volume_calc(text: str) -> Optional[str]:
    """Volume of sphere / cube / cylinder / cone from dimensions."""
    t = (text or "").lower()
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if any(n > 1e6 for n in nums):
        return "Dimensions bahut badi hain — chhoti values do."

    def _get(pat, default=None):
        m = re.search(pat, t)
        return float(m.group(1)) if m else default

    r = _get(r"(?:radius|trijya|\br\b)\s*(\d+(?:\.\d+)?)")
    h = _get(r"(?:height|unchai|\bh\b)\s*(\d+(?:\.\d+)?)")
    side = _get(r"(?:side|edge|bhuja|\ba\b)\s*(\d+(?:\.\d+)?)")

    if re.search(r"\b(sphere|gola|ball)\b", t):
        r = r or (nums[0] if nums else None)
        if not r:
            return "Sphere ka radius do — jaise 'sphere radius 5'."
        return f"Sphere r={_fmt(r)}: volume {_fmt(4/3*math.pi*r**3)}."
    if re.search(r"\b(cube|ghan)\b", t):
        a = side or (nums[0] if nums else None)
        if not a:
            return "Cube ka side do — jaise 'cube side 4'."
        return f"Cube side={_fmt(a)}: volume {_fmt(a**3)}."
    if re.search(r"\b(cylinder|belan)\b", t):
        if r is None or h is None:
            vals = [n for n in nums]
            if len(vals) >= 2:
                r, h = vals[0], vals[1]
        if not r or not h:
            return "Cylinder ka radius aur height do — jaise 'cylinder radius 3 height 10'."
        return f"Cylinder r={_fmt(r)}, h={_fmt(h)}: volume {_fmt(math.pi*r*r*h)}."
    if re.search(r"\b(cone|shanku)\b", t):
        if r is None or h is None:
            vals = [n for n in nums]
            if len(vals) >= 2:
                r, h = vals[0], vals[1]
        if not r or not h:
            return "Cone ka radius aur height do — jaise 'cone radius 3 height 9'."
        return f"Cone r={_fmt(r)}, h={_fmt(h)}: volume {_fmt(1/3*math.pi*r*r*h)}."
    return ("Kaunsa shape? sphere / cube / cylinder / cone — jaise "
            "'sphere radius 5 volume'.")


def coordinate_distance(text: str) -> Optional[str]:
    """Distance, midpoint and slope between two points. '(0,0) to (3,4)'."""
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text or "")]
    if len(nums) < 4:
        return ("Do points do (4 numbers) — jaise '0 0 se 3 4' — main "
                "distance, midpoint aur slope nikaal dunga.")
    if any(abs(n) > 1e9 for n in nums[:4]):
        return "Coordinates bahut bade hain — chhoti values do."
    x1, y1, x2, y2 = nums[0], nums[1], nums[2], nums[3]
    dist = math.hypot(x2 - x1, y2 - y1)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if x2 == x1:
        slope = "undefined (vertical line)"
    else:
        slope = _fmt((y2 - y1) / (x2 - x1))
    return (f"({_fmt(x1)},{_fmt(y1)}) se ({_fmt(x2)},{_fmt(y2)}): distance "
            f"{_fmt(dist)}, midpoint ({_fmt(mx)},{_fmt(my)}), slope {slope}.")
