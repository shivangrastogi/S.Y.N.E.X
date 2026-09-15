"""Retire the brain child while nobody is talking to it, and bring it back
with the conversation intact (§4.2 "Still open" of the load-free doc).

In split mode the resting footprint is ~478 MB, essentially all of it torch +
spaCy + llama held by a child process that is doing nothing between turns. The
supervisor could already stop and restart that child; what stopped us was that
the child owns the only copy of the conversation. ``core/brain_snapshot.py``
solves that half. This module is the *policy* half:

    idle for N seconds  →  snapshot  →  stop the child      (~478 MB → ~20 MB)
    next utterance      →  start     →  restore  →  dispatch (~2 s under lite)

Rules this encodes, each of which is a decision rather than an obvious default:

* **Never hibernate a child we could not snapshot.** If the snapshot request
  fails while the child is still alive and answering, we stay resident and try
  again next tick. Losing the conversation is a worse outcome than holding the
  RAM a little longer, and it is the exact failure this whole feature exists to
  avoid. (A child that is already dead is different — there is nothing left to
  save and nothing to gain by keeping the corpse.)

* **Waking is single-flight.** Two GUI turns arriving together must not spawn
  two brains. The wake path holds a lock; the second caller waits for the first
  one's child.

* **The clock is injected.** Hibernation is a timing policy, and a timing
  policy tested with `sleep` is a slow, flaky test. ``maybe_hibernate()`` is a
  deterministic function of the injected clock, so the whole state machine is
  exercised in milliseconds.

* **A hibernated brain is silent.** The proactive ticker lives in the child, so
  it stops with it — no offers arrive while asleep. That is the honest tradeoff
  and the reason the flag defaults to off: hibernation trades AERIS's ability
  to speak first for the resting footprint of the machine.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

from core.brain_snapshot import is_empty

log = logging.getLogger(__name__)

AWAKE = "awake"
HIBERNATED = "hibernated"

ENV_IDLE = "AERIS_BRAIN_HIBERNATE_S"
DEFAULT_IDLE_S = 0.0            # off unless asked for — see the tradeoff above


def idle_window_from_env(environ: Optional[dict] = None) -> float:
    """Read ``AERIS_BRAIN_HIBERNATE_S``. ``0``/unset/garbage → disabled.

    Parsed here rather than at import so tests and the GUI settings panel can
    pass an environment in, matching how the other load-free flags are read.
    """
    raw = (environ if environ is not None else os.environ).get(ENV_IDLE, "")
    try:
        v = float(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_IDLE_S
    return v if v > 0 else DEFAULT_IDLE_S


class BrainHibernator:
    """Owns the awake/hibernated lifecycle of one brain proxy.

    ``proxy`` is anything with the ``ServiceProxy`` surface used here:
    ``start(ready_timeout)``, ``stop()``, ``is_ready()``, ``request(kind,
    payload, timeout)``. Injectable so the state machine is tested with a fake.
    """

    def __init__(self, proxy: Any, idle_s: float = 0.0,
                 clock: Callable[[], float] = time.monotonic,
                 ready_timeout: float = 120.0,
                 request_timeout: float = 15.0,
                 suspend: Optional[Callable[[], Any]] = None,
                 resume: Optional[Callable[[], Any]] = None):
        self._proxy = proxy
        self.idle_s = float(idle_s or 0.0)
        self._clock = clock
        self._ready_timeout = ready_timeout
        self._timeout = request_timeout
        # When a Supervisor is watching this proxy it must be told that the
        # stop is deliberate — otherwise its monitor restarts the child a
        # second later (undoing the hibernation) and burns the crash-loop
        # budget doing it. See Supervisor.suspend/resume.
        self._suspend = suspend
        self._resume = resume
        self._lock = threading.RLock()
        self._hb: Optional[threading.Thread] = None
        self._hb_stop: Optional[threading.Event] = None
        self.state = AWAKE
        self._last_activity = clock()
        self._snapshot: Optional[dict] = None
        # Observability — surfaced by `/subsystems` and the log panel.
        self.hibernations = 0
        self.wakes = 0
        self.restore_failures = 0
        self.last_restored: list = []

    # ── activity tracking ────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return self.idle_s > 0

    def note_activity(self) -> None:
        """Call on every turn. Resets the idle countdown."""
        self._last_activity = self._clock()

    def idle_for(self) -> float:
        return max(0.0, self._clock() - self._last_activity)

    # ── sleep ────────────────────────────────────────────────────────
    def maybe_hibernate(self) -> bool:
        """Retire the child if it has been idle past the window.

        Deterministic: give it a clock and it needs no wall time. Returns True
        only when a child was actually put to sleep this call.
        """
        if not self.enabled:
            return False
        with self._lock:
            if self.state != AWAKE:
                return False
            if self.idle_for() < self.idle_s:
                return False
            return self._hibernate_locked()

    def hibernate_now(self) -> bool:
        """Force a sleep regardless of the idle window (used by tests, and by
        an explicit 'brain so ja' / low-power request)."""
        with self._lock:
            if self.state != AWAKE:
                return False
            return self._hibernate_locked()

    def _hibernate_locked(self) -> bool:
        alive = False
        try:
            alive = bool(self._proxy.is_ready())
        except Exception:
            alive = False

        if alive:
            snap = self._request_snapshot()
            if snap is None:
                # Alive but wouldn't answer — see the module docstring: stay
                # resident rather than drop the conversation on the floor.
                log.info("[hibernator] snapshot failed; staying resident")
                return False
            self._snapshot = snap
        # A child that is already gone has nothing left to snapshot; keep
        # whatever we last captured and stop pretending it is running.

        # Suspend BEFORE the stop, never after: in between the two, a
        # supervisor monitor tick would see a dead child and resurrect it.
        self._call_hook(self._suspend, "suspend")
        try:
            self._proxy.stop()
        except Exception as e:
            log.warning("[hibernator] stop raised: %s", e)
        self.state = HIBERNATED
        self.hibernations += 1
        log.info("[hibernator] brain hibernated after %.0fs idle "
                 "(snapshot: %s)", self.idle_for(),
                 "empty" if is_empty(self._snapshot) else "carried")
        return True

    def _request_snapshot(self) -> Optional[dict]:
        try:
            r = self._proxy.request("snapshot", {}, timeout=self._timeout)
        except Exception as e:
            log.debug("[hibernator] snapshot request raised: %s", e)
            return None
        if not getattr(r, "ok", False):
            log.debug("[hibernator] snapshot error: %s", getattr(r, "error", ""))
            return None
        state = (getattr(r, "payload", None) or {}).get("state")
        # An older brain build that doesn't know "snapshot" answers with an
        # error, handled above. A brain that answers with nothing genuinely
        # has nothing to carry — that is a valid, empty snapshot.
        return state if isinstance(state, dict) else {}

    # ── wake ─────────────────────────────────────────────────────────
    def ensure_awake(self) -> bool:
        """Bring the brain back if it is asleep, restoring the conversation.

        Safe to call before every turn: a no-op (one attribute read) when the
        brain is already awake. Returns whether a usable brain is available.
        """
        if self.state == AWAKE:
            return True
        with self._lock:
            if self.state == AWAKE:      # another thread woke it while we waited
                return True
            ok = False
            try:
                ok = bool(self._proxy.start(ready_timeout=self._ready_timeout))
            except Exception as e:
                log.warning("[hibernator] wake failed: %s", e)
                return False
            if not ok:
                # Stay suspended on purpose. While hibernation is enabled the
                # hibernator owns this child's lifecycle across the sleep
                # boundary, so handing a half-started service back to the
                # supervisor here would give the process two owners racing to
                # spawn it. The next turn calls ensure_awake again and retries.
                log.warning("[hibernator] brain did not come back ready")
                return False
            self._call_hook(self._resume, "resume")
            self.state = AWAKE
            self.wakes += 1
            self.note_activity()
            self._push_snapshot_locked()
            return True

    @staticmethod
    def _call_hook(fn: Optional[Callable[[], Any]], what: str) -> None:
        if fn is None:
            return
        try:
            fn()
        except Exception as e:
            log.warning("[hibernator] %s hook raised: %s", what, e)

    def _push_snapshot_locked(self) -> None:
        snap = self._snapshot
        if is_empty(snap):
            return                       # nothing to say — skip the round-trip
        try:
            r = self._proxy.request("restore", {"state": snap},
                                    timeout=self._timeout)
        except Exception as e:
            self.restore_failures += 1
            log.warning("[hibernator] restore request raised: %s", e)
            return
        if not getattr(r, "ok", False):
            self.restore_failures += 1
            log.warning("[hibernator] restore rejected: %s",
                        getattr(r, "error", ""))
            return
        self.last_restored = (getattr(r, "payload", None) or {}).get("restored") or []
        log.info("[hibernator] conversation restored: %s",
                 ", ".join(self.last_restored) or "nothing")

    # ── heartbeat ────────────────────────────────────────────────────
    # A REPL blocks in `input()` and a GUI blocks in the Qt loop, so neither
    # notices the idle window passing on its own — something has to tick.
    # Kept here rather than in each surface so the driver and the GUI get the
    # same policy, and so `maybe_hibernate` stays a pure, clock-injected
    # function that tests drive directly without any thread at all.
    def start_heartbeat(self, interval: Optional[float] = None) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if getattr(self, "_hb", None) is not None:
                return False
            self._hb_stop = threading.Event()
            # Check often enough that the window is honoured to the quarter,
            # rarely enough to be free: a bounded, cheap attribute compare.
            every = interval or max(5.0, min(30.0, self.idle_s / 4.0))

            def _run():
                while not self._hb_stop.wait(every):
                    try:
                        self.maybe_hibernate()
                    except Exception as e:  # pragma: no cover - defensive
                        log.debug("[hibernator] heartbeat tick raised: %s", e)

            self._hb = threading.Thread(target=_run, name="brain-hibernator",
                                        daemon=True)
            self._hb.start()
            return True

    def stop_heartbeat(self) -> None:
        with self._lock:
            hb, self._hb = getattr(self, "_hb", None), None
            stop = getattr(self, "_hb_stop", None)
        if stop is not None:
            stop.set()
        if hb is not None:
            hb.join(2.0)

    # ── introspection ────────────────────────────────────────────────
    def status(self) -> dict:
        return {"state": self.state,
                "enabled": self.enabled,
                "idle_s": round(self.idle_for(), 1),
                "window_s": self.idle_s,
                "hibernations": self.hibernations,
                "wakes": self.wakes,
                "restore_failures": self.restore_failures,
                "last_restored": list(self.last_restored)}
