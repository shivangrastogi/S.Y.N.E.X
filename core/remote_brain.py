"""RemoteBrain — the GUI-side seam to the brain running in its own process
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1).

Exposes the same ``process_text(text) -> reply`` surface the GUI already calls
on ``JarvisMainEngine``, but forwards it over the service bus to the child
``brain_service``. So switching the GUI to the isolated brain is (mostly) a
one-line swap: build a ``RemoteBrain`` instead of a ``JarvisMainEngine``.

Crucially it **degrades instead of dying**: if the brain child is not ready,
times out, or has crashed, ``process_text`` returns a friendly "reconnecting…"
line and asks the supervisor/proxy to restart — the GUI never hangs and never
inherits a native crash (torch lives only in the child).

The proxy is injectable so the adapter is unit-tested with a fake (no spawn);
the real path builds a ``ServiceProxy`` over ``brain_handler_factory``.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

_NOT_READY = "Dimaag abhi load ho raha hai — ek pal ruk jao, sir."
_RECONNECT = "Dimaag reconnect ho raha hai — dobara bol do."
_ERROR = "Sorry, us request me kuch gadbad ho gayi."


def extract_offers(events) -> list:
    """Pick the surfaceable proactive offers out of raw bus events.

    Returns ``[(text, payload), ...]``. An event qualifies when its kind is
    ``event:offer`` (the bus prefixes whatever `brain_service` emits) and its
    payload carries non-empty text — an offer with nothing to say is not
    something to put in front of the user.

    Tolerant by design: this consumes messages produced by a *separate
    process* that may be a different build, so anything malformed is skipped
    rather than raised. Kept module-level and Qt-free so the GUI's poller can
    be tested without standing up a QApplication.
    """
    from core.bus_events import payloads
    out = []
    for payload in payloads(events, "offer"):
        text = (payload.get("text") or "").strip()
        if text:
            out.append((text, dict(payload)))
    return out


class RemoteBrain:
    def __init__(self, proxy: Any = None, request_timeout: float = 30.0,
                 auto_restart: bool = True,
                 hibernate_after_s: Optional[float] = None,
                 suspend: Optional[Any] = None,
                 resume: Optional[Any] = None):
        self._proxy = proxy
        self._timeout = request_timeout
        # When a Supervisor owns the proxy's lifecycle, set auto_restart=False
        # so we don't race the supervisor's own restart on a failed request.
        self._auto_restart = auto_restart
        # GUI reads this after each turn for its "which skill fired" chip.
        self.last_dispatch: Optional[dict] = None
        # Idle-retire the child and bring the conversation back with it
        # (§4.2). Off unless AERIS_BRAIN_HIBERNATE_S says otherwise; an
        # explicit argument wins so the GUI/tests can set it directly.
        from core.brain_hibernator import BrainHibernator, idle_window_from_env
        idle_s = (idle_window_from_env() if hibernate_after_s is None
                  else float(hibernate_after_s or 0.0))
        self._hib = BrainHibernator(proxy, idle_s=idle_s,
                                    suspend=suspend, resume=resume)

    def _ensure_proxy(self) -> None:
        if self._proxy is None:
            from core.service_bus import ServiceProxy
            from core.brain_service import brain_handler_factory
            self._proxy = ServiceProxy("brain", brain_handler_factory)
            self._hib._proxy = self._proxy

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self, ready_timeout: float = 240.0) -> bool:
        self._ensure_proxy()
        try:
            return bool(self._proxy.start(ready_timeout=ready_timeout))
        except Exception as e:
            log.warning("[remote_brain] start failed: %s", e)
            return False

    def is_ready(self) -> bool:
        return self._proxy is not None and self._proxy.is_ready()

    def stop(self) -> None:
        if self._proxy is not None:
            try:
                self._proxy.stop()
            except Exception:
                pass

    # ── the seam the GUI calls ───────────────────────────────────────
    def process_text(self, text: str) -> str:
        # Wake BEFORE the readiness check: a hibernated brain is deliberately
        # not-ready, and answering "dimaag load ho raha hai" to the very
        # utterance that should have woken it would make the feature look
        # broken. No-op (one attribute read) when hibernation is off.
        if not self._hib.ensure_awake():
            return _NOT_READY
        self._hib.note_activity()
        if not self.is_ready():
            return _NOT_READY
        try:
            r = self._proxy.request("utterance", {"text": text},
                                    timeout=self._timeout)
        except Exception as e:
            log.warning("[remote_brain] request failed (%s) → restarting", e)
            self._try_restart()
            return _RECONNECT
        if not getattr(r, "ok", False):
            log.debug("[remote_brain] brain error reply: %s", getattr(r, "error", ""))
            return _ERROR
        # Prefer the full dispatch (intent/confidence/action) so the GUI's
        # per-reply chip matches the in-process path; fall back to the
        # skill-only shape when an older brain only sends "skill".
        self.last_dispatch = r.payload.get("dispatch") or {"skill": r.payload.get("skill")}
        return r.payload.get("reply", "") or ""

    # ── hibernation (§4.2) ───────────────────────────────────────────
    def tick(self) -> bool:
        """Idle housekeeping — call from the driver/GUI heartbeat. Retires the
        brain child once it has been quiet past the window. Returns True when
        this call actually hibernated it."""
        return self._hib.maybe_hibernate()

    def hibernation_status(self) -> dict:
        return self._hib.status()

    def start_idle_watch(self) -> bool:
        """Begin retiring the brain while the surface is blocked in its own
        loop (``input()``, the Qt event loop). No-op when hibernation is off."""
        return self._hib.start_heartbeat()

    def stop_idle_watch(self) -> None:
        self._hib.stop_heartbeat()

    def poll_events(self) -> list:
        """Proactive ``event:*`` messages the brain pushed (e.g. mode offers)."""
        if self._proxy is None:
            return []
        if self._hib.state != "awake":
            return []            # asleep: the child's ticker stopped with it
        try:
            return self._proxy.poll_events()
        except Exception:
            return []

    def poll_offers(self) -> list:
        """``poll_events`` narrowed to surfaceable offers: ``[(text, payload)]``.

        The GUI's split-mode poller uses this so the "which event is an offer
        and what should the user actually see" rule lives here — testable
        without Qt — rather than inside a QObject slot.
        """
        return extract_offers(self.poll_events())

    # ── resilience ───────────────────────────────────────────────────
    def _try_restart(self) -> None:
        if not self._auto_restart:
            return                      # supervisor owns the lifecycle
        try:
            restart = getattr(self._proxy, "restart", None)
            if callable(restart):
                restart(ready_timeout=60)
        except Exception as e:  # pragma: no cover - defensive
            log.debug("[remote_brain] restart raised: %s", e)
