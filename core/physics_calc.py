"""Physics — Newton's F=ma + kinetic/potential energy. Pure math, offline."""
from __future__ import annotations

import re
from typing import Optional

_G = 9.8   # m/s^2


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"


def _find(t: str, keyword: str, unit: str) -> Optional[float]:
    """Match 'keyword N' or 'N unit' (either word order)."""
    m = re.search(rf"(?:{keyword})\s*(?:=|is|of)?\s*(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))
    m = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{unit})", t)
    return float(m.group(1)) if m else None


def force_calc(text: str) -> Optional[str]:
    """Newton's second law F = m x a. Give any two, get the third."""
    t = (text or "").lower()
    F = _find(t, r"force", r"n\b|newton")
    m = _find(t, r"mass", r"kg|kilogram")
    a = _find(t, r"acceleration|accel", r"m ?/ ?s\s*\^?\s*2|m ?/ ?s2|ms-2")
    known = sum(x is not None for x in (F, m, a))
    if known < 2:
        return ("Do values do (force N / mass kg / acceleration m/s2) — jaise "
                "'mass 5 kg acceleration 10' — main teesra nikaal dunga.")
    if F is None:
        F = m * a
        return f"Force = mass x acceleration = {_fmt(m)} x {_fmt(a)} = {_fmt(F)} N."
    if m is None:
        if a == 0:
            return "Acceleration zero pe mass nikaalna possible nahi."
        m = F / a
        return f"Mass = force / acceleration = {_fmt(F)} / {_fmt(a)} = {_fmt(m)} kg."
    if m == 0:
        return "Mass zero nahi ho sakta."
    a2 = F / m
    return f"Acceleration = force / mass = {_fmt(F)} / {_fmt(m)} = {_fmt(a2)} m/s2."


def energy_calc(text: str) -> Optional[str]:
    """Kinetic energy (0.5 m v^2) or potential energy (m g h)."""
    t = (text or "").lower()
    mass = _find(t, r"mass", r"kg|kilogram")
    velocity = _find(t, r"velocity|speed", r"m ?/ ?s|mps")
    height = _find(t, r"height|unchai", r"metre|meter")
    want_pe = bool(re.search(r"\b(potential|pe|gravitational)\b", t)) or \
        (height is not None and velocity is None)
    if mass is None:
        return ("Mass do (+ velocity for KE, ya height for PE) — jaise "
                "'mass 5 kg velocity 10' — main energy bata dunga.")
    if want_pe:
        if height is None:
            return "Height do potential energy ke liye — jaise 'mass 5 height 10'."
        pe = mass * _G * height
        return (f"Potential energy = m g h = {_fmt(mass)} x {_G} x {_fmt(height)} "
                f"= {_fmt(pe)} J.")
    if velocity is None:
        return "Velocity do kinetic energy ke liye — jaise 'mass 5 velocity 10'."
    ke = 0.5 * mass * velocity * velocity
    return (f"Kinetic energy = 1/2 m v^2 = 0.5 x {_fmt(mass)} x {_fmt(velocity)}^2 "
            f"= {_fmt(ke)} J.")


def density_calc(text: str) -> Optional[str]:
    """Density = mass / volume. Give any two, get the third."""
    t = (text or "").lower()
    d = _find(t, r"density|ghanatv", r"kg ?/ ?m3|kg per m3|g ?/ ?cm3")
    m = _find(t, r"mass", r"kg|kilogram|grams?|\bg\b")
    v = _find(t, r"volume|aayatan", r"m3|cm3|litre|liter|\bl\b|ml|cubic")
    known = sum(x is not None for x in (d, m, v))
    if known < 2:
        return ("Do values do (mass / volume / density) — jaise 'mass 10 "
                "volume 2' — main teesra nikaal dunga.")
    if d is None:
        if v == 0:
            return "Volume zero nahi ho sakta."
        d = m / v
        return f"Density = mass / volume = {_fmt(m)} / {_fmt(v)} = {_fmt(d)} (units per volume)."
    if m is None:
        m = d * v
        return f"Mass = density x volume = {_fmt(d)} x {_fmt(v)} = {_fmt(m)}."
    if d == 0:
        return "Density zero pe volume nikaalna possible nahi."
    v2 = m / d
    return f"Volume = mass / density = {_fmt(m)} / {_fmt(d)} = {_fmt(v2)}."


