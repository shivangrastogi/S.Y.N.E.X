"""BMI + bill-split by voice. Offline pure math."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="bmi_calc",
    description="Body Mass Index from height + weight (offline, cm/m/feet).",
    patterns=[
        "bmi calculate karo", "mera bmi kya hai", "bmi nikalo",
        "height 170 weight 70 bmi", "weight 70 height 170 bmi batao",
        "bmi check karo", "mera bmi batao height weight se",
    ],
    required_entities=[],
)
def bmi_calc(slots: dict) -> str:
    from core.health_calc import bmi
    out = bmi(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Height aur weight dono do, sir — jaise 'height 170 "
                   "weight 70 bmi' (cm/kg ya feet bhi chalega).")


@skill(
    name="bmr_calorie",
    description="Daily calorie need (BMR + maintenance) via Mifflin-St Jeor (offline).",
    patterns=[
        "meri daily calorie need kya hai", "bmr nikalo",
        "weight 70 height 175 age 28 male calories", "maintenance calories batao",
        "kitni calories chahiye din me", "bmr calculate karo",
        "roz kitni calorie chahiye",
    ],
    required_entities=[],
)
def bmr_calorie(slots: dict) -> str:
    from core.health_calc import bmr_calorie as _bc
    return _bc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="ideal_weight",
    description="Healthy weight range and ideal weight for a height (offline).",
    patterns=[
        "meri height ke hisaab se ideal weight", "ideal weight batao",
        "height 175 ideal weight", "healthy weight range kya hai",
        "mera sahi weight kitna hona chahiye", "5 foot 9 ideal weight",
    ],
    required_entities=[],
)
def ideal_weight(slots: dict) -> str:
    from core.health_calc import ideal_weight as _iw
    return _iw(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="body_fat",
    description="Estimate body-fat % (Deurenberg) from weight, height, age, sex (offline).",
    patterns=[
        "mera body fat percentage kya hai", "body fat estimate karo",
        "weight 70 height 175 age 28 male body fat", "kitna fat hai mera",
        "body fat nikaalo", "fat percentage batao",
    ],
    required_entities=[],
)
def body_fat(slots: dict) -> str:
    from core.health_calc import body_fat as _bf
    return _bf(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="heart_rate_zones",
    description="Max heart rate and training zones from age (220-age formula, offline).",
    patterns=[
        "age 30 heart rate zones", "max heart rate nikaalo",
        "training zones batao age se", "fat burn zone kya hai mera",
        "target heart rate kitna", "cardio zone heart rate",
    ],
    required_entities=[],
)
def heart_rate_zones(slots: dict) -> str:
    from core.health_calc import heart_rate_zones as _hz
    return _hz(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="one_rep_max",
    description="Estimate one-rep-max (1RM) from weight and reps (Epley, offline).",
    patterns=[
        "100 kg 5 reps ka 1rm", "one rep max nikaalo",
        "max lift kitna hoga", "1rm estimate karo weight reps se",
        "kitna utha sakta hoon max", "one rep max batao",
    ],
    required_entities=[],
)
def one_rep_max(slots: dict) -> str:
    from core.health_calc import one_rep_max as _orm
    return _orm(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="calorie_deficit",
    description="Weight-loss timeline from target kg and daily calorie deficit (offline).",
    patterns=[
        "5 kg lose karne me kitne din 500 deficit", "calorie deficit timeline",
        "weight loss me kitna time lagega", "kitne din me weight ghatega",
        "fat loss calculate karo deficit se", "calorie deficit nikaalo",
    ],
    required_entities=[],
)
def calorie_deficit(slots: dict) -> str:
    from core.health_calc import calorie_deficit as _cd
    return _cd(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="bill_split",
    description="Split a bill among people, with optional tip (offline).",
    patterns=[
        "bill split karo", "1200 ka bill 4 log me baato",
        "bill baato", "kitna per person", "bill divide karo 4 me",
        "1000 ka bill 5 logon me 10% tip ke sath", "per head kitna hoga",
    ],
    required_entities=[],
)
def bill_split(slots: dict) -> str:
    from core.finance_math import bill_split as _bs
    out = _bs(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Bill amount aur kitne log — jaise '1200 ka bill 4 log "
                   "me baato' (10% tip bhi bol sakte ho).")


@skill(
    name="protein_needs",
    description="Daily protein requirement from body weight and activity/goal (offline).",
    patterns=[
        "weight 70 protein kitna chahiye", "daily protein need batao",
        "muscle building ke liye protein", "kitna protein khana chahiye",
        "gym ke liye protein intake", "protein requirement nikaalo",
    ],
    required_entities=[],
)
def protein_needs(slots: dict) -> str:
    from core.health_calc import protein_needs as _pn
    return _pn(slots.get("raw_text") or slots.get("text") or "")
