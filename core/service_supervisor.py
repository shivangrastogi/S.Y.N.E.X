"""Service supervisor — spawns, health-checks and auto-restarts services
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1).

Sits above ``core.service_bus.ServiceProxy``: register named services, start
them all, and a background monitor restarts any that die — with a crash-loop
guard so a service that keeps dying is marked ``failed`` instead of thrashing.
This is what makes the split architecture *resilient*: the Brain service can
segfault and the app keeps running (GUI shows "brain reconnecting…"), the
supervisor brings it back.

Deterministic-by-design: the health check is a single ``_check_once()`` that
the monitor thread calls on an interval AND tests can call directly, so restart
behaviour is unit-tested without sleeping on real threads.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.service_bus import Msg, ServiceProxy

log = logging.getLogger(__name__)

READY = "ready"
DEAD = "dead"
FAILED = "failed"       # exceeded the crash-loop cap → give up auto-restart
SUSPENDED = "suspended"  # deliberately stopped (hibernated) — not a failure


@dataclass
class _Entry:
    proxy: ServiceProxy
    factory: Callable[[], Callable[[str, dict], dict]]
    auto_restart: bool = True
    restarts: list = field(default_factory=list)   # monotonic timestamps
    failed: bool = False
    suspended: bool = False


class Supervisor:
    def __init__(self, poll_interval: float = 1.0, max_restarts: int = 5,
                 restart_window_s: float = 60.0,
                 now_fn: Callable[[], float] = time.monotonic):
        self._svcs: dict[str, _Entry] = {}
        self._poll = poll_interval
        self._max_restarts = max_restarts
        self._window = restart_window_s
        self._now = now_fn
        self._lock = threading.RLock()
        self._mon: Optional[threading.Thread] = None
        self._stop_mon = threading.Event()

    # ── registration / lifecycle ─────────────────────────────────────
    def register(self, name: str, factory, auto_restart: bool = True) -> None:
        with self._lock:
            self._svcs[name] = _Entry(ServiceProxy(name, factory), factory,
                                      auto_restart)

    def start_all(self, ready_timeout: float = 30.0) -> dict[str, bool]:
        out = {}
        with self._lock:
            entries = list(self._svcs.items())
        for name, e in entries:
            out[name] = e.proxy.start(ready_timeout=ready_timeout)
            if not out[name]:
                self._record_restart(e)
        return out

    def stop_all(self, timeout: float = 3.0) -> None:
        self.stop_monitor()
        with self._lock:
            entries = list(self._svcs.values())
        for e in entries:
            try:
                e.proxy.stop(timeout=timeout)
            except Exception:
                pass

    # ── suspend / resume ─────────────────────────────────────────────
    # "Down" and "deliberately retired" are different states, and the monitor
    # must not confuse them. The idle-brain hibernator (§4.2) stops the child on
    # purpose; without this the monitor would see a dead process, restart it a
    # second later — undoing the hibernation — and count each sleep/wake cycle
    # toward the crash-loop cap until the brain was marked FAILED for good.
    #
    # Suspending hands lifecycle ownership of that service to whoever suspended
    # it, until they resume. Restart accounting is untouched: a deliberate stop
    # is not a crash, and must not spend the crash budget of a real one.
    def suspend(self, name: str) -> bool:
        with self._lock:
            e = self._svcs.get(name)
            if e is None or e.suspended:
                return False
            e.suspended = True
        log.info("[supervisor] %s suspended (auto-restart paused)", name)
        return True

    def resume(self, name: str) -> bool:
        with self._lock:
            e = self._svcs.get(name)
            if e is None or not e.suspended:
                return False
            e.suspended = False
        log.info("[supervisor] %s resumed", name)
        return True

    def is_suspended(self, name: str) -> bool:
        with self._lock:
            e = self._svcs.get(name)
        return bool(e is not None and e.suspended)

    # ── health + restart ─────────────────────────────────────────────
    def _record_restart(self, e: _Entry) -> None:
        now = self._now()
        e.restarts = [t for t in e.restarts if now - t <= self._window]
        e.restarts.append(now)
        if len(e.restarts) > self._max_restarts:
            e.failed = True
            log.warning("[supervisor] %s exceeded %d restarts in %.0fs → FAILED",
                        e.proxy.name, self._max_restarts, self._window)

    def _check_once(self, ready_timeout: float = 30.0) -> None:
        """Restart any dead, auto-restart, not-failed service. One pass."""
        with self._lock:
            entries = list(self._svcs.values())
        for e in entries:
            if e.failed or e.suspended or not e.auto_restart:
                continue
            if not e.proxy.is_alive():
                log.info("[supervisor] %s is down → restarting", e.proxy.name)
                self._record_restart(e)
                if not e.failed:
                    try:
                        e.proxy.start(ready_timeout=ready_timeout)
                    except Exception as ex:
                        log.warning("[supervisor] %s restart raised: %s",
                                    e.proxy.name, ex)

    def health(self) -> dict[str, str]:
        with self._lock:
            entries = list(self._svcs.items())
        out = {}
        for name, e in entries:
            if e.failed:
                out[name] = FAILED
            elif e.suspended:
                out[name] = SUSPENDED
            elif e.proxy.is_ready():
                out[name] = READY
            else:
                out[name] = DEAD
        return out

    # ── background monitor ───────────────────────────────────────────
    def start_monitor(self) -> None:
        if self._mon is not None and self._mon.is_alive():
            return
        self._stop_mon.clear()

        def _run():
            while not self._stop_mon.wait(self._poll):
                try:
                    self._check_once()
                except Exception as ex:  # pragma: no cover - defensive
                    log.debug("[supervisor] monitor tick raised: %s", ex)

        self._mon = threading.Thread(target=_run, name="svc-supervisor",
                                     daemon=True)
        self._mon.start()

    def stop_monitor(self) -> None:
        self._stop_mon.set()
        if self._mon is not None:
            self._mon.join(2.0)
            self._mon = None

    # ── request routing / events ─────────────────────────────────────
    def request(self, service: str, kind: str, payload: Optional[dict] = None,
                timeout: float = 10.0) -> Msg:
        with self._lock:
            e = self._svcs.get(service)
        if e is None:
            raise KeyError(f"no service named {service!r}")
        return e.proxy.request(kind, payload, timeout=timeout)

    def poll_events(self) -> list[Msg]:
        with self._lock:
            entries = list(self._svcs.items())
        out: list[Msg] = []
        for name, e in entries:
            for m in e.proxy.poll_events():
                m.payload = dict(m.payload or {})
                m.payload.setdefault("_service", name)
                out.append(m)
        return out
