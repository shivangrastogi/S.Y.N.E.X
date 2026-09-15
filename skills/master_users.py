"""Master-user management — who is allowed to drive AERIS via gestures.

When the ``master_users`` settings list is non-empty, the gesture engine
will only fire when one of these people is identified in front of the
camera. Strangers / other family members get silently ignored — they
can wave at the screen without anything happening.

Skills:
  * ``i_am_master``        — register current frame as a new master
                            (will auto-name as 'master' if no name given)
  * ``add_master <name>``  — add an already-registered face to the master list
  * ``remove_master <name>``— remove from the master list
  * ``list_masters``       — read back the current list
  * ``face_gate_status``   — describe whether the gate is open / closed and why
  * ``register_face <name>``— enroll a NEW face from the current camera frame
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


def _load_masters() -> list[str]:
    raw = _settings.get("master_users") or []
    if not isinstance(raw, list):
        return []
    return [str(x).strip().lower() for x in raw if str(x).strip()]


def _save_masters(names: list[str]) -> None:
    # Dedup case-insensitively + sort for stable ordering.
    seen: list[str] = []
    for n in names:
        n = n.strip().lower()
        if n and n not in seen:
            seen.append(n)
    _settings.set_("master_users", sorted(seen))


def _extract_name_after(text: str, *triggers: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if t.startswith(trig):
            rest = text[len(trig):].strip()
            return re.sub(r"^(?:as\s+|me\s+as\s+)?", "", rest, flags=re.IGNORECASE).strip(" .,?")
    return text.strip()


def _grab_frame():
    """Snap a single frame off the shared VisionEngine."""
    try:
        from core.vision_engine import get_vision_engine
        return get_vision_engine().snapshot(timeout=1.5)
    except Exception as e:
        log.info("[master_users] snapshot failed: %s", e)
        return None


# ── register_face ──────────────────────────────────────────────────


@skill(
    name="register_face",
    description="Enroll a face from the current camera frame under a name. "
                "Pre-requisite for marking that name as a master.",
    patterns=[
        "register my face", "register face", "face register karo",
        "register face as", "save my face", "remember my face",
        "enroll face", "enroll my face",
        "register face as shivang", "register face as boss",
    ],
    required_entities=[],
)
def register_face(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name_after(
        text,
        "register my face as", "register face as",
        "face register karo as",
        "save my face as", "remember my face as", "enroll my face as",
        "enroll face as",
        "register my face", "register face",
        "save my face", "remember my face",
        "enroll my face", "enroll face",
        "face register karo",
    )
    if not name or name == text.strip().lower():
        return ("Kis naam se register karu? e.g. 'register my face as shivang'.")
    frame = _grab_frame()
    if frame is None:
        return "Camera se frame nahi mila — gesture mode on hai kya?"
    try:
        from core.face_recognition import get_recognizer
    except Exception as e:
        return f"face_recognition module load fail: {e}"
    rec = get_recognizer()
    if not rec.is_available():
        return "InsightFace nahi mila — pip install insightface."
    ok, msg = rec.register_from_frame(name, frame)
    return msg


# ── i_am_master ────────────────────────────────────────────────────


@skill(
    name="i_am_master",
    description="Register the current face as a new master user and "
                "add them to the master_users list in one shot.",
    patterns=[
        "i am master", "i am the master", "main hu master",
        "make me master", "set me as master",
        "mark me as master", "mujhe master banao",
        "make me the master", "i am the boss",
    ],
    required_entities=[],
)
def i_am_master(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    spoken_name = _extract_name_after(
        text,
        "set me as master", "make me the master", "make me master",
        "mark me as master", "mujhe master banao",
        "i am the master", "i am master", "main hu master",
        "i am the boss",
    )
    if spoken_name == text.strip().lower():
        spoken_name = ""    # nothing extracted — leave blank
    frame = _grab_frame()
    if frame is None:
        return "Camera frame nahi mila — pehle 'gesture mode on' karo."
    try:
        from core.face_recognition import get_recognizer
    except Exception as e:
        return f"face_recognition load fail: {e}"
    rec = get_recognizer()
    if not rec.is_available():
        return ("Face recognition unavailable (insightface nahi). "
                "Master user nahi set ho sakta.")

    # First try to MATCH against an existing face in the registry.
    identified = rec.identify_faces(frame)
    existing = next((n for n in identified if n), None)
    if existing:
        canon = existing.strip().lower()
        masters = _load_masters()
        if canon in masters:
            return (f"'{existing}' already master hai. List: "
                    f"{', '.join(sorted(set(masters)))}.")
        masters.append(canon)
        _save_masters(masters)
        return (f"Pehchana — '{existing}' ko master bana diya. "
                f"List: {', '.join(sorted(set(masters)))}.")

    # No existing match → register a new face with the given name.
    new_name = (spoken_name or "master").strip().lower()
    ok, msg = rec.register_from_frame(new_name, frame)
    if not ok:
        return msg
    masters = _load_masters()
    masters.append(new_name)
    _save_masters(masters)
    return f"{msg}. Master list: {', '.join(sorted(set(masters)))}."


# ── add_master / remove_master ─────────────────────────────────────


@skill(
    name="add_master",
    description="Add an already-registered face to the master_users list.",
    patterns=[
        "add master", "add master shivang", "add master sara",
        "add to master list", "make X a master",
        "X ko master banao", "X master hai",
    ],
    required_entities=[],
)
def add_master(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name_after(
        text,
        "add to master list",
        "add master", "make master",
    )
    # Also handle "ko master banao" suffix form.
    if not name or name == text.strip().lower():
        m = re.search(r"\b([\w\s.\-']{2,40}?)\s+(?:ko\s+master\s+banao|master\s+hai)\b",
                      text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    name = (name or "").strip().lower()
    if not name:
        return "Kiska naam? e.g. 'add master shivang'."
    try:
        from core.face_recognition import get_registry
    except Exception:
        get_registry = None  # type: ignore
    if get_registry is not None and name not in get_registry().all_names():
        return (f"'{name}' face registered nahi hai. "
                f"Pehle 'register my face as {name}' bolo.")
    masters = _load_masters()
    if name in masters:
        return f"'{name}' already master list mein hai."
    masters.append(name)
    _save_masters(masters)
    return f"Added '{name}' as master. List: {', '.join(sorted(set(masters)))}."


@skill(
    name="remove_master",
    description="Remove a name from the master_users list.",
    patterns=[
        "remove master", "remove master shivang", "remove from masters",
        "X ko master se hatao", "remove X as master",
        "delete master", "drop master",
    ],
    required_entities=[],
)
def remove_master(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name_after(
        text,
        "remove from masters", "remove from master list",
        "remove master", "delete master", "drop master",
        "remove as master",
    )
    if not name or name == text.strip().lower():
        m = re.search(r"\b([\w\s.\-']{2,40}?)\s+ko\s+master\s+se\s+hatao\b",
                      text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    name = (name or "").strip().lower()
    if not name:
        return "Kiska naam hatana hai? e.g. 'remove master shivang'."
    masters = _load_masters()
    if name not in masters:
        return f"'{name}' master list mein tha hi nahi."
    masters.remove(name)
    _save_masters(masters)
    return (f"Removed '{name}'. List: " +
            (", ".join(sorted(set(masters))) or "(empty)"))


# ── list_masters / face_gate_status ────────────────────────────────


@skill(
    name="list_masters",
    description="List every user marked as master (allowed to drive gestures).",
    patterns=[
        "list masters", "show masters", "who are masters",
        "masters dikhao", "kaun master hai", "master list",
        "who can use gestures", "gesture allow list",
    ],
    required_entities=[],
)
def list_masters(_slots: dict) -> str:
    masters = _load_masters()
    if not masters:
        return ("Koi master set nahi — gesture gate disabled hai. "
                "Sab faces gestures fire kar sakte hain.")
    return f"{len(masters)} master(s): {', '.join(sorted(masters))}."


@skill(
    name="face_gate_status",
    description="Explain whether the face gate is open/closed and the last-seen status.",
    patterns=[
        "face gate status", "gate status", "is face gate on",
        "face gate kya hai", "gate kya hai", "kya face gate enabled hai",
        "master gate status",
    ],
    required_entities=[],
)
def face_gate_status(_slots: dict) -> str:
    try:
        from core.face_gate import explain
        return explain()
    except Exception as e:
        return f"face_gate module load fail: {e}"
