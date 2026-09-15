"""Presence journal — the persistent memory behind the eternal presence.

A rolling, append-only JSON-lines log at ``data/presence_journal.jsonl`` that
records two things over time:

* **state transitions** — every AWAY/IDLE/ACTIVE/FOCUS change, with the
  workspace profile and how long the previous state lasted; and
* **moments** — every proactive nudge the engine surfaced.

This is the load-bearing history layer the rest of the proactive roadmap
depends on: the daily digest (Phase 1e) reads ``day_summary()``, and the
routine learner (Phase 2a) reads the arrival/focus rhythm from
``transitions()``.

Design choices that keep it cheap and crash-safe:

* append is a plain line-write (O(1), no rewrite of the whole file);
* the file is trimmed back to ``_MAX_LINES`` only occasionally, and that trim
  goes through ``atomic_io`` so a power-loss mid-trim can't corrupt history;
* every public call is best-effort — journalling must never take the app down.

    from core.presence_journal import get_journal
    j = get_journal()
    j.record_state("focus", prev="active", held_s=512, profile="CODING")
    j.record_moment("greeting", "Good morning!", priority=1)
    print(j.day_summary())   # {'focus_s': ..., 'arrivals': ..., 'moments': ...}
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_MAX_LINES = 5000              # ~weeks of normal use; trimmed past this
_TRIM_SLACK = 500             # only trim once we're this far over the cap


def _default_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "presence_journal.jsonl")


class PresenceJournal:
    """Append-only presence history. Process-wide via ``get_journal()``."""

    def __init__(self, path: Optional[str] = None, *, max_lines: int = _MAX_LINES):
        self._path = path or _default_path()
        self._max_lines = max(100, max_lines)
        self._lock = threading.RLock()
        self._appends_since_trim = 0
        # Check for a trim this often. Scales down with the cap so a small
        # journal still trims promptly instead of overshooting by 500.
        self._trim_check_every = min(_TRIM_SLACK, self._max_lines)

    # ── writes ────────────────────────────────────────────────────────

    def record_state(self, state: str, *, prev: str = "", held_s: float = 0.0,
                     profile: str = "") -> None:
        self._append({
            "t": "state", "ts": _now_iso(), "state": state, "prev": prev,
            "held_s": round(float(held_s), 1), "profile": profile,
        })

    def record_moment(self, kind: str, text: str = "", *,
                      priority: int = 1, state: str = "") -> None:
        self._append({
            "t": "moment", "ts": _now_iso(), "kind": kind,
            "priority": int(priority), "state": state, "text": text,
        })

    def _append(self, rec: Dict[str, Any]) -> None:
        line = json.dumps(rec, ensure_ascii=False)
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
                self._appends_since_trim += 1
            except Exception:
                log.debug("[journal] append failed", exc_info=True)
                return
            if self._appends_since_trim >= self._trim_check_every:
                self._appends_since_trim = 0
                self._maybe_trim()

    def _maybe_trim(self) -> None:
        """Keep only the last ``_max_lines`` records. Atomic rewrite."""
        try:
            lines = self._read_lines()
            if len(lines) <= self._max_lines + self._trim_check_every:
                return
            keep = lines[-self._max_lines:]
            from core.atomic_io import write_atomic_text
            write_atomic_text(self._path, "".join(keep), fsync=False)
            log.info("[journal] trimmed to %d records.", len(keep))
        except Exception:
            log.debug("[journal] trim failed", exc_info=True)

    # ── reads ─────────────────────────────────────────────────────────

    def _read_lines(self) -> List[str]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return fh.readlines()
        except FileNotFoundError:
            return []
        except Exception:
            log.debug("[journal] read failed", exc_info=True)
            return []

    def records(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        lines = self._read_lines()
        if limit is not None:
            lines = lines[-limit:]
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    def transitions(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return [r for r in self.records(limit=limit) if r.get("t") == "state"]

    def day_summary(self, day: Optional[date] = None) -> Dict[str, Any]:
        """Aggregate one calendar day for the digest.

        Counts seconds spent in each state (attributing a transition's
        ``held_s`` to the state it just *left*), number of arrivals
        (AWAY/IDLE → ACTIVE/FOCUS), and proactive moments by kind.
        """
        day = day or date.today()
        prefix = day.isoformat()
        state_s: Dict[str, float] = {}
        arrivals = 0
        moments: Dict[str, int] = {}
        for r in self.records():
            if not str(r.get("ts", "")).startswith(prefix):
                continue
            if r.get("t") == "state":
                left = r.get("prev") or ""
                if left:
                    state_s[left] = state_s.get(left, 0.0) + float(r.get("held_s", 0))
                if r.get("prev") in ("away", "idle") and r.get("state") in (
                        "active", "focus"):
                    arrivals += 1
            elif r.get("t") == "moment":
                k = r.get("kind", "?")
                moments[k] = moments.get(k, 0) + 1
        return {
            "day": prefix,
            "focus_s": round(state_s.get("focus", 0.0)),
            "active_s": round(state_s.get("active", 0.0)),
            "away_s": round(state_s.get("away", 0.0) + state_s.get("idle", 0.0)),
            "arrivals": arrivals,
            "moments": moments,
        }

    def digest_line(self, day: Optional[date] = None) -> str:
        """One human Hinglish line for the morning digest."""
        s = self.day_summary(day)
        if not s["focus_s"] and not s["active_s"] and not s["arrivals"]:
            return ""
        fm = s["focus_s"] // 60
        am = (s["active_s"] + s["focus_s"]) // 60
        return (f"Kal: ~{am} min screen pe, {fm} min deep focus, "
                f"{s['arrivals']} baar baithe. Aaj phir se chalein?")


# ── singleton ─────────────────────────────────────────────────────────── #

_DEFAULT: Optional[PresenceJournal] = None
_DEFAULT_LOCK = threading.Lock()


def get_journal() -> PresenceJournal:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = PresenceJournal()
        return _DEFAULT


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":      # pragma: no cover — manual smoke
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    j = PresenceJournal(path=os.path.join(os.path.dirname(__file__),
                                          "_journal_smoke.jsonl"))
    j.record_state("active", prev="away", held_s=300, profile="CODING")
    j.record_state("focus", prev="active", held_s=520, profile="CODING")
    j.record_moment("greeting", "Good morning!", priority=1, state="active")
    print(j.day_summary())
    print(j.digest_line())
    os.remove(j._path)
