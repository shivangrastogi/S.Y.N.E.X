"""Health math — BMI. Pure arithmetic, offline (not medical advice)."""
from __future__ import annotations

import re
from typing import Optional


def _height_m_keyword(text: str) -> Optional[float]:
    """Height from an EXPLICIT keyword or feet notation (word-boundaried so
    the 'ht' in 'weight' can't masquerade as height)."""
    t = text.lower()
    fm = re.search(r"(\d)\s*(?:'|feet|foot|ft)\s*(\d{1,2})?", t)
    if fm:
        ft = int(fm.group(1))
        inch = int(fm.group(2)) if fm.group(2) else 0
        return (ft * 12 + inch) * 0.0254
    hm = re.search(r"\b(?:height|ht|lambai|lambaai)\b\s*(\d+(?:\.\d+)?)", t)
    if hm:
        v = float(hm.group(1))
        return v / 100 if v > 3 else v
    return None


def _weight_kg_keyword(text: str) -> Optional[float]:
    wm = re.search(r"\b(?:weight|wt|vajan|wajan|vazan)\b\s*(\d+(?:\.\d+)?)",
                   text.lower())
    return float(wm.group(1)) if wm else None


def bmi(text: str) -> Optional[str]:
    t = (text or "").lower()
    h = _height_m_keyword(t)
    w = _weight_kg_keyword(t)
    # Fill gaps from range heuristics, but height and weight must be DISTINCT
    # numbers — one lone number can't be both.
    used = set()
    if h is not None:
        used.add(round(h * 100) if h < 3 else round(h))
    if w is not None:
        used.add(round(w))
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if h is None:
        for f in nums:
            if round(f) in used:
                continue
            if 100 <= f <= 250:
                h = f / 100
                used.add(round(f))
                break
            if 1.2 <= f <= 2.5:
                h = f
                used.add(round(f * 100))
                break
    if w is None:
        for f in nums:
            if round(f) in used:
                continue
            if 25 <= f <= 350:
                w = f
                used.add(round(f))
                break
    if not h or not w or h <= 0:
        return None
    val = w / (h * h)
    if val < 18.5:
        cat = "underweight"
    elif val < 25:
        cat = "normal (healthy)"
    elif val < 30:
        cat = "overweight"
    else:
        cat = "obese"
    return (f"BMI = {val:.1f} ({cat}). Height {h*100:.0f}cm, weight {w:.0f}kg. "
            "(Sirf ek indicator hai, medical advice nahi.)")


_ACT = {  # activity level -> TDEE multiplier
    "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
    "active": 1.725, "very active": 1.9,
}


def _age(text: str, used: set) -> Optional[int]:
    m = re.search(r"\b(?:age|umar|umra|saal|years?|yr)\b[^\d]{0,6}(\d{1,3})", text)
    if not m:
        m = re.search(r"(\d{1,3})\s*(?:saal|years?\s*old|yr)", text)
    if m:
        a = int(m.group(1))
        if 1 <= a <= 120:
            return a
    for f in re.findall(r"\d+(?:\.\d+)?", text):
        v = float(f)
        if round(v) in used:
            continue
        if 5 <= v <= 100 and v == int(v):
            return int(v)
    return None


def bmr_calorie(text: str) -> Optional[str]:
    t = (text or "").lower()
    h = _height_m_keyword(t)
    w = _weight_kg_keyword(t)
    used = set()
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if h is not None:
        used.add(round(h * 100) if h < 3 else round(h))
    if w is not None:
        used.add(round(w))
    if h is None:
        for f in nums:
            if round(f) in used:
                continue
            if 100 <= f <= 250:
                h = f / 100; used.add(round(f)); break
            if 1.2 <= f <= 2.5:
                h = f; used.add(round(f * 100)); break
    if w is None:
        for f in nums:
            if round(f) in used:
                continue
            if 25 <= f <= 350:
                w = f; used.add(round(f)); break
    age = _age(t, used)
    if not h or not w or not age:
        return ("BMR ke liye weight, height aur age teeno chahiye — jaise "
                "'weight 70 height 175 age 28 male'.")
    female = bool(re.search(r"\b(female|woman|aurat|mahila|ladki|girl)\b", t))
    male = bool(re.search(r"\b(male|man|aadmi|purush|ladka|boy)\b", t))
    sex = "female" if (female and not male) else "male"
    hc = h * 100
    bmr = 10 * w + 6.25 * hc - 5 * age + (-161 if sex == "female" else 5)
    lvl = next((k for k in _ACT if k in t), "moderate")
    tdee = bmr * _ACT[lvl]
    table = " | ".join(f"{k}: {bmr*v:.0f}" for k, v in _ACT.items())
    return (f"BMR ({sex}, {age}y, {w:.0f}kg, {hc:.0f}cm): {bmr:.0f} kcal/day. "
            f"Maintenance ({lvl}): {tdee:.0f} kcal/day.\nActivity-wise: {table}.")


