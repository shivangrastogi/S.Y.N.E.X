"""Process-wide serialization of Win32 clipboard access.

Sibling of ``core/encoder_lock.py``, and it exists for the same reason: a
shared native resource that Windows does not allow two threads to touch at
once, reached from many places in this codebase.

The bug
-------
AERIS polls the clipboard from **two independent daemon threads**:

* ``core/cloud_bridge.py:_clip_loop``        — every 1.0 s (phone sync)
* ``skills/clipboard_history.py:_watcher_loop`` — every 0.5 s (history)

…plus ~40 one-shot ``pyperclip.copy()`` / ``.paste()`` call sites in skills,
which run on the brain thread whenever a command needs the clipboard.

The Windows clipboard is a single globally-locked resource. `paste_windows`
does `OpenClipboard()` → `GetClipboardData()` → `CloseClipboard()`, and the
handle `GetClipboardData` returns is **owned by the clipboard, not by the
caller** — it stops being valid the moment anyone calls `CloseClipboard()` or
`EmptyClipboard()`. With two pollers 500 ms out of phase, one thread reads
through a handle the other has just invalidated: a use-after-free, which
Windows reports as `0xC0000374` (heap corruption) — the same signature as the
encoder crashes, from a completely different resource.

Reproduced twice while running the full test suite: both times the faulting
thread was `_clip_loop` inside `pyperclip.paste_windows`, with the history
watcher live alongside it.

The fix
-------
``install()`` wraps ``pyperclip.copy`` / ``pyperclip.paste`` on the shared
module object with ``CLIPBOARD_LOCK``. Because every call site in this repo
reaches the clipboard through ``import pyperclip``, patching the module makes
all of them — including ones written later — serialized, with no call-site
edits and no change in behaviour or exceptions raised.

Idempotent and safe to call from anywhere, including when pyperclip isn't
installed (then it's a no-op and the existing "pyperclip nahi hai" degrade
paths keep working).
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

# RLock: a skill may copy() inside a paste()-driven flow on one thread.
CLIPBOARD_LOCK = threading.RLock()

_MARK = "_aeris_clipboard_locked"
_install_lock = threading.Lock()


def install() -> bool:
    """Serialize pyperclip through CLIPBOARD_LOCK. True if it applied now.

    Returns False when pyperclip is absent or the patch is already in place.
    Never raises — clipboard support is optional everywhere in this codebase.
    """
    with _install_lock:
        try:
            import pyperclip
        except Exception as e:
            log.debug("[clipboard_lock] pyperclip unavailable: %s", e)
            return False

        if getattr(pyperclip, _MARK, False):
            return False

        real_copy = pyperclip.copy
        real_paste = pyperclip.paste

        def locked_copy(text):
            with CLIPBOARD_LOCK:
                return real_copy(text)

        def locked_paste():
            with CLIPBOARD_LOCK:
                return real_paste()

        # Keep the originals reachable for debugging / a clean uninstall.
        locked_copy._aeris_wrapped = real_copy      # type: ignore[attr-defined]
        locked_paste._aeris_wrapped = real_paste    # type: ignore[attr-defined]

        pyperclip.copy = locked_copy
        pyperclip.paste = locked_paste
        setattr(pyperclip, _MARK, True)
        log.info("[clipboard_lock] pyperclip serialized (0xC0000374 guard)")
        return True


def is_installed() -> bool:
    try:
        import pyperclip
    except Exception:
        return False
    return bool(getattr(pyperclip, _MARK, False))
