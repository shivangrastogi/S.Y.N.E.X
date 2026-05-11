"""User-editable runtime settings.

JSON-backed config at ``data/settings.json``. Two access patterns:

  - Stateless: ``settings.get("assistant_name")`` / ``settings.set(...)`` —
    convenient one-shots that read/write disk on demand.
  - Subscriber: ``settings.subscribe(callback)`` for GUI widgets that
    need to react when a value changes from another thread.

Schema (with defaults):

    assistant_name           : str    = "AERIS"
    wake_word                : str    = "aeris"        (also accepts the assistant name lowercased)
    default_browser          : str    = "system"       (system | chrome | edge | brave | firefox | opera)
    default_browser_profile  : dict   = {}             (browser -> profile_directory string)
    speech_rate              : int    = 175            (TTS WPM; pyttsx3 / edge-tts)
    voice_gender             : str    = "female"
    language                 : str    = "hinglish"

Anything not listed is treated as user-defined — we don't validate keys, so
skills can stash their own knobs here ("focus_mode_apps", etc).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "settings.json")

_DEFAULTS: dict[str, Any] = {
    "assistant_name":          "AERIS",
    "wake_word":               "aeris",
    "default_browser":         "system",
    "default_browser_profile": {},
    "speech_rate":             175,
    "voice_gender":            "female",
    "language":                "hinglish",
    "focus_mode_close":        ["discord", "slack", "telegram"],
    "focus_mode_open":         ["code"],
    "focus_mode_pomodoro_min": 25,
}


class _SettingsStore:
    def __init__(self, path: str = _PATH):
        self.path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {}
        self._subscribers: list[Callable[[str, Any], None]] = []
        self._load()

    # ----------------------------------------------------------------- #
    #  Persistence                                                       #
    # ----------------------------------------------------------------- #

    def _load(self) -> None:
        with self._lock:
            self._data = dict(_DEFAULTS)
            if not os.path.exists(self.path):
                return
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except Exception as e:
                log.warning("[settings] load failed (%s); using defaults", e)

    def _save(self) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)

    # ----------------------------------------------------------------- #
    #  Public API                                                        #
    # ----------------------------------------------------------------- #

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                return self._data[key]
            return _DEFAULTS.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            old = self._data.get(key)
            self._data[key] = value
            self._save()
            subs = list(self._subscribers)
        if old != value:
            for cb in subs:
                try:
                    cb(key, value)
                except Exception as e:
                    log.info("[settings] subscriber raised: %s", e)

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def subscribe(self, cb: Callable[[str, Any], None]) -> None:
        with self._lock:
            self._subscribers.append(cb)

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._data = dict(_DEFAULTS)
            self._save()


_INSTANCE: Optional[_SettingsStore] = None


def get_settings() -> _SettingsStore:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = _SettingsStore()
    return _INSTANCE


# Convenience wrappers (most callers want these).

def get(key: str, default: Any = None) -> Any:
    return get_settings().get(key, default)


def set_(key: str, value: Any) -> None:
    get_settings().set(key, value)


def assistant_name() -> str:
    return str(get("assistant_name") or "AERIS")
