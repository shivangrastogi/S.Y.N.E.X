"""RemoteVision — the GUI-side seam to the vision service (P1).

Same idea as ``core/remote_brain.py``, but the lifecycle is inverted. The brain
is always-on and the interesting question is how to *retire* it (§6.22).
Vision is the opposite: nothing should exist until the user switches gestures
on, and the moment they switch them off the whole MediaPipe stack should leave
the machine — not be unloaded, not be idled, but gone with its process.

So the mapping is:

    enable()   → spawn the child, then tell it to start capturing
    disable()  → tell it to stop, then kill the child          (RAM returns)
    poll_gestures() → the recognised gestures since the last poll

which means "gestures off" is a state with **zero** vision residency, enforced
by process lifetime rather than by an unloader that has to guess when it is
safe. That is the §4.2 "one ML stack at a time" rule made structural.

Degrades the way the brain seam does: a machine with no camera or no MediaPipe
is a normal configuration, not a fault, so ``enable()`` returns False with a
reason instead of raising or crash-looping a service.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


def extract_gestures(events) -> list:
    """Pick recognised gesture names out of raw bus events, newest last.

    Tolerant for the same reason ``remote_brain.extract_offers`` is: these
    messages come from a separate process that may be a different build, so
    anything malformed is skipped rather than raised. Kept module-level and
    Qt-free so the GUI's poller is testable without a QApplication.
    """
    from core.bus_events import texts
    return texts(events, "gesture", field="name")


class RemoteVision:
    def __init__(self, proxy: Any = None, request_timeout: float = 10.0,
                 ready_timeout: float = 60.0):
        self._proxy = proxy
        self._timeout = request_timeout
        self._ready_timeout = ready_timeout
        self._own_proxy = proxy is None
        self.last_error: str = ""

    def _ensure_proxy(self) -> None:
        if self._proxy is None:
            from core.service_bus import ServiceProxy
            from core.vision_service import vision_handler_factory
            self._proxy = ServiceProxy("vision", vision_handler_factory)

    def is_running(self) -> bool:
        return self._proxy is not None and self._proxy.is_ready()

    # ── lifecycle ────────────────────────────────────────────────────
    def enable(self) -> bool:
        """Spawn the vision child (if needed) and start capturing."""
        self.last_error = ""
        self._ensure_proxy()
        if not self._proxy.is_ready():
            try:
                started = bool(self._proxy.start(ready_timeout=self._ready_timeout))
            except Exception as e:
                self.last_error = f"vision service failed to start: {e}"
                log.warning("[remote_vision] %s", self.last_error)
                return False
            if not started:
                # A FATAL handshake here usually means MediaPipe/OpenCV is
                # missing in the child — a configuration answer, not a crash.
                self.last_error = "vision service did not come up"
                log.warning("[remote_vision] %s", self.last_error)
                return False
        r = self._request("start", {})
        if r is None:
            self.last_error = "vision service did not answer"
            return False
        if not r.get("ok"):
            self.last_error = r.get("reason") or r.get("error") or "gestures unavailable"
            log.info("[remote_vision] enable refused: %s", self.last_error)
            return False
        return True

    def disable(self, kill: bool = True) -> None:
        """Stop capturing. With ``kill`` (the default) the child process goes
        too, which is the point — that is where the ~MediaPipe residency
        actually comes back."""
        if self._proxy is None:
            return
        ready = self._proxy.is_ready()
        if ready:
            self._request("stop", {})
        if not kill:
            return
        # Only tear down something that actually exists. A child that came up
        # but refused to start capturing still needs killing (ready, not
        # enabled); one that never spawned has nothing to kill, and a proxy
        # that is alive-but-not-ready is a failed handshake worth cleaning up.
        alive = getattr(self._proxy, "is_alive", lambda: False)
        try:
            if not (ready or alive()):
                return
        except Exception:
            return
        try:
            self._proxy.stop()
        except Exception as e:
            log.debug("[remote_vision] stop raised: %s", e)

    # ── the surface the GUI calls ────────────────────────────────────
    def status(self) -> dict:
        if self._proxy is None or not self._proxy.is_ready():
            return {"available": False, "enabled": False, "running": False}
        r = self._request("status", {}) or {}
        r["running"] = True
        return r

    def set_cursor_mode(self, on: bool) -> bool:
        r = self._request("cursor_mode", {"on": bool(on)})
        return bool(r and r.get("cursor_mode"))

    def snapshot_jpeg(self, timeout: float = 1.5,
                      quality: int = 70) -> Optional[bytes]:
        """One frame, JPEG-encoded — the only image that crosses the boundary.
        ``None`` when there is no camera or nothing was captured."""
        r = self._request("snapshot", {"timeout": timeout, "quality": quality},
                          timeout=max(self._timeout, timeout + 5.0))
        if not r or r.get("error"):
            self.last_error = (r or {}).get("error", "snapshot failed")
            return None
        jpeg = r.get("jpeg")
        return bytes(jpeg) if jpeg else None

    def poll_gestures(self) -> list:
        """Gesture names recognised since the last poll."""
        if self._proxy is None or not self._proxy.is_ready():
            return []
        try:
            return extract_gestures(self._proxy.poll_events())
        except Exception:
            return []

    # ── plumbing ─────────────────────────────────────────────────────
    def _request(self, kind: str, payload: dict,
                 timeout: Optional[float] = None) -> Optional[dict]:
        if self._proxy is None:
            return None
        try:
            r = self._proxy.request(kind, payload,
                                    timeout=timeout or self._timeout)
        except Exception as e:
            log.warning("[remote_vision] %s request failed: %s", kind, e)
            return None
        if not getattr(r, "ok", False):
            log.debug("[remote_vision] %s error: %s", kind, getattr(r, "error", ""))
            return {"error": getattr(r, "error", "") or "service error"}
        return dict(getattr(r, "payload", None) or {})
