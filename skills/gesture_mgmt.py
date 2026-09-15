"""Gesture management voice skills — bind/unbind/list bindings + trace.

  * ``gesture_bind``    — "bind peace to screenshot_full" / "remap X to Y"
  * ``gesture_unbind``  — "unbind peace" — revert to the built-in action
  * ``gesture_bindings``— "list gesture bindings"
  * ``gesture_trace``   — "show gesture trace" — last 10 fires + blocks
  * ``gesture_trace_clear`` — wipe the trace log

Bindings live in settings as ``gesture_binding.<gesture_name> = <skill_name>``.
The GestureEngine consults that key on every emit before falling back to
its built-in DEFAULT_ACTIONS.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill, get_skill

log = logging.getLogger(__name__)


# Canonical gesture names. Must match keys in core.gesture_engine.DEFAULT_ACTIONS.
def _known_gestures() -> list[str]:
    try:
        from core.gesture_engine import DEFAULT_ACTIONS
        return sorted(DEFAULT_ACTIONS.keys())
    except Exception:
        return []


_BIND_RE = re.compile(
    r"(?:bind|remap|map|set)\s+"
    r"(?:gesture\s+)?(?P<gesture>[a-z_][a-z0-9_]*)"
    r"\s+(?:to|=|->|→)\s+"
    r"(?P<skill>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)

_UNBIND_RE = re.compile(
    r"(?:unbind|reset|remove|drop)\s+"
    r"(?:gesture\s+)?(?:binding\s+(?:for\s+)?)?(?P<gesture>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _settings_key(gesture: str) -> str:
    return f"gesture_binding.{gesture}"


# ── gesture_bind ───────────────────────────────────────────────────


@skill(
    name="gesture_bind",
    description="Rebind a gesture to a registered skill name "
                "(e.g. 'bind peace to screenshot_full').",
    patterns=[
        "bind gesture", "bind peace to", "bind double_pinch to",
        "remap gesture", "remap peace to",
        "map gesture", "set gesture binding",
        "gesture bind karo", "gesture map karo",
    ],
    required_entities=[],
)
def gesture_bind(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _BIND_RE.search(text)
    if not m:
        return ("Format: 'bind <gesture> to <skill>'. Example: "
                "'bind peace to screenshot_full'.")
    gesture = m.group("gesture").lower()
    target_skill = m.group("skill").lower()

    if gesture not in _known_gestures():
        nearest = ", ".join(_known_gestures()[:8])
        return (f"'{gesture}' unknown gesture. Known: {nearest}...")
    if get_skill(target_skill) is None:
        return (f"'{target_skill}' registered skill nahi hai. "
                f"'help' bolo to skill list dekho.")
    _settings.set_(_settings_key(gesture), target_skill)
    return f"Bound — {gesture} → {target_skill}."


# ── gesture_unbind ─────────────────────────────────────────────────


@skill(
    name="gesture_unbind",
    description="Remove a gesture binding override — revert to the built-in action.",
    patterns=[
        "unbind gesture", "unbind peace", "reset gesture binding",
        "remove gesture binding", "gesture binding hatao",
        "reset peace", "unbind double_pinch",
    ],
    required_entities=[],
)
def gesture_unbind(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _UNBIND_RE.search(text)
    if not m:
        return "Format: 'unbind <gesture>'. Example: 'unbind peace'."
    gesture = m.group("gesture").lower()
    if gesture not in _known_gestures():
        return f"'{gesture}' unknown gesture."
    key = _settings_key(gesture)
    cur = _settings.get(key)
    if cur is None:
        return f"'{gesture}' had no override; already on default action."
    # Settings store has no native delete — set to empty string and the
    # resolver treats falsy as "no override".
    _settings.set_(key, "")
    return f"Unbound — {gesture} is back on its default ({cur} → built-in)."


# ── gesture_bindings ───────────────────────────────────────────────


@skill(
    name="gesture_bindings",
    description="List every custom gesture binding currently in effect.",
    patterns=[
        "list gesture bindings", "show gesture bindings",
        "gesture bindings dikhao", "list bindings",
        "what are my gesture bindings", "kya gestures bind hain",
    ],
    required_entities=[],
)
def gesture_bindings(_slots: dict) -> str:
    overrides: list[tuple[str, str]] = []
    for g in _known_gestures():
        val = _settings.get(_settings_key(g))
        if val:
            overrides.append((g, str(val)))
    if not overrides:
        return ("Koi custom gesture binding nahi hai — sab gestures "
                "apni built-in action chala rahe hain.")
    lines = [f"{len(overrides)} custom binding(s):"]
    for g, sk in overrides:
        lines.append(f"  • {g:24s} → {sk}")
    return "\n".join(lines)


# ── gesture_trace ──────────────────────────────────────────────────


@skill(
    name="gesture_trace",
    description="Show the last 10 gesture events (fires + blocks).",
    patterns=[
        "gesture trace", "show gesture trace", "gesture log",
        "gesture history", "kya gestures hue", "gestures dikhao recent",
        "recent gestures",
    ],
    required_entities=[],
)
def gesture_trace(_slots: dict) -> str:
    try:
        from core import gesture_trace as gt
    except Exception as e:
        return f"gesture_trace load fail: {e}"
    events = gt.tail(10)
    if not events:
        return "Gesture trace khaali hai — abhi tak koi gesture nahi mila."
    lines = [f"Last {len(events)} gesture events:"]
    for ev in events:
        ts = ev.get("ts", "?")
        g = ev.get("gesture", "?")
        status = ev.get("status", "?")
        faces = ev.get("faces") or []
        face_part = f" by {', '.join(faces)}" if faces else ""
        reason = ev.get("blocked_reason")
        reason_part = f" [reason: {reason}]" if reason else ""
        lines.append(f"  {ts}  {g:20s} {status}{face_part}{reason_part}")
    return "\n".join(lines)


@skill(
    name="gesture_trace_clear",
    description="Wipe the gesture trace log.",
    patterns=[
        "clear gesture trace", "gesture trace clear", "wipe gesture log",
        "gesture log clear", "reset gesture log",
    ],
    required_entities=[],
)
def gesture_trace_clear(_slots: dict) -> str:
    try:
        from core import gesture_trace as gt
    except Exception as e:
        return f"gesture_trace load fail: {e}"
    n = gt.clear()
    return f"Gesture trace cleared ({n} bytes removed)."


# ── what_does_gesture_do (reverse lookup) ─────────────────────────


_LOOKUP_RE = re.compile(
    r"(?:what\s+does|what's|kya\s+karta\s+hai|kya\s+karta\s+hua\s+hai|"
    r"what\s+is\s+(?:my\s+)?|describe|explain)\s+"
    r"(?:my\s+|mera\s+|meri\s+|the\s+)?"
    r"(?P<gesture>[a-z_][a-z0-9_]*)"
    r"(?:\s+(?:gesture|do|trigger|fire|effect|action))?",
    re.IGNORECASE,
)


@skill(
    name="what_does_gesture_do",
    description="Describe the effective action for a gesture (override "
                "if set, else built-in default).",
    patterns=[
        "what does peace do", "what does double_pinch do",
        "what does my peace gesture do",
        "what is peace gesture", "describe peace gesture",
        "peace gesture kya karta hai",
        "what does palm_fist_lock trigger",
        "explain double_pinch", "explain peace",
    ],
    required_entities=[],
)
def what_does_gesture_do(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _LOOKUP_RE.search(text)
    if not m:
        return ("Format: 'what does <gesture> do?'. e.g. 'what does peace do?'.")
    gesture = m.group("gesture").lower()
    if gesture not in _known_gestures():
        nearest = ", ".join(_known_gestures()[:6])
        return f"'{gesture}' unknown gesture. Try: {nearest}..."
    override = _settings.get(_settings_key(gesture)) or ""
    if override:
        sk = get_skill(str(override))
        desc = sk.description if sk else "(skill not registered)"
        return f"{gesture} → custom binding: '{override}' ({desc})."
    # Built-in default — pull its function name as a readable hint.
    try:
        from core.gesture_engine import DEFAULT_ACTIONS
        fn = DEFAULT_ACTIONS.get(gesture)
        fn_name = getattr(fn, "__name__", "lambda")
        return f"{gesture} → built-in default action ({fn_name})."
    except Exception:
        return f"{gesture} → built-in default action."


# ── gesture_stats (trace aggregation) ─────────────────────────────


@skill(
    name="gesture_stats",
    description="Aggregate gesture trace counts by name + face for the last hour.",
    patterns=[
        "gesture stats", "gesture statistics",
        "kya kya gestures hue", "trace stats",
        "gesture counts", "gestures kitne hue today",
        "show gesture activity",
    ],
    required_entities=[],
)
def gesture_stats(_slots: dict) -> str:
    try:
        from core import gesture_trace as gt
        from datetime import datetime, timedelta
    except Exception as e:
        return f"gesture_trace load fail: {e}"
    events = gt.tail(500)
    if not events:
        return "Gesture trace khaali hai — abhi tak kuch nahi mila."
    # Filter to the last hour by parsing ISO timestamps.
    cutoff = datetime.now() - timedelta(hours=1)
    recent = []
    for ev in events:
        try:
            ts = datetime.fromisoformat(ev.get("ts", ""))
        except ValueError:
            continue
        if ts >= cutoff:
            recent.append(ev)
    if not recent:
        return "Last hour mein koi gesture nahi mila."
    by_gesture: dict[str, int] = {}
    by_face: dict[str, int] = {}
    fired = blocked = 0
    for ev in recent:
        name = ev.get("gesture") or "?"
        by_gesture[name] = by_gesture.get(name, 0) + 1
        for f in (ev.get("faces") or []):
            by_face[f] = by_face.get(f, 0) + 1
        if ev.get("status") == "fired":
            fired += 1
        elif ev.get("status") == "blocked":
            blocked += 1
    lines = [
        f"Last 1h: {fired} fired · {blocked} blocked · {len(recent)} total events"
    ]
    if by_gesture:
        lines.append("By gesture:")
        for g, n in sorted(by_gesture.items(), key=lambda kv: -kv[1])[:10]:
            lines.append(f"  • {g:24s} {n}")
    if by_face:
        lines.append("By face:")
        for f, n in sorted(by_face.items(), key=lambda kv: -kv[1]):
            lines.append(f"  • {f:24s} {n}")
    return "\n".join(lines)
