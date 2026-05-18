"""A.E.R.I.S Automation Engine — routines, triggers, action workflows.

This is the "intelligent workflow" surface the user asked for. Routines
are user-defined JSON objects with one **trigger** and a list of
sequential **actions**. A daemon scheduler thread evaluates time
triggers every 30 s; other triggers (battery, gesture, workspace,
manual) are event-driven and subscribe to existing monitors.

Architecture
------------

      data/routines.json
              │
              ▼
       RoutineStore  ──── atomic_io.write_atomic_json
              │
              ▼
   AutomationEngine ◄──── PowerMonitor      (battery, idle)
              │     ◄──── WorkspaceMonitor  (foreground app)
              │     ◄──── GestureEngine     (hand gestures)
              │     ◄──── internal scheduler thread (time triggers)
              │
              ▼
        _execute_routine()  →  ActionDispatcher
                                   │
            ┌────────┬──────────┬───┴──────┬────────┬─────────┐
            ▼        ▼          ▼          ▼        ▼         ▼
         notify  open_app   open_url   ai_prompt  delay  run_skill

Triggers
--------
* ``time``            — 5-field cron (``"min hour dom mon dow"``).
                        e.g. ``"0 8 * * *"`` = 8:00 daily.
* ``battery_below``   — fires once on the falling edge through ``percent``.
* ``battery_above``   — fires once on the rising edge through ``percent``.
* ``gesture``         — gesture-engine event name (e.g. ``"three_up"``).
* ``workspace_enter`` — workspace classifier crosses into a profile
                        (CODING / MEETING / GAMING / ...).
* ``manual``          — only ``run_routine(id)`` can fire it.

Actions
-------
* ``notify``     — tray toast, params: title, body
* ``open_app``   — subprocess.Popen on params.value
* ``open_url``   — webbrowser.open on params.value
* ``run_skill``  — invoke ``skill_breaker.call(name, fn, slots)``
* ``ai_prompt``  — feed text to the AERIS brain (via registered handler)
* ``delay``      — sleep params.seconds between steps

Adding a new action: implement ``_action_<kind>(self, params)`` and add
its name to ``_ACTION_KINDS`` — the dispatcher auto-discovers it.

Threading model
---------------
* All trigger sources run on their own threads (we don't own them).
* When ANY trigger fires for ANY enabled routine, we submit the routine
  to a small thread pool (4 workers). Actions inside one routine run
  sequentially in their submitted thread; routines run in parallel.
* The scheduler thread is daemon + holds no locks across sleeps, so
  process exit is clean even mid-routine.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from core.atomic_io import write_atomic_json

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_ROUTINES_PATH = os.path.join(_ROOT, "data", "routines.json")


# ── Models ─────────────────────────────────────────────────────────── #

@dataclass
class Trigger:
    """One trigger spec. ``params`` keys depend on ``kind`` — see module doc."""
    kind: str
    params: dict = field(default_factory=dict)

    def summary(self) -> str:
        k = self.kind
        p = self.params
        if k == "time":
            return f"Daily {_cron_humanise(p.get('cron', ''))}"
        if k == "battery_below":
            return f"Battery falls below {p.get('percent', '?')}%"
        if k == "battery_above":
            return f"Battery rises above {p.get('percent', '?')}%"
        if k == "gesture":
            return f"Gesture: {p.get('name', '?')}"
        if k == "workspace_enter":
            return f"Workspace → {p.get('profile', '?')}"
        if k == "interval":
            secs = int(p.get("seconds", 0))
            if secs >= 3600 and secs % 3600 == 0:
                return f"Every {secs // 3600} hour(s)"
            if secs >= 60 and secs % 60 == 0:
                return f"Every {secs // 60} minute(s)"
            return f"Every {secs}s"
        if k == "manual":
            return "Manual (run-now only)"
        return f"{k} {p}"


@dataclass
class Action:
    """One action step. ``params`` keys depend on ``kind`` — see module doc."""
    kind: str
    params: dict = field(default_factory=dict)

    def summary(self) -> str:
        p = self.params
        if self.kind == "notify":
            return f"notify '{p.get('title') or p.get('body') or ''}'"
        if self.kind == "open_app":
            return f"open app: {p.get('value', '?')}"
        if self.kind == "open_url":
            return f"open url: {p.get('value', '?')}"
        if self.kind == "run_skill":
            return f"skill: {p.get('name', '?')}"
        if self.kind == "ai_prompt":
            v = (p.get('value') or '')[:40]
            return f"ai: '{v}{'…' if len(p.get('value', '')) > 40 else ''}'"
        if self.kind == "delay":
            return f"wait {p.get('seconds', '?')}s"
        return self.kind


@dataclass
class Routine:
    id: str
    name: str
    description: str = ""
    trigger: Trigger = field(default_factory=lambda: Trigger(kind="manual"))
    actions: list[Action] = field(default_factory=list)
    enabled: bool = False
    last_fired_ts: float = 0.0
    fire_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": asdict(self.trigger),
            "actions": [asdict(a) for a in self.actions],
            "enabled": self.enabled,
            "last_fired_ts": self.last_fired_ts,
            "fire_count": self.fire_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Routine":
        return cls(
            id=str(d.get("id") or d.get("name", "untitled")),
            name=str(d.get("name", "Untitled")),
            description=str(d.get("description", "")),
            trigger=_trigger_from_dict(d.get("trigger") or {}),
            actions=[_action_from_dict(a) for a in d.get("actions", [])],
            enabled=bool(d.get("enabled", False)),
            last_fired_ts=float(d.get("last_fired_ts", 0.0)),
            fire_count=int(d.get("fire_count", 0)),
        )


def _trigger_from_dict(t: dict) -> Trigger:
    """Accept BOTH the canonical nested form ``{"kind": X, "params": {...}}``
    and a flat legacy form ``{"kind": X, "cron": "..."}``. Round-tripping a
    nested-form file through to_dict + from_dict must reproduce the same
    structure — that's the round-trip invariant the engine relies on.
    """
    kind = str(t.get("kind", "manual"))
    if "params" in t and isinstance(t.get("params"), dict):
        params = dict(t["params"])
    else:
        # Flat form — everything that isn't "kind" goes into params.
        params = {k: v for k, v in t.items() if k != "kind"}
    return Trigger(kind=kind, params=params)


def _action_from_dict(a: dict) -> Action:
    """Same dual-shape logic as ``_trigger_from_dict``."""
    kind = str(a.get("kind", ""))
    if "params" in a and isinstance(a.get("params"), dict):
        params = dict(a["params"])
    else:
        params = {k: v for k, v in a.items() if k != "kind"}
    return Action(kind=kind, params=params)


# ── Cron matcher (5-field, 1-minute resolution) ───────────────────── #

def _parse_cron_field(field: str, lo: int, hi: int) -> set[int]:
    """Parse one cron field — supports ``*``, ``a-b``, ``a,b,c``, ``*/n``."""
    out: set[int] = set()
    for chunk in field.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        step = 1
        if "/" in chunk:
            chunk, s = chunk.split("/", 1)
            step = int(s)
        if chunk == "*" or chunk == "":
            start, end = lo, hi
        elif "-" in chunk:
            a, b = chunk.split("-", 1)
            start, end = int(a), int(b)
        else:
            start = end = int(chunk)
        out.update(range(start, end + 1, step))
    return out & set(range(lo, hi + 1))


class _CronMatcher:
    """``matches(datetime) -> bool`` for a 5-field cron expression.

    Fields: minute (0-59) hour (0-23) day-of-month (1-31) month (1-12)
            day-of-week (0-6, Sun=0).
    """

    def __init__(self, expr: str):
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"cron must have 5 fields, got {len(parts)}: {expr!r}")
        self.expr = expr
        self.minute = _parse_cron_field(parts[0], 0, 59)
        self.hour = _parse_cron_field(parts[1], 0, 23)
        self.dom = _parse_cron_field(parts[2], 1, 31)
        self.mon = _parse_cron_field(parts[3], 1, 12)
        self.dow = _parse_cron_field(parts[4], 0, 6)

    def matches(self, dt: datetime) -> bool:
        # weekday: Monday=0 in datetime but Sunday=0 in cron-classic.
        dow = (dt.weekday() + 1) % 7
        return (dt.minute in self.minute
                and dt.hour in self.hour
                and dt.day in self.dom
                and dt.month in self.mon
                and dow in self.dow)


_WD_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _cron_humanise(expr: str) -> str:
    """Best-effort prose for a cron expression."""
    try:
        parts = expr.strip().split()
        if len(parts) != 5:
            return f"({expr})"
        mi, hr, dom, mon, dow = parts
        if mi.isdigit() and hr.isdigit() and dom == "*" and mon == "*":
            t = f"{int(hr):02d}:{int(mi):02d}"
            if dow == "*":
                return f"at {t}"
            if dow == "1-5":
                return f"weekdays at {t}"
            if dow.isdigit():
                return f"every {_WD_NAMES[int(dow)]} at {t}"
        return f"({expr})"
    except Exception:
        return f"({expr})"


# ── {prev} / {var.NAME} / {i} substitution ────────────────────────── #

import re as _re

_SUB_RE = _re.compile(r"\{(prev|var\.[^{}\s]+|i)\}")

# Keys whose values hold NESTED action lists. Their contents must NOT be
# substituted at the outer-action dispatch — substitution happens later,
# per-sub-action, so each iteration of a `repeat` sees its own `{i}` and
# the post-`set_var` `{var.NAME}` reflects the freshly bound value.
_NESTED_ACTION_KEYS = frozenset({"then", "else", "actions"})


def _substitute(params: Any, ctx: dict) -> Any:
    """Recursively walk ``params`` replacing ``{prev}``, ``{var.X}``, and
    ``{i}`` tokens in any string value.

    Non-string values pass through unchanged. Lists/dicts recurse. Keys
    in ``_NESTED_ACTION_KEYS`` are passed through RAW so the inner
    executor can substitute them per sub-action.
    """
    if isinstance(params, str):
        def _repl(m: "_re.Match") -> str:
            tok = m.group(1)
            if tok == "prev":
                return str(ctx.get("prev", ""))
            if tok == "i":
                return str(ctx.get("vars", {}).get("i", ""))
            if tok.startswith("var."):
                key = tok[4:]
                return str(ctx.get("vars", {}).get(key, ""))
            return m.group(0)
        return _SUB_RE.sub(_repl, params)
    if isinstance(params, list):
        return [_substitute(x, ctx) for x in params]
    if isinstance(params, dict):
        return {
            k: (v if k in _NESTED_ACTION_KEYS else _substitute(v, ctx))
            for k, v in params.items()
        }
    return params


# ── Condition evaluation for the ``if`` action ────────────────────── #

def _evaluate_condition(cond: dict) -> bool:
    """Return True/False for one ``if`` condition spec.

    Supported types:
      battery_above   {percent: N}
      battery_below   {percent: N}
      workspace_is    {profile: "CODING"|"MEETING"|...}
      time_between    {start: "HH:MM", end: "HH:MM"}   (24-hour clock,
                      handles ranges that wrap midnight)
      idle_more_than  {seconds: N}
      random          {chance: 0.25}                   (0..1)
    """
    t = str(cond.get("type") or "").lower()

    if t in ("battery_above", "battery_below"):
        try:
            from core.power_state import get_monitor
            snap = get_monitor().snapshot()
            pct = int(snap.percent)
        except Exception:
            return False
        try:
            thresh = int(cond.get("percent", 0))
        except Exception:
            return False
        return pct > thresh if t == "battery_above" else pct < thresh

    if t == "workspace_is":
        try:
            from core.workspace_profile import get_monitor
            cur = get_monitor().snapshot().profile.upper()
        except Exception:
            return False
        return cur == str(cond.get("profile", "")).upper()

    if t == "time_between":
        from datetime import datetime as _dt
        try:
            sh, sm = [int(x) for x in str(cond.get("start", "0:0")).split(":")]
            eh, em = [int(x) for x in str(cond.get("end", "0:0")).split(":")]
        except Exception:
            return False
        now = _dt.now()
        cur_minute = now.hour * 60 + now.minute
        start_minute = sh * 60 + sm
        end_minute = eh * 60 + em
        if start_minute <= end_minute:
            return start_minute <= cur_minute <= end_minute
        # Range wraps midnight (e.g. start=22:00 end=06:00)
        return cur_minute >= start_minute or cur_minute <= end_minute

    if t == "idle_more_than":
        try:
            from core.power_state import get_monitor
            snap = get_monitor().snapshot()
            idle_s = int(snap.idle_s)
        except Exception:
            return False
        try:
            thresh = int(cond.get("seconds", 0))
        except Exception:
            return False
        return idle_s > thresh

    if t == "random":
        try:
            chance = float(cond.get("chance", 0))
        except Exception:
            return False
        import random as _r
        return _r.random() < chance

    log.warning("[automation] unknown condition type: %s", t)
    return False


# ── Engine ─────────────────────────────────────────────────────────── #

class AutomationEngine:
    """Singleton. Construct once via ``get_engine()``."""

    _ACTION_KINDS = ("notify", "open_app", "open_url",
                     "run_skill", "ai_prompt", "delay",
                     "if", "repeat", "set_var")

    def __init__(self, *, routines_path: str = _DEFAULT_ROUTINES_PATH,
                 poll_interval_s: float = 30.0):
        self._path = routines_path
        self._poll_s = max(5.0, poll_interval_s)
        self._lock = threading.RLock()
        self._routines: dict[str, Routine] = {}
        self._matchers: dict[str, _CronMatcher] = {}     # routine id → matcher
        self._last_minute_fired: dict[str, int] = {}     # routine id → minute key
        # Interval triggers: per-routine "next-fire monotonic timestamp".
        # First fire is delayed by one interval after start() so the user
        # isn't surprised by an immediate trigger on app launch.
        self._next_fire: dict[str, float] = {}
        self._stop = threading.Event()
        self._sched_thread: Optional[threading.Thread] = None
        self._pool = ThreadPoolExecutor(max_workers=4,
                                        thread_name_prefix="aeris-routine")
        self._running_ids: set[str] = set()
        # Battery-edge bookkeeping — fire-once when crossing a threshold.
        self._last_battery_pct: Optional[int] = None
        # Handlers wired by main_window for actions that need GUI/brain.
        self._ai_prompt_handler: Optional[Callable[[str], None]] = None
        self._notify_handler: Optional[Callable[[str, str], None]] = None
        # Subscriptions we need to clean up on stop().
        self._unsub: list[Callable[[], None]] = []
        # Load whatever's on disk (if any) right away so the engine is
        # interrogable before ``start()`` runs.
        self.reload()

    # ── handler wiring ──

    def register_ai_prompt_handler(self, fn: Callable[[str], None]) -> None:
        self._ai_prompt_handler = fn

    def register_notify_handler(self, fn: Callable[[str, str], None]) -> None:
        self._notify_handler = fn

    # ── persistence ──

    def reload(self) -> int:
        """Re-read routines from disk. Returns count loaded."""
        with self._lock:
            self._routines.clear()
            self._matchers.clear()
            self._last_minute_fired.clear()
            # Don't reset _next_fire — a routine that's already scheduled
            # to fire at T should still fire at T even after reload.
            now_mono = time.monotonic()
            data = self._read_file()
            for r_dict in data.get("routines", []):
                try:
                    r = Routine.from_dict(r_dict)
                    self._routines[r.id] = r
                    if r.trigger.kind == "time":
                        cron = r.trigger.params.get("cron")
                        if cron:
                            try:
                                self._matchers[r.id] = _CronMatcher(cron)
                            except Exception as e:
                                log.warning("[automation] bad cron in %s: %s", r.id, e)
                    elif r.trigger.kind == "interval":
                        # First fire = now + interval (NOT immediate).
                        try:
                            secs = max(60.0, float(r.trigger.params.get("seconds", 3600)))
                        except Exception:
                            secs = 3600.0
                        # Preserve existing schedule if we already had one;
                        # otherwise set the first deadline.
                        if r.id not in self._next_fire:
                            self._next_fire[r.id] = now_mono + secs
                except Exception as e:
                    log.warning("[automation] could not load routine %r: %s",
                                r_dict.get("id"), e)
            log.info("[automation] loaded %d routines from %s",
                     len(self._routines), self._path)
            return len(self._routines)

    def save(self) -> None:
        with self._lock:
            payload = {"routines": [r.to_dict() for r in self._routines.values()]}
        write_atomic_json(self._path, payload, indent=2)

    def _read_file(self) -> dict:
        if not os.path.exists(self._path):
            return {"routines": []}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f) or {"routines": []}
        except Exception as e:
            log.warning("[automation] cannot read %s (%s)", self._path, e)
            return {"routines": []}

    # ── inspection ──

    def list_routines(self) -> list[Routine]:
        with self._lock:
            return list(self._routines.values())

    def get_routine(self, rid: str) -> Optional[Routine]:
        with self._lock:
            return self._routines.get(rid)

    def find_by_name(self, query: str) -> Optional[Routine]:
        """Cheap fuzzy match — first routine whose name OR id contains query."""
        q = query.lower().strip()
        with self._lock:
            for r in self._routines.values():
                if q in r.name.lower() or q in r.id.lower():
                    return r
        return None

    # ── enable/disable ──

    def set_enabled(self, rid: str, enabled: bool) -> bool:
        with self._lock:
            r = self._routines.get(rid)
            if r is None:
                return False
            r.enabled = bool(enabled)
        self.save()
        return True

    # ── lifecycle ──

    def start(self) -> None:
        """Start the scheduler thread + subscribe to event-trigger sources."""
        with self._lock:
            if self._sched_thread and self._sched_thread.is_alive():
                return
            self._stop.clear()
            self._sched_thread = threading.Thread(
                target=self._sched_run, name="AutomationScheduler", daemon=True,
            )
            self._sched_thread.start()
            log.info("[automation] scheduler thread up (%.0fs poll)", self._poll_s)

        # Power events
        try:
            from core.power_state import get_monitor as _gp
            pm = _gp()
            self._unsub.append(pm.on_power_change(self._on_power_change))
        except Exception as e:
            log.debug("[automation] no power monitor: %s", e)

        # Workspace events
        try:
            from core.workspace_profile import get_monitor as _gw
            wm = _gw()
            self._unsub.append(wm.subscribe(self._on_workspace_change))
        except Exception as e:
            log.debug("[automation] no workspace monitor: %s", e)

        # Gesture events — gesture engine uses add_listener (no unsubscribe).
        try:
            from core.gesture_engine import get_gesture_engine
            get_gesture_engine().add_listener(self._on_gesture)
        except Exception as e:
            log.debug("[automation] no gesture engine: %s", e)

    def stop(self, *, timeout: float = 2.0) -> None:
        self._stop.set()
        for un in self._unsub:
            try: un()
            except Exception: pass
        self._unsub.clear()
        t = self._sched_thread
        if t and t.is_alive():
            t.join(timeout=timeout)
        try:
            self._pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    # ── trigger handlers ──

    def _on_power_change(self, on_battery: bool, percent: int, plugged: bool) -> None:
        last = self._last_battery_pct
        self._last_battery_pct = percent
        # Fire-on-edge so a sub-20% routine doesn't spam every poll.
        with self._lock:
            candidates = list(self._routines.values())
        for r in candidates:
            if not r.enabled:
                continue
            k = r.trigger.kind
            try:
                threshold = int(r.trigger.params.get("percent", 0))
            except Exception:
                continue
            if k == "battery_below":
                if last is not None and last > threshold and percent <= threshold:
                    self._fire(r, reason=f"battery dropped to {percent}%")
            elif k == "battery_above":
                if last is not None and last < threshold and percent >= threshold:
                    self._fire(r, reason=f"battery rose to {percent}%")

    def _on_workspace_change(self, profile: str, foreground: str) -> None:
        with self._lock:
            candidates = list(self._routines.values())
        for r in candidates:
            if r.enabled and r.trigger.kind == "workspace_enter":
                if r.trigger.params.get("profile", "").upper() == profile.upper():
                    self._fire(r, reason=f"workspace → {profile}")

    def _on_gesture(self, name: str) -> None:
        with self._lock:
            candidates = list(self._routines.values())
        for r in candidates:
            if r.enabled and r.trigger.kind == "gesture":
                if r.trigger.params.get("name", "") == name:
                    self._fire(r, reason=f"gesture {name}")

    # ── scheduler loop ──

    def _sched_run(self) -> None:
        # Light initial stagger so launch-time GIL churn doesn't fight us.
        if self._stop.wait(1.5):
            return
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("[automation] tick raised")
            if self._stop.wait(self._poll_s):
                return

    def _tick(self) -> None:
        now = datetime.now()
        now_mono = time.monotonic()
        # Minute-precision dedup key so we never fire the same routine
        # twice in the same minute even if the poll lands twice.
        minute_key = now.year * 10000 * 60 + now.month * 100000 + now.day * 1440 \
            + now.hour * 60 + now.minute
        with self._lock:
            time_routines = [(r, self._matchers.get(r.id))
                             for r in self._routines.values()
                             if r.enabled and r.trigger.kind == "time"]
            interval_routines = [r for r in self._routines.values()
                                 if r.enabled and r.trigger.kind == "interval"]
        # ── cron / time triggers ──
        for r, m in time_routines:
            if m is None:
                continue
            if not m.matches(now):
                continue
            if self._last_minute_fired.get(r.id) == minute_key:
                continue
            self._last_minute_fired[r.id] = minute_key
            self._fire(r, reason=f"cron {m.expr}")
        # ── interval triggers ──
        for r in interval_routines:
            try:
                secs = max(60.0, float(r.trigger.params.get("seconds", 3600)))
            except Exception:
                continue
            deadline = self._next_fire.get(r.id)
            if deadline is None:
                # Never scheduled — set deadline + skip first fire.
                self._next_fire[r.id] = now_mono + secs
                continue
            if now_mono >= deadline:
                self._next_fire[r.id] = now_mono + secs
                self._fire(r, reason=f"every {int(secs)}s")

    # ── fire / execute ──

    def run_routine(self, rid: str, *, reason: str = "manual") -> bool:
        """Public entry point for "run now" — bypasses enabled check."""
        r = self.get_routine(rid)
        if r is None:
            return False
        self._fire(r, reason=reason, force=True)
        return True

    def _fire(self, r: Routine, *, reason: str, force: bool = False) -> None:
        if not force and not r.enabled:
            return
        # Prevent concurrent runs of the same routine.
        with self._lock:
            if r.id in self._running_ids:
                log.info("[automation] %s already running — skipping", r.id)
                return
            self._running_ids.add(r.id)
        log.info("[automation] firing %s (%s)", r.id, reason)
        self._pool.submit(self._execute_routine, r, reason)

    def _execute_routine(self, r: Routine, reason: str) -> None:
        try:
            try:
                from core.log_setup import event as _log_event
                _log_event("routine_fire", routine=r.id, reason=reason,
                           actions=len(r.actions))
            except Exception:
                pass
            # Per-run context — actions can read/write via {prev} and
            # {var.NAME} substitution, or store explicitly via set_var.
            ctx: dict = {"prev": "", "vars": {}}
            self._exec_actions(r.actions, ctx, route_id=r.id)
            with self._lock:
                r.last_fired_ts = time.time()
                r.fire_count += 1
            try:
                self.save()
            except Exception:
                pass
        finally:
            with self._lock:
                self._running_ids.discard(r.id)

    def _exec_actions(self, actions: list, ctx: dict, *, route_id: str) -> None:
        """Walk a list of actions sequentially. ``ctx`` is shared with all
        nested calls (``if``/``repeat`` sub-actions see the same dict)
        so variables flow across nested boundaries.
        """
        for i, action in enumerate(actions):
            if self._stop.is_set():
                log.info("[automation] %s aborted mid-run (shutdown)", route_id)
                return
            try:
                self._exec_action(action, ctx)
            except Exception as e:
                log.warning("[automation] %s step %d (%s) raised: %s",
                            route_id, i, action.kind, e)
                # Continue — one bad step never aborts the whole routine.

    def _exec_action(self, a: Action, ctx: dict) -> None:
        if a.kind not in self._ACTION_KINDS:
            log.warning("[automation] unknown action kind: %s", a.kind)
            return
        handler = getattr(self, f"_action_{a.kind}", None)
        if handler is None:
            log.warning("[automation] no handler for %s", a.kind)
            return
        # Resolve {prev} and {var.X} substitutions in string-typed params
        # before handing off. Handlers don't need to think about it.
        params = _substitute(a.params, ctx)
        result = handler(params, ctx)
        # Every handler may return a string to bind into ctx["prev"] for
        # the NEXT action's substitution. None = leave prev untouched.
        if isinstance(result, str):
            ctx["prev"] = result

    # ── action handlers ──
    # All handlers take ``(params, ctx)``. Returning a non-None string
    # binds that value into ``ctx['prev']`` for the next action's
    # ``{prev}`` substitution. Returning None leaves prev unchanged.

    def _action_notify(self, p: dict, ctx: dict) -> None:
        title = str(p.get("title") or "AERIS")
        body = str(p.get("body") or "")
        if self._notify_handler:
            try:
                self._notify_handler(title, body)
                return
            except Exception as e:
                log.warning("[automation] notify handler raised: %s", e)
        log.info("[notify] %s — %s", title, body)

    def _action_open_app(self, p: dict, ctx: dict) -> None:
        value = str(p.get("value", "")).strip()
        if not value:
            return
        try:
            alias = {
                "vscode": "code", "vs code": "code",
                "browser": "chrome",
            }.get(value.lower(), value)
            subprocess.Popen(alias, shell=True, close_fds=True)
        except Exception as e:
            log.warning("[automation] open_app %s failed: %s", value, e)

    def _action_open_url(self, p: dict, ctx: dict) -> None:
        url = str(p.get("value", "")).strip()
        if not url:
            return
        try:
            webbrowser.open(url, new=2)
        except Exception as e:
            log.warning("[automation] open_url %s failed: %s", url, e)

    def _action_run_skill(self, p: dict, ctx: dict) -> Optional[str]:
        name = str(p.get("name") or "")
        if not name:
            return None
        slots = dict(p.get("slots") or {})
        try:
            from core.skill_registry import REGISTRY
            from core.skill_breaker import call as _call
        except Exception:
            return None
        s = REGISTRY.get(name)
        if s is None:
            log.warning("[automation] no skill named %s", name)
            return None
        res = _call(name, s.run, slots)
        if not res.ok:
            log.warning("[automation] skill %s failed: %s", name, res.error)
            return None
        # Bind the skill's reply into ctx['prev'] so the next action can
        # reference it via {prev} — this is the multi-step pipeline glue.
        return str(res.value or "")

    def _action_ai_prompt(self, p: dict, ctx: dict) -> None:
        text = str(p.get("value") or "").strip()
        if not text:
            return
        if self._ai_prompt_handler:
            try:
                self._ai_prompt_handler(text)
            except Exception as e:
                log.warning("[automation] ai_prompt handler raised: %s", e)
        else:
            log.info("[automation] ai_prompt queued (no handler): %s", text[:60])

    def _action_delay(self, p: dict, ctx: dict) -> None:
        try:
            seconds = float(p.get("seconds", 0))
        except Exception:
            return
        # Cap at 5 minutes so a typo can't lock a worker forever.
        time.sleep(max(0.0, min(seconds, 300.0)))

    # ── new control-flow actions ──

    def _action_if(self, p: dict, ctx: dict) -> None:
        """Conditional branching. ``params``:
            condition: {type: <name>, ...}
            then:      [actions]
            else:      [actions]    (optional)
        """
        cond = p.get("condition") or {}
        then_actions = p.get("then") or []
        else_actions = p.get("else") or []
        try:
            passed = _evaluate_condition(cond)
        except Exception as e:
            log.warning("[automation] if condition raised: %s", e)
            passed = False
        chosen = then_actions if passed else else_actions
        # The nested actions are still raw dicts at this point — convert
        # them via _action_from_dict so the executor sees Action instances.
        action_objs = [_action_from_dict(a) for a in chosen]
        self._exec_actions(action_objs, ctx, route_id="if-branch")

    def _action_repeat(self, p: dict, ctx: dict) -> None:
        """Repeat ``actions`` ``times`` times. ``times`` capped at 100
        so an off-by-one typo can't lock a worker.

        Each iteration exposes ``{i}`` (1-based) so notify titles like
        ``"Pomodoro {i}/4"`` work naturally.
        """
        try:
            times = max(1, min(100, int(p.get("times", 1))))
        except Exception:
            times = 1
        sub = [_action_from_dict(a) for a in (p.get("actions") or [])]
        for i in range(1, times + 1):
            if self._stop.is_set():
                return
            ctx["vars"]["i"] = i
            self._exec_actions(sub, ctx, route_id=f"repeat[{i}/{times}]")

    def _action_set_var(self, p: dict, ctx: dict) -> None:
        """Bind a string into ``ctx['vars'][name]`` so later actions can
        reference it as ``{var.name}``. Use ``value: "{prev}"`` to
        capture the previous action's result by name.
        """
        name = str(p.get("name") or "").strip()
        if not name:
            return
        ctx["vars"][name] = str(p.get("value", ""))


# ── Singleton ──────────────────────────────────────────────────────── #

_singleton: Optional[AutomationEngine] = None
_singleton_lock = threading.Lock()


def get_engine() -> AutomationEngine:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = AutomationEngine()
        return _singleton


# ── Smoke test ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    import tempfile
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Cron matcher sanity
    m = _CronMatcher("30 14 * * 1-5")
    from datetime import datetime as _dt
    print("Mon 14:30 matches:", m.matches(_dt(2026, 5, 18, 14, 30)))
    print("Sat 14:30 matches:", m.matches(_dt(2026, 5, 23, 14, 30)))

    # Engine on a TEMP path — NEVER touch real data/routines.json from
    # the smoke test or we clobber the user's curated routines.
    tmp = tempfile.NamedTemporaryFile(prefix="aeris_routines_", suffix=".json",
                                      delete=False)
    tmp.close()
    eng = AutomationEngine(routines_path=tmp.name)
    eng.register_notify_handler(lambda t, b: print(f"  [TOAST] {t} - {b}"))
    eng.register_ai_prompt_handler(lambda t: print(f"  [BRAIN <] {t}"))
    print(f"loaded {len(eng.list_routines())} routines (expected 0)")
    r = Routine(
        id="smoke", name="Smoke Test",
        trigger=Trigger(kind="manual"),
        actions=[
            Action(kind="notify", params={"title": "Hi", "body": "Smoke test"}),
            Action(kind="delay", params={"seconds": 0.3}),
            Action(kind="ai_prompt", params={"value": "say hello"}),
        ],
        enabled=True,
    )
    eng._routines[r.id] = r
    eng.start()
    eng.run_routine("smoke")
    time.sleep(1.5)
    eng.stop()
    try: os.unlink(tmp.name)
    except OSError: pass
