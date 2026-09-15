"""Conversational state that survives the brain process dying and coming back
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md §4.2 "Still open").

The last big load-free win is retiring an **idle brain child** in split mode:
the supervisor can already stop/start it, and with lite boot a respawn is ~2 s
to ready, which would take the resting footprint from ~478 MB to the GUI's own
~20 MB. The blocker was never the lifecycle — it was that the child owns the
only copy of the conversation:

    "chrome kholo"          → child: dialogue.last_intent = open_app(chrome)
    ‹5 minutes idle, child retired›
    "ab isko band karo"     → fresh child: last_intent = None → "kaunsa app?"

So hibernation needs a way to lift three pieces of *working* memory out of a
child before it dies and put them back into its replacement:

* ``engine.dialogue``      — the last executed turn (pronoun/ellipsis resolution)
* ``engine.history``       — the rolling user/assistant transcript
* ``engine._pending_offer`` — the parked proactive offer the user can accept
  with "haan" on their next turn

That is all of it. Everything else the brain knows (semantic memory, the
knowledge graph, the vault) already persists to disk and is reloaded by the
new child on its own.

Design notes worth keeping:

**Ages, not timestamps.** ``DialogueState.ts`` is ``time.monotonic()``, whose
zero point is undefined and explicitly *not* comparable across processes. A
snapshot that shipped the raw float would land in the new child as garbage —
either "fresh" forever (context an hour stale resolving pronouns) or never
fresh (the whole feature silently dead, with no error to notice). We ship the
*elapsed age* and rebase it against the new process's clock in `restore`.

**JSON-shaped, tolerant.** The snapshot crosses a process boundary and may one
day be written to disk or read by a differently-versioned build, so it is
plain dicts/lists/strings with a schema version, and every section restores
independently — a section this build does not understand is skipped, never
raised. A failed restore costs context; a raised restore costs the turn.

**Mutate in place.** ``core.conversation`` keeps a module-level ``_ACTIVE``
handle on the history object, and skills (``repeat_last``) resolve through it.
Restoring by *replacing* ``engine.history`` would leave that handle pointing at
an orphan, so we refill the existing deque instead.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

SCHEMA = 1

# Hard caps so a snapshot can never balloon the message it rides in. The
# history deque is already bounded (max_turns * 2, currently 16) — this is
# belt-and-braces against a future engine with a longer buffer.
MAX_TURNS = 32
MAX_TEXT = 4000

# An age we refuse to carry across. FRESH_WINDOW_S is 180 s, so anything older
# than this is already unusable for resolution; shipping it would only risk
# clock weirdness resurrecting stale context.
MAX_AGE_S = 3600.0


def _clip(s: Any) -> str:
    return (str(s) if s is not None else "")[:MAX_TEXT]


# ── capture ──────────────────────────────────────────────────────────

def _capture_dialogue(engine: Any) -> Optional[dict]:
    d = getattr(engine, "dialogue", None)
    if d is None or getattr(d, "last_intent", None) is None:
        return None                     # nothing executed yet — nothing to carry
    ts = float(getattr(d, "ts", 0.0) or 0.0)
    age = max(0.0, time.monotonic() - ts) if ts else MAX_AGE_S
    if age > MAX_AGE_S:
        return None                     # too stale to be worth the bytes
    ents = getattr(d, "last_entities", None)
    return {
        "last_intent": str(d.last_intent),
        "last_entities": {str(k): _clip(v) for k, v in (ents or {}).items()},
        "last_user_text": _clip(getattr(d, "last_user_text", "")),
        "last_reply": _clip(getattr(d, "last_reply", "")),
        "age_s": round(age, 3),
    }


def _capture_history(engine: Any) -> Optional[dict]:
    h = getattr(engine, "history", None)
    buf = getattr(h, "_buf", None)
    if buf is None:
        return None
    turns = []
    for t in list(buf)[-MAX_TURNS:]:
        try:
            turns.append({
                "role": str(t.role),
                "content": _clip(t.content),
                "timestamp": str(getattr(t, "timestamp", "") or ""),
                "sentiment": getattr(t, "sentiment", None),
            })
        except Exception as e:          # a malformed turn is not worth the whole snapshot
            log.debug("[brain_snapshot] skipping turn %r: %s", t, e)
    if not turns:
        return None
    return {"turns": turns}


def _capture_offer(engine: Any) -> Optional[dict]:
    offer = getattr(engine, "_pending_offer", None)
    if not offer:
        return None
    try:
        skill, slots = offer
    except Exception:
        return None
    if not skill:
        return None
    return {"skill": str(skill),
            "slots": {str(k): v for k, v in (slots or {}).items()}}


def capture(engine: Any) -> dict:
    """Lift the conversational working memory out of ``engine``.

    Always returns a dict (possibly holding nothing but the version) so a
    caller can snapshot unconditionally without branching. Never raises: this
    runs on the way to killing the process, and a capture failure must not be
    the thing that keeps a child alive.
    """
    snap: dict = {"v": SCHEMA}
    for name, fn in (("dialogue", _capture_dialogue),
                     ("history", _capture_history),
                     ("offer", _capture_offer)):
        try:
            got = fn(engine)
        except Exception as e:
            log.debug("[brain_snapshot] capture of %s failed: %s", name, e)
            continue
        if got:
            snap[name] = got
    return snap


def is_empty(snap: Optional[dict]) -> bool:
    """True when a snapshot carries no actual conversation — a fresh child
    needs no restore round-trip, so hibernation can skip one bus request."""
    if not isinstance(snap, dict):
        return True
    return not any(k in snap for k in ("dialogue", "history", "offer"))


# ── restore ──────────────────────────────────────────────────────────

def _restore_dialogue(engine: Any, sec: dict) -> bool:
    d = getattr(engine, "dialogue", None)
    if d is None or not isinstance(sec, dict) or not sec.get("last_intent"):
        return False
    age = float(sec.get("age_s") or 0.0)
    if age < 0 or age > MAX_AGE_S:
        return False
    d.last_intent = sec["last_intent"]
    d.last_entities = dict(sec.get("last_entities") or {})
    d.last_user_text = sec.get("last_user_text") or ""
    d.last_reply = sec.get("last_reply") or ""
    # Rebase onto THIS process's monotonic clock, keeping the elapsed age the
    # user actually experienced — including the time spent hibernated, which
    # is exactly the point: a turn from 5 minutes ago must still read stale.
    d.ts = time.monotonic() - age
    return True


def _restore_history(engine: Any, sec: dict) -> bool:
    h = getattr(engine, "history", None)
    buf = getattr(h, "_buf", None)
    if buf is None or not isinstance(sec, dict):
        return False
    turns = sec.get("turns") or []
    if not turns:
        return False
    from core.conversation import Turn
    restored = []
    for t in turns[-MAX_TURNS:]:
        if not isinstance(t, dict) or not t.get("role"):
            continue
        restored.append(Turn(role=str(t["role"]),
                             content=t.get("content") or "",
                             timestamp=t.get("timestamp") or "",
                             sentiment=t.get("sentiment")))
    if not restored:
        return False
    # Refill in place: `core.conversation._ACTIVE` and any skill holding a
    # reference keep pointing at the live object. The deque's own maxlen
    # trims the overflow if a snapshot outgrew this build's buffer.
    buf.clear()
    buf.extend(restored)
    return True


def _restore_offer(engine: Any, sec: dict) -> bool:
    if not isinstance(sec, dict) or not sec.get("skill"):
        return False
    # Tuple, not list: the engine's "haan" gate unpacks `skill, slots`.
    engine._pending_offer = (str(sec["skill"]), dict(sec.get("slots") or {}))
    return True


def restore(engine: Any, snap: Optional[dict]) -> list:
    """Put a ``capture()`` back into a freshly built engine.

    Returns the names of the sections that actually landed, for logging and
    tests. Sections are independent: a malformed one is skipped, so a partial
    restore still gives the user back whatever survived.
    """
    if not isinstance(snap, dict):
        return []
    if int(snap.get("v") or 0) > SCHEMA:
        log.warning("[brain_snapshot] snapshot v%s newer than this build (v%s)"
                    " — restoring what is recognised", snap.get("v"), SCHEMA)
    done = []
    for name, fn in (("dialogue", _restore_dialogue),
                     ("history", _restore_history),
                     ("offer", _restore_offer)):
        sec = snap.get(name)
        if not sec:
            continue
        try:
            if fn(engine, sec):
                done.append(name)
        except Exception as e:
            log.debug("[brain_snapshot] restore of %s failed: %s", name, e)
    if done:
        log.info("[brain_snapshot] restored %s", ", ".join(done))
    return done