def ideal_weight(text: str) -> Optional[str]:
    """Healthy weight range (BMI 18.5-24.9) + Devine ideal, from height."""
    t = (text or "").lower()
    h = _height_m_keyword(t)
    if h is None:
        for f in re.findall(r"\d+(?:\.\d+)?", t):
            v = float(f)
            if 100 <= v <= 250:
                h = v / 100; break
            if 1.2 <= v <= 2.5:
                h = v; break
    if not h or h <= 0:
        return ("Apni height batao — jaise 'height 175 ideal weight' ya "
                "'5 foot 9 ideal weight'.")
    lo = 18.5 * h * h
    hi = 24.9 * h * h
    # Devine (male baseline): 50 + 2.3 kg per inch over 5 ft
    inches = h / 0.0254
    devine = 50 + 2.3 * max(0.0, inches - 60)
    return (f"Height {h*100:.0f}cm: healthy weight {lo:.0f}-{hi:.0f} kg "
            f"(BMI 18.5-24.9). Ideal ~{devine:.0f} kg (Devine). "
            "(Guide hai, medical advice nahi.)")


def _hw_age(t: str):
    """Shared height(m)/weight(kg)/age extraction with distinct-number guard."""
    h = _height_m_keyword(t)
    w = _weight_kg_keyword(t)
    used = set()
    if h is not None:
        used.add(round(h * 100) if h < 3 else round(h))
    if w is not None:
        used.add(round(w))
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if h is None:
        for f in nums:
            if round(f) in used:
                continue
            if 100 <= f <= 250:
                h = f / 100; used.add(round(f)); break
            if 1.2 <= f <= 2.5:
                h = f; used.add(round(f * 100)); break
    if w is None:
        for f in nums:
            if round(f) in used:
                continue
            if 25 <= f <= 350:
                w = f; used.add(round(f)); break
    return h, w, _age(t, used)


def body_fat(text: str) -> Optional[str]:
    """Body-fat % via Deurenberg (needs weight, height, age, sex)."""
    t = (text or "").lower()
    h, w, age = _hw_age(t)
    if not h or not w or not age:
        return ("Body-fat ke liye weight, height aur age chahiye — jaise "
                "'weight 70 height 175 age 28 male'.")
    female = bool(re.search(r"\b(female|woman|aurat|mahila|ladki|girl)\b", t))
    male = bool(re.search(r"\b(male|man|aadmi|purush|ladka|boy)\b", t))
    sex_val = 0 if (female and not male) else 1   # male=1, female=0
    sex = "female" if sex_val == 0 else "male"
    bmi_v = w / (h * h)
    bf = 1.20 * bmi_v + 0.23 * age - 10.8 * sex_val - 5.4
    bf = max(2.0, bf)
    if sex == "male":
        cat = ("essential" if bf < 6 else "athletic" if bf < 14 else
               "fitness" if bf < 18 else "average" if bf < 25 else "high")
    else:
        cat = ("essential" if bf < 14 else "athletic" if bf < 21 else
               "fitness" if bf < 25 else "average" if bf < 32 else "high")
    return (f"Body fat ~{bf:.1f}% ({cat}) — {sex}, BMI {bmi_v:.1f}. "
            "(Deurenberg estimate, medical advice nahi.)")


