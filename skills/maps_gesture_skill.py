"""Voice surface for the Maps + Mouse gesture modes.

  - search_maps_for          — voice "open <place> in maps" → default browser
  - maps_gestures_on/off     — start/stop the maps gesture engine
  - mouse_gestures_on/off    — start/stop the mouse-cursor gesture engine
  - gesture_arm / disarm     — same toggle that peace-sign triggers
  - gesture_arm_status       — report armed flag + per-engine counters
"""
from __future__ import annotations

import re
import urllib.parse
import webbrowser

from core.skill_registry import skill


# ── Maps search ─────────────────────────────────────────────


_MAPS_VERBS = re.compile(
    r"^\s*(?:open|search|find|show|navigate to|directions to|"
    r"maps mein|maps me|google maps mein|location of)\s+",
    re.IGNORECASE,
)
# Strip a trailing "… ko/in/on maps [mein] [dikhao|dhundo|kholo|find|search]".
_MAPS_TAIL = re.compile(
    r"\s+(?:ko|ka|in|on)?\s*(?:google\s+)?maps?\s*"
    r"(?:mein|me|on|in)?\s*(?:dikhao|dhundo|kholo|search|find|show|"
    r"khol\s+do|dikha\s+do)?\s*$",
    re.IGNORECASE,
)
_FALLBACK_HEAD = re.compile(
    r"^\s*(?:open\s+)?(?:google\s+)?maps?\s+(?:for|of|to|mein|me)?\s*",
    re.IGNORECASE,
)


