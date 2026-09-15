"""`GestureEngine`'s surface, backed by the vision child process (§6.30).

The brain cutover (§6.6.4) was easy because the GUI touched the engine through
exactly one method, `process_text`. Vision looked worse: `get_gesture_engine()`
is a singleton called from `skills/gesture_skill.py`, `ui/calibration_wizard
.py`, `ui/hud_overlay.py`, `ui/jarvis_v31/tab_panels.py` and `main_window`.

Resolving what those callers actually *use* shrank the problem to seven names:

    add_listener  is_available  is_enabled  start  stop
    set_cursor_mode  is_cursor_mode

`RemoteVision` already answers six of them. The one real mismatch is
`add_listener`: `GestureEngine` **pushes** to listeners from its capture
thread, while the bus **pulls** with `poll_gestures()`. So this class is the
push/pull adapter — a poll thread that fans events out to listeners — and with
it the cutover becomes a single decision at the singleton instead of edits
across five files. Every existing caller keeps working unchanged.

That the listeners fire on a worker thread is not a new hazard: `GestureEngine`
already invoked them from the capture thread, which is why `main_window`
marshals through `pyqtSignal`. The threading contract is preserved exactly.

Off unless ``AERIS_SPLIT_VISION=1``. Like every other cutover here, it waits on
a live check (`python run_vision_split.py`) — the spawn itself is already
verified on this machine (§6.23).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

ENV_SPLIT_VISION = "AERIS_SPLIT_VISION"

# How often the adapter drains gestures off the bus. This is the only latency
# the split adds on top of in-process gestures — against ~30 ms of capture and
# inference, and well under the ~200 ms at which a UI response stops feeling
# immediate. Faster would burn a wakeup per tick for no perceptible gain.
POLL_S = 0.12


def split_vision_enabled(environ: Optional[dict] = None) -> bool:
    raw = (environ if environ is not None else os.environ).get(ENV_SPLIT_VISION, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


class RemoteGestureEngine:
    """Presents the `GestureEngine` surface over a `RemoteVision`.

    ``vision`` is injected, so the whole adapter — including the push/pull
    conversion — is tested with a fake and no camera, no MediaPipe, no spawn.
    """

    def __init__(self, vision: Any = None, poll_s: float = POLL_S,
                 sleep_fn: Callable[[float], None] = time.sleep):
        if vision is None:
            from core.remote_vision import RemoteVision
            vision = RemoteVision()
        self._vision = vision
        self._poll_s = poll_s
        self._sleep = sleep_fn
        self._listeners: list = []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._enabled = False
        self.dispatched = 0

    # ── the GestureEngine surface ────────────────────────────────────
    def is_available(self) -> bool:
        try:
            return bool(self._vision.status().get("available"))
        except Exception:
            return False

    def is_enabled(self) -> bool:
        return self._enabled

    def start(self) -> bool:
        with self._lock:
            if self._enabled:
                return True
            if not self._vision.enable():
                log.info("[remote_gestures] vision refused: %s",
                         getattr(self._vision, "last_error", ""))
                return False
            self._enabled = True
            self._start_poller()
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._enabled:
                return
            self._enabled = False
        # Stop the poller BEFORE killing the child: a drain against a dead
        # proxy is harmless but pointless, and joining first keeps the
        # listener callbacks from overlapping teardown.
        self._stop_poller()
        try:
            self._vision.disable()
        except Exception as e:
            log.debug("[remote_gestures] disable raised: %s", e)

    def add_listener(self, fn: Callable[[str], None]) -> None:
        """Register a gesture callback.

        Fires on the poll thread — the same contract `GestureEngine` had,
        where listeners ran on the capture thread. Callers that marshal to the
        GUI thread (`main_window` via `pyqtSignal`) need no change.
        """
        with self._lock:
            self._listeners.append(fn)

    def set_cursor_mode(self, on: bool) -> bool:
        return bool(self._vision.set_cursor_mode(bool(on)))

    def is_cursor_mode(self) -> bool:
        try:
            return bool(self._vision.status().get("cursor_mode"))
        except Exception:
            return False

    # ── push/pull conversion ─────────────────────────────────────────
    def drain_once(self) -> int:
        """One poll → fan out. Pure enough to drive from a test without the
        thread; returns how many gestures were dispatched."""
        try:
            names = self._vision.poll_gestures()
        except Exception as e:
            log.debug("[remote_gestures] poll failed: %s", e)
            return 0
        n = 0
        with self._lock:
            listeners = list(self._listeners)
        for name in names or []:
            for fn in listeners:
                try:
                    fn(name)
                except Exception as e:
                    # One bad listener must not stop the others, nor kill the
                    # poll thread — GestureEngine swallows these too.
                    log.debug("[remote_gestures] listener raised: %s", e)
            n += 1
        self.dispatched += n
        return n

    def _start_poller(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()

        def _run():
            while not self._stop.is_set():
                self.drain_once()
                self._sleep(self._poll_s)

        self._thread = threading.Thread(target=_run, name="remote-gestures",
                                        daemon=True)
        self._thread.start()

    def _stop_poller(self) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(2.0)

    # ── introspection ────────────────────────────────────────────────
    def status(self) -> dict:
        s = {}
        try:
            s = dict(self._vision.status())
        except Exception:
            pass
        s.update({"split": True, "enabled": self._enabled,
                  "listeners": len(self._listeners),
                  "dispatched": self.dispatched})
        return s