def pressure_calc(text: str) -> Optional[str]:
    """Pressure = force / area. Give any two, get the third."""
    t = (text or "").lower()
    p = _find(t, r"pressure|dabav", r"pa\b|pascal|n ?/ ?m2")
    f = _find(t, r"force", r"n\b|newton")
    a = _find(t, r"area|kshetrafal", r"m2|m\^2|sq ?m|square met|cm2")
    known = sum(x is not None for x in (p, f, a))
    if known < 2:
        return ("Do values do (force N / area m2 / pressure Pa) — jaise "
                "'force 100 area 2' — main teesra nikaal dunga.")
    if p is None:
        if a == 0:
            return "Area zero nahi ho sakta."
        p = f / a
        return f"Pressure = force / area = {_fmt(f)} / {_fmt(a)} = {_fmt(p)} Pa."
    if f is None:
        f = p * a
        return f"Force = pressure x area = {_fmt(p)} x {_fmt(a)} = {_fmt(f)} N."
    if p == 0:
        return "Pressure zero pe area nikaalna possible nahi."
    a2 = f / p
    return f"Area = force / pressure = {_fmt(f)} / {_fmt(p)} = {_fmt(a2)} m2."


def momentum_calc(text: str) -> Optional[str]:
    """Momentum p = mass x velocity. Give any two, get the third."""
    t = (text or "").lower()
    p = _find(t, r"momentum|sanveg", r"kg ?m ?/ ?s|kgms")
    m = _find(t, r"mass", r"kg|kilogram")
    v = _find(t, r"velocity|speed", r"m ?/ ?s|mps")
    known = sum(x is not None for x in (p, m, v))
    if known < 2:
        return ("Do values do (mass kg / velocity m/s / momentum) — jaise "
                "'mass 5 velocity 10' — main teesra nikaal dunga.")
    if p is None:
        p = m * v
        return f"Momentum = mass x velocity = {_fmt(m)} x {_fmt(v)} = {_fmt(p)} kg.m/s."
    if m is None:
        if v == 0:
            return "Velocity zero pe mass nikaalna possible nahi."
        m = p / v
        return f"Mass = momentum / velocity = {_fmt(p)} / {_fmt(v)} = {_fmt(m)} kg."
    if m == 0:
        return "Mass zero nahi ho sakta."
    v2 = p / m
    return f"Velocity = momentum / mass = {_fmt(p)} / {_fmt(m)} = {_fmt(v2)} m/s."


def work_power(text: str) -> Optional[str]:
    """Work = force x distance; Power = work / time."""
    t = (text or "").lower()
    force = _find(t, r"force", r"n\b|newton")
    dist = _find(t, r"distance|displacement|doori", r"m\b|metre|meter")
    work = _find(t, r"work|kaam", r"j\b|joule")
    power = _find(t, r"power|shakti", r"w\b|watt")
    time = _find(t, r"time|samay", r"s\b|sec|second|minute|min")
    if work is None and force is not None and dist is not None:
        work = force * dist
        base = f"Work = force x distance = {_fmt(force)} x {_fmt(dist)} = {_fmt(work)} J."
        if time is not None and time > 0:
            return base + f" Power = work / time = {_fmt(work/time)} W."
        return base
    if power is None and work is not None and time is not None:
        if time == 0:
            return "Time zero nahi ho sakta."
        return f"Power = work / time = {_fmt(work)} / {_fmt(time)} = {_fmt(work/time)} W."
    if work is None and power is not None and time is not None:
        work = power * time
        return f"Work = power x time = {_fmt(power)} x {_fmt(time)} = {_fmt(work)} J."
    return ("Force + distance do (work ke liye), ya work + time do (power ke "
            "liye) — jaise 'force 10 distance 5' ya 'work 100 time 20'.")