def _extract_place(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    # Strip a leading "open/search/find/maps mein …"
    t = _MAPS_VERBS.sub("", t)
    # Strip a trailing "… ko maps mein dikhao" or "… in maps"
    t = _MAPS_TAIL.sub("", t)
    # Or just "maps for <X>"
    t = _FALLBACK_HEAD.sub("", t)
    return t.strip(" ,.?!")


@skill(
    name="search_maps_for",
    description="Open Google Maps in the default browser, searched for a location.",
    patterns=[
        "open X in maps", "find X on maps", "show X on maps",
        "X ko maps mein dikhao", "maps mein X dhundo", "maps me X dikhao",
        "X ka location dikhao", "directions to X", "navigate to X",
        "X tak ka raasta", "maps for X", "google maps mein X",
    ],
    required_entities=[],
)
def search_maps_for(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or slots.get("location") or ""
    place = _extract_place(text)
    if not place:
        return "Place batao — jaise 'connaught place ko maps mein dikhao'."
    url = "https://www.google.com/maps/search/" + urllib.parse.quote(place)
    try:
        webbrowser.open(url)
    except Exception as e:
        return f"Browser launch fail: {e}"
    return (f"Opened Google Maps for {place}. "
            "Say 'maps gestures on' to control with hand gestures.")


# ── Maps gesture mode ───────────────────────────────────────


@skill(
    name="maps_gestures_on",
    description="Start the Maps gesture engine — two-hand OK pinch zoom, "
                "open-palm pan, double-tap select. Peace sign arms/disarms.",
    patterns=[
        "maps gestures on", "start maps gestures", "enable maps gestures",
        "start gesture for maps", "maps mein gesture chalu karo",
        "start gesture", "begin maps gestures",
    ],
    required_entities=[],
)
def maps_gestures_on(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    eng = get_maps_gesture_engine()
    ok, msg = eng.start()
    if not ok:
        return f"Maps gestures start nahi hua: {msg}"
    return (msg + " — both hands OK + separate to zoom in, OK + together to "
            "zoom out, open palm to pan, fast double-tap to select. Peace "
            "sign = arm/disarm.")


@skill(
    name="maps_gestures_off",
    description="Stop the Maps gesture engine.",
    patterns=[
        "maps gestures off", "stop maps gestures", "disable maps gestures",
        "maps gesture band karo", "stop gesture for maps",
    ],
    required_entities=[],
)
def maps_gestures_off(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    _, msg = get_maps_gesture_engine().stop()
    return msg


@skill(
    name="maps_gesture_status",
    description="Report whether maps gesture engine is running + armed + counts.",
    patterns=[
        "maps gesture status", "maps gestures status", "are maps gestures on",
        "maps gesture stats",
    ],
    required_entities=[],
)
def maps_gesture_status(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    s = get_maps_gesture_engine().stats()
    return (f"Maps gestures running={s['running']}, armed={s['armed']}. "
            f"zoom in/out {s['zoom_in']}/{s['zoom_out']}, "
            f"pan {s['pan']}, select {s['select']}, "
            f"frames {s['frames']}.")


# ── Mouse gesture mode ──────────────────────────────────────


@skill(
    name="mouse_gestures_on",
    description="Start the V-cursor mouse-gesture engine. Index+middle stuck "
                "together with thumb out = cursor; thumb tap on folded fingers "
                "= click (left hand=L-click, right hand=R-click). Peace = arm.",
    patterns=[
        "mouse gestures on", "start mouse gestures", "enable mouse gestures",
        "cursor gestures on", "start mouse mode", "hand mouse chalu karo",
        "v cursor on",
    ],
    required_entities=[],
)
def mouse_gestures_on(_slots: dict) -> str:
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    ok, msg = get_mouse_gesture_engine().start()
    if not ok:
        return f"Mouse gestures start nahi hua: {msg}"
    return (msg + " — V-cursor pose moves the pointer; thumb-tap the folded "
            "fingers to click (left hand = left click, right hand = right). "
            "Peace sign = arm/disarm.")


@skill(
    name="mouse_gestures_off",
    description="Stop the V-cursor mouse-gesture engine.",
    patterns=[
        "mouse gestures off", "stop mouse gestures", "disable mouse gestures",
        "cursor gestures off", "stop mouse mode", "v cursor off",
    ],
    required_entities=[],
)
def mouse_gestures_off(_slots: dict) -> str:
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    _, msg = get_mouse_gesture_engine().stop()
    return msg


@skill(
    name="mouse_gesture_status",
    description="Report whether mouse gesture engine is running + armed + counts.",
    patterns=[
        "mouse gesture status", "mouse gestures status",
        "are mouse gestures on", "v cursor status",
    ],
    required_entities=[],
)
def mouse_gesture_status(_slots: dict) -> str:
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    s = get_mouse_gesture_engine().stats()
    return (f"Mouse gestures running={s['running']}, armed={s['armed']}. "
            f"moves {s['move']}, L-clicks {s['left_click']}, "
            f"R-clicks {s['right_click']}, frames {s['frames']}.")


# ── Global arm / disarm (peace-sign equivalent in voice) ────


@skill(
    name="gesture_arm",
    description="ARM the maps + mouse gesture engines so detected gestures "
                "actually fire keyboard/mouse actions.",
    patterns=[
        "arm gestures", "gestures arm karo", "enable gesture actions",
        "fire gestures", "gestures live karo",
    ],
    required_entities=[],
)
def gesture_arm(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    get_maps_gesture_engine().set_armed(True)
    get_mouse_gesture_engine().set_armed(True)
    return "Gestures ARMED — actions will fire."


@skill(
    name="gesture_disarm",
    description="DISARM both gesture engines — detections still log, but no "
                "keyboard or mouse actions will fire. Useful for practice.",
    patterns=[
        "disarm gestures", "gestures disarm karo", "gesture safety on",
        "freeze gestures", "stop firing gestures",
    ],
    required_entities=[],
)
def gesture_disarm(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    get_maps_gesture_engine().set_armed(False)
    get_mouse_gesture_engine().set_armed(False)
    return "Gestures DISARMED — practice safely."


@skill(
    name="gesture_arm_status",
    description="Report ARM/DISARM state for the maps + mouse gesture engines.",
    patterns=[
        "gesture arm status", "are gestures armed", "is gesture mode armed",
        "gesture safety status",
    ],
    required_entities=[],
)
def gesture_arm_status(_slots: dict) -> str:
    from core.maps_gesture_engine import get_maps_gesture_engine
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    m = get_maps_gesture_engine()
    u = get_mouse_gesture_engine()
    return (f"Maps engine: running={m.is_running()}, armed={m.is_armed()}. "
            f"Mouse engine: running={u.is_running()}, armed={u.is_armed()}.")
