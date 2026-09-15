"""Team/group splitter + calories-burned estimate. Pure math, offline."""
from __future__ import annotations

import re
from typing import Optional


def _people_count(t: str, exclude: set) -> Optional[int]:
    m = re.search(r"(\d+)\s*(?:log|logo|people|persons?|players?|students?|"
                  r"bacche|members?|items?|cheez)", t)
    if m:
        return int(m.group(1))
    nums = [int(x) for x in re.findall(r"\d+", t) if int(x) not in exclude]
    return max(nums) if nums else None


def team_split(text: str) -> Optional[str]:
    t = (text or "").lower()
    # size-of-group mode: "groups of 4" / "4 ke groups" / "4-4 ke"
    size_m = re.search(r"(?:groups? of|team of|of)\s*(\d+)", t) or \
        re.search(r"(\d+)\s*(?:ke group|-\d+ ke|ke team|-\1)", t)
    # count-of-teams mode: "2 teams" / "3 groups"
    teams_m = re.search(r"(\d+)\s*(?:teams?|groups?|hisso?n?|parts?)", t)

    if size_m:
        size = int(size_m.group(1))
        total = _people_count(t, {size})
        if not total or size <= 0:
            return "Kitne log aur kitne ke group? Jaise '15 log 4 ke groups'."
        groups = total // size
        rem = total % size
        base = f"{total} ko {size}-{size} ke groups me: {groups} full group"
        if rem:
            return base + f" + 1 group of {rem} (total {groups + 1})."
        return base + f" (total {groups})."

    if teams_m:
        teams = int(teams_m.group(1))
        total = _people_count(t, {teams})
        if not total or teams <= 0:
            return "Kitne log aur kitni teams? Jaise '10 log 2 teams'."
        base = total // teams
        extra = total % teams
        if extra == 0:
            return f"{total} ko {teams} teams me: har team {base} log."
        return (f"{total} ko {teams} teams me: {extra} team{'s' if extra > 1 else ''} "
                f"of {base + 1}, baaki {teams - extra} of {base}.")
    return ("Batao kitne log aur kaise baatna hai — jaise '10 log 2 teams' "
            "ya '15 log 4 ke groups'.")


# rough kcal per step (level walking); scales a bit with body weight
def calories_burned(text: str) -> Optional[str]:
    t = (text or "").lower()
    wm = re.search(r"\b(?:weight|wt|vajan|wajan)\b\s*(\d+(?:\.\d+)?)", t)
    weight = float(wm.group(1)) if wm else 65.0
    used = set()
    if wm:
        used.add(wm.group(1))
    sm = re.search(r"(\d+(?:,\d{3})*)\s*(?:steps|kadam|kadmo|qadam)", t)
    if sm:
        steps = int(sm.group(1).replace(",", ""))
        # ~0.0005 kcal per step per kg (=0.033 kcal/step at 65kg)
        kcal = steps * 0.0005 * weight
        km = steps * 0.762 / 1000  # ~0.762 m stride
        return (f"~{steps:,} steps = {kcal:.0f} kcal burn (~{km:.1f} km). "
                "(Estimate — actual pe weight/pace ka farak padta hai.)")
    # distance walked/ran
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet)", t)
    if dm:
        km = float(dm.group(1))
        running = re.search(r"\b(run|running|jog|daud|bhaag)", t)
        # walking =0.5 kcal/kg/km, running =1.0 kcal/kg/km
        rate = 1.0 if running else 0.53
        kcal = rate * weight * km
        mode = "running" if running else "walking"
        return (f"~{_fmt(km)} km {mode} = {kcal:.0f} kcal burn "
                f"(weight {_fmt(weight)}kg). (Rough estimate.)")
    return ("Steps ya distance batao — jaise '8000 steps' ya '5 km walk' — "
            "main approx calorie burn bata dunga.")


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"