def heart_rate_zones(text: str) -> Optional[str]:
    """Max HR (220 - age) + training zones."""
    t = (text or "").lower()
    m = re.search(r"(?:age|umar|umra)\s*(\d{1,3})", t) or \
        re.search(r"(\d{1,3})\s*(?:saal|years?\s*old|yr)", t)
    age = None
    if m:
        age = int(m.group(1))
    else:
        for f in re.findall(r"\d+", t):
            v = int(f)
            if 5 <= v <= 100:
                age = v
                break
    if not age or not (5 <= age <= 100):
        return ("Apni age batao — jaise 'age 30 heart rate zones' — main "
                "max HR aur training zones bata dunga.")
    mhr = 220 - age

    def _z(lo, hi):
        return f"{round(mhr*lo)}-{round(mhr*hi)}"
    return (f"Age {age}: max heart rate ~{mhr} bpm. Zones (bpm): "
            f"warm-up {_z(0.5,0.6)}, fat-burn {_z(0.6,0.7)}, "
            f"aerobic {_z(0.7,0.8)}, anaerobic {_z(0.8,0.9)}, "
            f"max {_z(0.9,1.0)}. (Guide hai, medical advice nahi.)")


def one_rep_max(text: str) -> Optional[str]:
    """1RM via Epley: weight * (1 + reps/30). '100 kg 5 reps'."""
    t = (text or "").lower()
    wm = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram|pounds?|lbs?)", t)
    rm = re.search(r"(\d+)\s*(?:reps?|repetitions?|baar)", t)
    weight = float(wm.group(1)) if wm else None
    reps = int(rm.group(1)) if rm else None
    if weight is None or reps is None:
        nums = sorted((float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)), reverse=True)
        if len(nums) >= 2:
            weight = weight or nums[0]
            reps = reps or int(min(nums))
    if not weight or not reps or reps < 1:
        return ("Weight aur reps do — jaise '100 kg 5 reps' — main 1RM "
                "(max lift) estimate bata dunga.")
    if reps > 30:
        return "Reps 1-30 ke beech do (formula wahi tak accurate hai)."
    orm = weight * (1 + reps / 30)
    p90 = orm * 0.9
    p80 = orm * 0.8
    return (f"1RM (Epley) ~{_fmt2(orm)} (from {_fmt2(weight)} x {reps} reps). "
            f"90% = {_fmt2(p90)}, 80% = {_fmt2(p80)}. (Estimate hai.)")


def calorie_deficit(text: str) -> Optional[str]:
    """Weight-loss timeline: ~7700 kcal per kg fat. 'lose 5 kg 500 cal deficit'."""
    t = (text or "").lower()
    kgm = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)", t)
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:cal|calorie|kcal|calories)", t)
    kg = float(kgm.group(1)) if kgm else None
    deficit = float(dm.group(1)) if dm else None
    if kg is None or deficit is None:
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
        if len(nums) >= 2:
            kg = kg or min(nums)
            deficit = deficit or max(nums)
    if not kg or not deficit or deficit <= 0 or kg <= 0:
        return ("Kitna weight ghatana hai aur daily calorie deficit batao — "
                "jaise 'lose 5 kg 500 cal deficit'.")
    total = kg * 7700
    days = total / deficit
    weeks = days / 7
    return (f"{_fmt2(kg)} kg ghataane ke liye ~{_fmt2(total)} kcal deficit "
            f"chahiye. {_fmt2(deficit)} kcal/day pe ~{days:.0f} din "
            f"(~{weeks:.1f} hafte). Healthy pace ~0.5 kg/week. "
            "(Guide hai, medical advice nahi.)")


def _fmt2(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.1f}"


def protein_needs(text: str) -> Optional[str]:
    """Daily protein from body weight + activity/goal (g/kg)."""
    t = (text or "").lower()
    wm = re.search(r"\b(?:weight|wt|vajan|wajan)\b\s*(\d+(?:\.\d+)?)", t)
    weight = float(wm.group(1)) if wm else None
    if weight is None:
        for f in re.findall(r"\d+(?:\.\d+)?", t):
            v = float(f)
            if 25 <= v <= 250:
                weight = v
                break
    if not weight:
        return ("Apna weight batao — jaise 'weight 70 protein' — main daily "
                "protein need bata dunga.")
    if re.search(r"\b(muscle|build|gym|bodybuild|bulk|strength)\b", t):
        lo, hi, goal = 1.6, 2.2, "muscle building"
    elif re.search(r"\b(active|exercise|athlete|sports?|workout)\b", t):
        lo, hi, goal = 1.2, 1.6, "active"
    else:
        lo, hi, goal = 0.8, 1.0, "general"
    return (f"Weight {_fmt2(weight)}kg ({goal}): ~{_fmt2(weight*lo)}-"
            f"{_fmt2(weight*hi)} g protein/day. (Guide hai, medical advice nahi.)")
