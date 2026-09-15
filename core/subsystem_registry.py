"""In-process subsystem supervision — boot stages that degrade, not die.

The gap this closes
-------------------
``core/service_supervisor.py`` supervises subsystems that live in their own
**processes** (brain, and eventually voice/vision). But most of AERIS's
subsystems are still in-process objects installed on the GUI thread during
staged boot: the tray icon, the global hotkey, the health server, the
workspace monitor, the skill watcher, semantic memory, the cloud bridge, the
voice stack.

Those installs were already wrapped in ``try/except`` — so one broken
subsystem never killed boot — but that is only half of P0. The other half was
missing:

  * **Nobody remembered.** The exception was logged once and dropped. There
    was no way to ask "is the tray up?" — not from the UI, not from
    ``/health``, not from a bug report.
  * **Nothing ever came back.** A subsystem that lost a race at boot (mic
    busy, port 8765 still held by the previous run, network down for the
    bridge) stayed dead for the whole session. The only cure was restarting
    AERIS.

This module is the in-process analogue of the process supervisor: a registry
that runs each install fault-isolated, *remembers the outcome*, and can bring
a failed subsystem back with backoff.

The OS concept
--------------
This is ``init``'s job description, scoped to one process. A service manager
does four things — start, isolate, observe, restart — and the interesting one
is the fourth. Restarting blindly is how you get a crash loop that burns a
CPU core on a subsystem that will never work (a laptop with no camera will
*never* grow one). So retries are:

  * **bounded** — ``max_retries`` per subsystem, then FAILED and left alone;
  * **backed off** — the delay doubles each attempt, capped, so a dead
    subsystem costs geometrically less over a long session;
  * **pulled, not pushed** — this module owns no thread and no timer. The
    caller asks ``due_for_retry()`` from a tick it already has (the GUI's
    idle timer, the standby daemon's sweep). A registry that spawned its own
    thread would be one more thing to crash, and would need a lock discipline
    against the Qt main thread that nothing here wants.

Degraded is a real state, not a synonym for failed
--------------------------------------------------
A subsystem that installed fine and later broke (voice lost the mic, bridge
lost the network) is DEGRADED, not FAILED: it has a live object, it just is
not working right now. That distinction is what lets the UI say "voice is
reconnecting" instead of "voice is dead", and it is why reconnect is a
separate verb from boot — reconnect tears the old object down first.

Thread-safety
-------------
One ``RLock`` guards the whole record table. Installs run **outside** the lock
(they can take seconds — the health server binds a socket, semantic memory
touches disk) so a slow install never blocks a status read from the health
server's thread. Re-entrant because ``reconnect`` calls ``boot`` internally.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

log = logging.getLogger(__name__)


# ── Tunables ───────────────────────────────────────────────────────── #

_DEFAULT_BACKOFF_S = 5.0      # first retry waits this long
_BACKOFF_FACTOR = 2.0         # then doubles
_MAX_BACKOFF_S = 300.0        # capped at 5 min — a dead subsystem is cheap
_ERR_SNIPPET = 300            # chars of the error we keep for the UI


class SubsystemState(str, Enum):
    """Lifecycle of one in-process subsystem.

    ``str`` mixin so a snapshot is JSON-serialisable without a custom
    encoder — the health server dumps these straight to the wire.
    """
    PENDING = "pending"      # registered, never attempted
    OK = "ok"                # installed and believed healthy
    DEGRADED = "degraded"    # was OK, broke at runtime; reconnect pending
    RETRYING = "retrying"    # install failed, attempts remain
    FAILED = "failed"        # out of attempts — left alone deliberately
    DISABLED = "disabled"    # switched off by config/user, not a fault


#: States a subsystem can be dragged back from.
_RECOVERABLE = (SubsystemState.DEGRADED, SubsystemState.RETRYING)


class SubsystemUnavailable(Exception):
    """Raise from an install to say "not a fault — I cannot run here."

    The third category, and the one a plain ``try/except`` cannot express.
    An install has three possible bad outcomes, not two:

      * it lost a **race** — port busy, mic held, network blipped. Retry.
      * it **broke** — a bug, a missing DLL, a corrupt file. Fail loudly.
      * the **precondition is absent** — no service-account key, not paired
        yet, the feature is switched off. Retrying cannot help, and shouting
        about it is noise: nothing is wrong, the user just has not set it up.

    Raising this lands the subsystem in DISABLED with the reason attached, so
    it is skipped by retries, excluded from ``critical_down``, and reported as
    "off" rather than "broken". ``enable()`` + ``boot()`` picks it back up
    once the precondition is met (the user pairs their phone, plugs in a mic).
    """


@dataclass
class SubsystemRecord:
    """Everything we know about one subsystem. Pure data — no behaviour."""
    name: str
    install: Callable[[], object] = field(repr=False)
    teardown: Optional[Callable[[], None]] = field(default=None, repr=False)
    critical: bool = False
    max_retries: int = 0
    backoff_s: float = _DEFAULT_BACKOFF_S

    state: SubsystemState = SubsystemState.PENDING
    attempts: int = 0
    install_ms: float = 0.0
    last_error: str = ""
    last_traceback: str = field(default="", repr=False)
    ready_at: float = 0.0
    last_attempt_at: float = 0.0
    next_retry_at: float = 0.0

    @property
    def healthy(self) -> bool:
        return self.state is SubsystemState.OK

    @property
    def retries_left(self) -> int:
        # ``attempts`` counts the first install too, so the budget is
        # ``max_retries`` *after* that first try. The inner clamp matters for
        # attempts == 0 (never tried, or rewound by SubsystemUnavailable):
        # without it the budget reads one higher than it is.
        return max(0, self.max_retries - max(0, self.attempts - 1))

    def as_dict(self) -> dict:
        """JSON-safe view for ``/health`` and the UI. Drops the callables and
        the full traceback (that stays in the log, not on the wire)."""
        return {
            "name": self.name,
            "state": self.state.value,
            "critical": self.critical,
            "attempts": self.attempts,
            "retries_left": self.retries_left,
            "install_ms": round(self.install_ms, 1),
            "last_error": self.last_error,
            "ready_at": self.ready_at,
            "next_retry_at": self.next_retry_at,
        }


class SubsystemRegistry:
    """Register subsystems, boot them fault-isolated, remember, retry.

    Typical use from a staged boot::

        reg = SubsystemRegistry()
        reg.register("tray", self._install_tray, max_retries=0)
        reg.register("health server", self._install_health, max_retries=3)
        for name in reg.names():
            reg.boot(name)          # never raises

    and later, from any tick the caller already owns::

        reg.retry_due()
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        # Injectable clock so tests can drive backoff without sleeping.
        self._clock = clock
        self._lock = threading.RLock()
        self._records: dict[str, SubsystemRecord] = {}
        self._order: list[str] = []

    # ── registration ─────────────────────────────────────────────── #

    def register(
        self,
        name: str,
        install: Callable[[], object],
        *,
        teardown: Optional[Callable[[], None]] = None,
        critical: bool = False,
        max_retries: int = 0,
        backoff_s: float = _DEFAULT_BACKOFF_S,
    ) -> SubsystemRecord:
        """Add a subsystem. Re-registering a name replaces its callables but
        **keeps its history** — a hot-reload should not erase the fact that
        this thing has failed four times.

        ``max_retries=0`` (the default) means one attempt, no retry: right for
        things that either work or genuinely cannot on this machine (tray,
        hotkey). Give retries to anything whose failure is a *race* rather
        than an absence — port binds, mics, sockets.
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None:
                rec = SubsystemRecord(name=name, install=install)
                self._records[name] = rec
                self._order.append(name)
            rec.install = install
            rec.teardown = teardown
            rec.critical = critical
            rec.max_retries = max_retries
            rec.backoff_s = backoff_s
            return rec

    def names(self) -> list[str]:
        """Registration order — boot order is the caller's to choose, and
        insertion order is the one they meant."""
        with self._lock:
            return list(self._order)

    def get(self, name: str) -> Optional[SubsystemRecord]:
        with self._lock:
            return self._records.get(name)

    # ── running ──────────────────────────────────────────────────── #

    def boot(self, name: str) -> bool:
        """Run one subsystem's install, fault-isolated. Never raises.

        Returns True if it is now OK. An unknown name returns False (the
        caller is mid-refactor; that is a bug worth logging, not crashing).
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None:
                log.warning("[subsystems] boot of unregistered '%s'", name)
                return False
            if rec.state is SubsystemState.DISABLED:
                return False
            install = rec.install
            rec.attempts += 1
            rec.last_attempt_at = self._clock()
            attempt_no = rec.attempts

        # Outside the lock: installs bind sockets and touch disk.
        t0 = time.perf_counter()
        try:
            install()
        except SubsystemUnavailable as e:
            # Precondition absent, not a fault — DISABLED, no retry, no
            # ERROR-level noise. Rewind the attempt so the retry budget is
            # intact for when the precondition is met.
            with self._lock:
                rec = self._records[name]
                rec.attempts = max(0, rec.attempts - 1)
                rec.install_ms = (time.perf_counter() - t0) * 1000
            self.mark_disabled(name, str(e) or "unavailable")
            return False
        except Exception as e:
            self._record_failure(name, e, (time.perf_counter() - t0) * 1000)
            return False

        elapsed = (time.perf_counter() - t0) * 1000
        with self._lock:
            rec = self._records[name]
            rec.state = SubsystemState.OK
            rec.install_ms = elapsed
            rec.ready_at = self._clock()
            rec.last_error = ""
            rec.last_traceback = ""
            rec.next_retry_at = 0.0
        if attempt_no > 1:
            log.info("[subsystems] '%s' RECOVERED after %d attempts (%.0f ms)",
                     name, attempt_no, elapsed)
        else:
            log.info("[subsystems] '%s' ok in %.0f ms", name, elapsed)
        return True

    def _record_failure(self, name: str, exc: BaseException,
                        elapsed_ms: float) -> None:
        """Log loudly, schedule the next attempt (or give up)."""
        with self._lock:
            rec = self._records[name]
            rec.install_ms = elapsed_ms
            rec.last_error = f"{type(exc).__name__}: {exc}"[:_ERR_SNIPPET]
            rec.last_traceback = traceback.format_exc()
            if rec.retries_left > 0:
                rec.state = SubsystemState.RETRYING
                rec.next_retry_at = self._clock() + self._backoff_for(rec)
            else:
                rec.state = SubsystemState.FAILED
                rec.next_retry_at = 0.0
            state, err, left = rec.state, rec.last_error, rec.retries_left
            critical, tb = rec.critical, rec.last_traceback

        # "Logs loudly": critical failures are ERROR, the rest WARNING, and
        # the traceback goes to DEBUG so a support log has it without every
        # boot printing a wall of stack.
        emit = log.error if critical else log.warning
        emit("[subsystems] '%s' %s — %s (%d retr%s left)",
             name, state.value.upper(), err, left,
             "y" if left == 1 else "ies")
        log.debug("[subsystems] '%s' traceback:\n%s", name, tb)

    def _backoff_for(self, rec: SubsystemRecord) -> float:
        """Exponential in attempts already made, capped. Caller holds the
        lock."""
        return min(
            rec.backoff_s * (_BACKOFF_FACTOR ** max(0, rec.attempts - 1)),
            _MAX_BACKOFF_S,
        )

    def boot_all(self) -> dict[str, bool]:
        """Boot every registered subsystem in registration order.

        Convenience for headless entry points (``run_split.py``, the standby
        daemon). The GUI does *not* use this — it boots one per timer tick so
        first paint is never blocked.
        """
        return {name: self.boot(name) for name in self.names()}

    # ── runtime health transitions ───────────────────────────────── #

    def mark_degraded(self, name: str, reason: str) -> None:
        """A subsystem that installed fine has stopped working.

        This is the hook for error signals that arrive *after* boot — the
        voice stack's ``error`` signal, the bridge's disconnect callback. It
        schedules a reconnect if the subsystem has budget for one.
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None or rec.state is SubsystemState.DISABLED:
                return
            rec.last_error = str(reason)[:_ERR_SNIPPET]
            rec.state = SubsystemState.DEGRADED
            rec.next_retry_at = (
                self._clock() + self._backoff_for(rec)
                if rec.retries_left > 0 else 0.0
            )
            left = rec.retries_left
        log.warning("[subsystems] '%s' DEGRADED — %s (%d reconnect%s left)",
                    name, reason, left, "" if left == 1 else "s")

    def mark_disabled(self, name: str, reason: str = "") -> None:
        """Switched off on purpose (privacy mode, a settings toggle).

        Distinct from FAILED so the UI never shows "voice failed" when the
        user simply turned the mic off, and so retries never fight the user.
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None:
                return
            rec.state = SubsystemState.DISABLED
            rec.last_error = reason
            rec.next_retry_at = 0.0
        log.info("[subsystems] '%s' disabled%s", name,
                 f" — {reason}" if reason else "")

    def enable(self, name: str) -> None:
        """Undo ``mark_disabled``; leaves it PENDING for the next boot."""
        with self._lock:
            rec = self._records.get(name)
            if rec is None or rec.state is not SubsystemState.DISABLED:
                return
            rec.state = SubsystemState.PENDING
            rec.last_error = ""
            rec.next_retry_at = 0.0

    # ── retry / reconnect ────────────────────────────────────────── #

    def due_for_retry(self) -> list[str]:
        """Names whose backoff has elapsed and that still have budget.

        Pull-based on purpose — see the module docstring. Safe to call every
        tick; it is a dict scan under a lock, nothing more.
        """
        now = self._clock()
        with self._lock:
            return [
                r.name for r in self._records.values()
                if r.state in _RECOVERABLE
                and r.retries_left > 0
                and 0 < r.next_retry_at <= now
            ]

    def reconnect(self, name: str) -> bool:
        """Tear down then re-install. The verb for a DEGRADED subsystem.

        A failing teardown is logged and ignored — we are already in the
        error path, and refusing to re-install because cleanup was messy is
        how a recoverable subsystem stays dead.
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None or rec.state is SubsystemState.DISABLED:
                return False
            teardown = rec.teardown
        if teardown is not None:
            try:
                teardown()
            except Exception as e:
                log.warning("[subsystems] '%s' teardown failed (ignored): %s",
                            name, e)
        log.info("[subsystems] reconnecting '%s'", name)
        return self.boot(name)

    def retry_due(self) -> dict[str, bool]:
        """Reconnect everything currently due. Returns name → recovered.

        This is the one call a caller's idle tick needs.
        """
        return {name: self.reconnect(name) for name in self.due_for_retry()}

    def reset(self, name: str) -> None:
        """Clear a FAILED subsystem's history so the user can retry by hand
        from a debug menu — the manual override on the bounded-retry policy.
        """
        with self._lock:
            rec = self._records.get(name)
            if rec is None:
                return
            rec.state = SubsystemState.PENDING
            rec.attempts = 0
            rec.last_error = ""
            rec.last_traceback = ""
            rec.next_retry_at = 0.0

    # ── observation ──────────────────────────────────────────────── #

    def snapshot(self) -> dict:
        """JSON-safe health view: per-subsystem records plus a roll-up."""
        with self._lock:
            recs = [self._records[n].as_dict() for n in self._order]
            failed = [r["name"] for r in recs if r["state"] == "failed"]
            degraded = [r["name"] for r in recs
                        if r["state"] in ("degraded", "retrying")]
            crit_down = [
                n for n in self._order
                if self._records[n].critical
                and not self._records[n].healthy
                and self._records[n].state is not SubsystemState.DISABLED
            ]
        return {
            # "ok" means nothing is down *right now*. A RETRYING subsystem
            # counts as down even though it may recover in 10 s — it is not
            # installed, and a monitor that saw ok=true next to a non-empty
            # `down` list would rightly not trust either field. DISABLED is
            # not down: the user turned it off.
            "ok": not failed and not degraded and not crit_down,
            "total": len(recs),
            "healthy": sum(1 for r in recs if r["state"] == "ok"),
            "failed": failed,
            "degraded": degraded,
            "critical_down": crit_down,
            "subsystems": recs,
        }

    def summary_line(self) -> str:
        """One line for the boot log and the UI's status strip."""
        s = self.snapshot()
        line = f"{s['healthy']}/{s['total']} subsystems up"
        if s["degraded"]:
            line += f" · reconnecting: {', '.join(s['degraded'])}"
        if s["failed"]:
            line += f" · down: {', '.join(s['failed'])}"
        return line


# ── Process-wide default ───────────────────────────────────────────── #
#
# The health server, the UI status strip and the staged boot all need the
# same registry, and threading it through three constructors buys nothing —
# there is exactly one GUI process. Same pattern as ``get_bridge()``.

_DEFAULT: Optional[SubsystemRegistry] = None
_DEFAULT_LOCK = threading.Lock()


def get_registry() -> SubsystemRegistry:
    """The process-wide registry (created on first use)."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = SubsystemRegistry()
        return _DEFAULT


def reset_registry() -> None:
    """Drop the process-wide registry — tests only."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        _DEFAULT = None
