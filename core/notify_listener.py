"""Windows toast notification mirror — speak system toasts aloud.

When the optional ``winrt`` (or ``winsdk``) bridge is installed, AERIS
subscribes to ``Windows.UI.Notifications.Management.UserNotificationListener``
and reads each new toast aloud via TTS. Without that dep, the module
still imports cleanly and the skills report "unavailable" so the user
knows what to install.

Capabilities:
  * Requires "Notifications" access (enabled in Windows Settings →
    Privacy → Notifications). On first subscribe the user is asked to
    grant access — we surface the result message.
  * Read-only — we don't dismiss / interact with toasts.

Public API:
    listener = get_listener()
    listener.start()           # subscribes
    listener.stop()
    listener.is_running()
    listener.last_notification() -> Optional[dict]   # {'app','title','body','ts'}
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)


def _winrt_import():
    """Try winrt-runtime first, then winsdk as a fallback. Returns the
    notifications module or None.
    """
    try:
        # Modern: 'winrt' from pywinrt
        from winrt.windows.ui.notifications.management import (  # type: ignore
            UserNotificationListener
        )
        return UserNotificationListener
    except Exception:
        pass
    try:
        # Fallback: 'winsdk'
        from winsdk.windows.ui.notifications.management import (  # type: ignore
            UserNotificationListener
        )
        return UserNotificationListener
    except Exception:
        return None


class NotificationListener:
    def __init__(self):
        self._lock = threading.RLock()
        self._enabled = False
        self._last: Optional[dict] = None
        self._listeners: list[Callable[[dict], None]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    def is_available(self) -> bool:
        return _winrt_import() is not None

    def is_running(self) -> bool:
        return self._enabled

    def last_notification(self) -> Optional[dict]:
        return self._last

    def add_listener(self, fn: Callable[[dict], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def start(self) -> tuple[bool, str]:
        cls = _winrt_import()
        if cls is None:
            return False, ("winrt / winsdk nahi mila. Install for notification "
                           "mirror: 'pip install winsdk'.")
        if self._enabled:
            return True, "Already running."
        # Request access on the calling thread (it's an async operation but
        # we can poll-and-block via the sync API on a worker).
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, args=(cls,),
            daemon=True, name="NotificationListener",
        )
        self._thread.start()
        self._enabled = True
        return True, "Notification mirror starting (allow access in Windows if prompted)."

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._enabled = False

    # ── internals ──────────────────────────────────────────────────

    def _poll_loop(self, cls) -> None:
        """Polls the UserNotificationListener for new toasts at 1 Hz.
        Uses the *count*-based change detection rather than a real
        subscription to keep the code path simple (the event-driven
        WinRT API is awkward to bridge into a worker thread)."""
        try:
            listener = cls.current
        except Exception as e:
            log.warning("[notify] cannot access UserNotificationListener: %s", e)
            return
        seen_ids: set = set()
        while not self._stop_evt.is_set():
            try:
                # Synchronous-ish path: get_notifications_async returns
                # an IAsyncOperation, but most winrt builds let .get()
                # block until ready.
                notifs = listener.get_notifications_async(1).get()
                latest = None
                for n in notifs:
                    nid = getattr(n, "id", None)
                    if nid in seen_ids:
                        continue
                    seen_ids.add(nid)
                    latest = self._summarise(n)
                    if latest:
                        with self._lock:
                            self._last = latest
                            subs = list(self._listeners)
                        for fn in subs:
                            try:
                                fn(latest)
                            except Exception as e:
                                log.debug("[notify] subscriber raised: %s", e)
            except Exception as e:
                log.debug("[notify] poll iteration failed: %s", e)
            self._stop_evt.wait(1.0)

    def _summarise(self, notif) -> Optional[dict]:
        try:
            app = (getattr(notif, "app_info", None) and
                   getattr(notif.app_info, "display_info", None) and
                   getattr(notif.app_info.display_info, "display_name", "")) or "?"
        except Exception:
            app = "?"
        title = body = ""
        try:
            t = notif.notification
            v = t.visual.get_binding("ToastGeneric")
            if v is not None:
                texts = list(v.get_text_elements())
                if texts:
                    title = texts[0].text or ""
                if len(texts) > 1:
                    body = " ".join((e.text or "") for e in texts[1:])
        except Exception:
            pass
        if not (app or title or body):
            return None
        return {"app": app, "title": title, "body": body, "ts": time.time()}


# Module-level singleton.
_DEFAULT: Optional[NotificationListener] = None


def get_listener() -> NotificationListener:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = NotificationListener()
    return _DEFAULT


def install_speaker_hook() -> None:
    """Idempotent — register a TTS hook so each new toast is read aloud.
    Safe to call even when the listener can't actually start."""
    eng = get_listener()
    with eng._lock:
        for fn in eng._listeners:
            if getattr(fn, "_aeris_speaker_hook", False):
                return

    def _speak(notif: dict) -> None:
        title = (notif.get("title") or "").strip()
        body = (notif.get("body") or "").strip()
        if not (title or body):
            return
        msg = f"{title}. {body}" if title and body else (title or body)
        try:
            from core.tts import TTS
            TTS().speak(msg[:240])
        except Exception as e:
            log.info("[notify] tts speak failed: %s", e)

    _speak._aeris_speaker_hook = True  # type: ignore[attr-defined]
    eng.add_listener(_speak)
