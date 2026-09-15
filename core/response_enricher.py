"""LLM-backed reply enricher with persistent cache.

When a skill returns a stock template ("Good morning, sir."), the enricher
generates richer / more-varied phrasings via the local LLM (Ollama), then
caches every successful generation to ``data/response_cache.json`` so the
SAME line never gets used twice in a row.

Strategy per call:

  1. **Try cache** — if we have ≥``_PREFER_CACHE_AT`` unused entries for
     this slot, pick the least-recently-used one. Free, instant.
  2. **Try LLM** — prompt Ollama for a fresh phrasing; on success, append
     to the cache + return it.
  3. **Fall back** — return the base reply verbatim.

The "slot" is whatever key the caller supplies (typically the skill name
or a (skill, sub-context) tuple). Each slot has its own pool with an
LRU cap so the cache file stays small.

Public API:
    enriched_reply(slot, base_reply, hint=None) -> str
    is_enabled() -> bool
    set_enabled(on)
    clear_cache(slot=None) -> int
    stats() -> dict
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CACHE_PATH = _ROOT / "data" / "response_cache.json"

_PER_SLOT_CAP = 20            # max stored variations per slot
_PREFER_CACHE_AT = 3          # need ≥ N unused to skip the LLM
_RECENT_AVOID_N = 3           # don't repeat the last N picks
_LLM_TIMEOUT_S = 4.0          # bail fast if Ollama is slow

_SETTINGS_KEY = "response_enrich"      # bool, default True

_LOCK = threading.RLock()


# ── persistence ──────────────────────────────────────────────────


def _load() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    try:
        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        log.warning("[enricher] cache load failed: %s", e)
        return {}
    out: dict[str, dict] = {}
    for k, v in raw.items() if isinstance(raw, dict) else []:
        if not isinstance(v, dict):
            continue
        entries = v.get("entries") or []
        if not isinstance(entries, list):
            entries = []
        # Normalise entries to {text, ts, used}
        norm = []
        for e in entries:
            if isinstance(e, dict) and "text" in e:
                norm.append({
                    "text": str(e["text"]),
                    "ts":   float(e.get("ts") or 0.0),
                    "used": int(e.get("used") or 0),
                })
            elif isinstance(e, str):
                norm.append({"text": e, "ts": 0.0, "used": 0})
        out[str(k)] = {
            "entries": norm,
            "recent":  list((v.get("recent") or []))[-_RECENT_AVOID_N:],
        }
    return out


_STATE: dict = _load()


def _save() -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_STATE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("[enricher] cache save failed: %s", e)


# ── enable / disable ────────────────────────────────────────────


def is_enabled() -> bool:
    try:
        from core import settings as _settings
        v = _settings.get(_SETTINGS_KEY, True)
    except Exception:
        v = True
    return bool(v)


def set_enabled(on: bool) -> None:
    try:
        from core import settings as _settings
        _settings.set_(_SETTINGS_KEY, bool(on))
    except Exception:
        pass


# ── cache helpers ───────────────────────────────────────────────


def _slot(slot_key: str) -> dict:
    with _LOCK:
        return _STATE.setdefault(str(slot_key), {"entries": [], "recent": []})


def _pick_from_cache(slot_key: str) -> Optional[str]:
    """Return an unused (or least-recently-used) cached line, or None."""
    s = _slot(slot_key)
    entries = s["entries"]
    recent = set(s["recent"])
    if len(entries) < _PREFER_CACHE_AT:
        return None
    # Prefer entries not in the recent-avoid window.
    fresh = [e for e in entries if e["text"] not in recent]
    pool = fresh if fresh else entries
    # Sort by (used, ts) ascending — least-used + oldest first.
    pool.sort(key=lambda e: (e["used"], e["ts"]))
    pick = pool[0]
    _mark_used(slot_key, pick["text"])
    return pick["text"]


def _mark_used(slot_key: str, text: str) -> None:
    s = _slot(slot_key)
    now = time.time()
    for e in s["entries"]:
        if e["text"] == text:
            e["used"] += 1
            e["ts"] = now
            break
    # Maintain recent ring buffer.
    s["recent"].append(text)
    if len(s["recent"]) > _RECENT_AVOID_N:
        s["recent"] = s["recent"][-_RECENT_AVOID_N:]
    _save()


def _append_to_cache(slot_key: str, text: str) -> None:
    if not text:
        return
    s = _slot(slot_key)
    if any(e["text"] == text for e in s["entries"]):
        # Dedup — bump usage instead.
        _mark_used(slot_key, text)
        return
    s["entries"].append({"text": text, "ts": time.time(), "used": 1})
    # Cap pool size — drop the oldest entry once we exceed.
    if len(s["entries"]) > _PER_SLOT_CAP:
        s["entries"].sort(key=lambda e: e["ts"])
        s["entries"] = s["entries"][-_PER_SLOT_CAP:]
    s["recent"].append(text)
    if len(s["recent"]) > _RECENT_AVOID_N:
        s["recent"] = s["recent"][-_RECENT_AVOID_N:]
    _save()


# ── LLM generation ──────────────────────────────────────────────


def _via_llm(slot_key: str, base: str, hint: str = "") -> Optional[str]:
    try:
        from core.llm_chat import LLMChat
    except Exception:
        return None
    llm = LLMChat()
    if not llm.is_available():
        return None

    recent = _slot(slot_key)["recent"][-_RECENT_AVOID_N:]
    avoid_block = ""
    if recent:
        avoid_block = ("\n\nAvoid these recent phrasings:\n  - "
                       + "\n  - ".join(recent))

    prompt = (
        f"You are AERIS, a Hinglish-speaking desktop assistant. Generate ONE "
        f"natural, friendly, varied reply for the '{slot_key}' situation. "
        f"Be brief — under 18 words. Mix English + light Hinglish. Do not "
        f"include quotation marks, explanations, or preambles. "
        f"Reply text only.\n\n"
        f"Base reply (use as starting point, but rephrase): {base!r}\n"
        f"Optional hint: {hint or '(none)'}"
        f"{avoid_block}"
    )

    try:
        out = llm.reply(
            user_text=prompt,
            sentiment_label="positive",
            memory_facts={},
            history=[],
        )
    except Exception as e:
        log.info("[enricher] LLM call raised: %s", e)
        return None
    if not out:
        return None
    text = out.strip().strip('"').strip("'").rstrip(".")
    # Reject obviously-malformed output.
    if len(text) < 3 or len(text) > 300:
        return None
    # Single line.
    text = text.splitlines()[0].strip()
    return text or None


# ── public ──────────────────────────────────────────────────────


def enriched_reply(slot_key: str, base_reply: str, hint: str = "") -> str:
    """Return a varied reply for ``slot_key``. Falls through to ``base_reply``
    if enrichment disabled or unavailable. Never raises."""
    if not is_enabled() or not base_reply:
        return base_reply
    try:
        cached = _pick_from_cache(slot_key)
        if cached:
            return cached
        fresh = _via_llm(slot_key, base_reply, hint=hint)
        if fresh:
            _append_to_cache(slot_key, fresh)
            return fresh
    except Exception as e:
        log.debug("[enricher] enriched_reply raised: %s", e)
    return base_reply


def clear_cache(slot_key: Optional[str] = None) -> int:
    with _LOCK:
        if slot_key is None:
            n = sum(len(s["entries"]) for s in _STATE.values())
            _STATE.clear()
        else:
            n = len(_STATE.pop(slot_key, {}).get("entries", []))
        _save()
    return n


def stats() -> dict:
    with _LOCK:
        slots = []
        total = 0
        for k, v in _STATE.items():
            n = len(v.get("entries") or [])
            total += n
            slots.append({"slot": k, "count": n})
        slots.sort(key=lambda s: -s["count"])
        return {
            "enabled":   is_enabled(),
            "llm_available": _llm_available_safe(),
            "total":     total,
            "slots":     slots,
        }


def _llm_available_safe() -> bool:
    try:
        from core.llm_chat import LLMChat
        return LLMChat().is_available()
    except Exception:
        return False
