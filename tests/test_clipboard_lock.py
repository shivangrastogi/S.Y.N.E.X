"""Clipboard serialization — the second 0xC0000374 source.

Two daemon threads poll the Win32 clipboard (cloud_bridge's phone sync every
1.0 s, clipboard_history's watcher every 0.5 s) and ~40 skill call sites touch
it on the brain thread. The clipboard handle `GetClipboardData` hands back is
invalidated by anyone else's `CloseClipboard`, so unserialized access is a
use-after-free. These tests pin the guard that makes that impossible.
"""

from __future__ import annotations

import sys
import threading
import types

import pytest

from core import clipboard_lock


@pytest.fixture
def fake_pyperclip(monkeypatch):
    """A stand-in pyperclip that records overlapping access."""
    mod = types.ModuleType("pyperclip")
    state = {"inside": 0, "max_overlap": 0, "calls": []}
    barrier = threading.Barrier(2, timeout=5)

    def _enter(tag):
        state["inside"] += 1
        state["max_overlap"] = max(state["max_overlap"], state["inside"])
        state["calls"].append(tag)

    def paste():
        _enter("paste")
        try:
            # Without a lock both threads sit in here together.
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
            return "text"
        finally:
            state["inside"] -= 1

    def copy(text):
        _enter("copy")
        try:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
            return None
        finally:
            state["inside"] -= 1

    mod.paste = paste
    mod.copy = copy
    monkeypatch.setitem(sys.modules, "pyperclip", mod)
    return mod, state, barrier


def test_install_wraps_copy_and_paste(fake_pyperclip):
    mod, _, _ = fake_pyperclip
    raw_paste = mod.paste
    assert clipboard_lock.install() is True
    assert mod.paste is not raw_paste
    assert clipboard_lock.is_installed() is True
    assert mod.paste._aeris_wrapped is raw_paste


def test_install_is_idempotent(fake_pyperclip):
    mod, _, _ = fake_pyperclip
    assert clipboard_lock.install() is True
    wrapped_once = mod.paste
    assert clipboard_lock.install() is False, "must not double-wrap"
    assert mod.paste is wrapped_once


def test_install_is_a_noop_without_pyperclip(monkeypatch):
    """Clipboard support is optional everywhere — a missing module must not
    raise, so the existing 'pyperclip nahi hai' degrade paths still run."""
    monkeypatch.setitem(sys.modules, "pyperclip", None)

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) \
        else __builtins__.__import__

    def no_pyperclip(name, *a, **k):
        if name == "pyperclip":
            raise ImportError("no pyperclip")
        return real_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", no_pyperclip)
    assert clipboard_lock.install() is False
    assert clipboard_lock.is_installed() is False


def test_two_threads_never_overlap_once_installed(fake_pyperclip):
    """The actual property: with the lock on, a second thread cannot be
    inside pyperclip while the first still is."""
    mod, state, barrier = fake_pyperclip
    clipboard_lock.install()

    def worker():
        mod.paste()

    ts = [threading.Thread(target=worker) for _ in range(2)]
    for t in ts:
        t.start()
    # The barrier can never trip (each thread is alone), so it times out and
    # both calls return via BrokenBarrierError — that is the proof.
    for t in ts:
        t.join(timeout=20)
        assert not t.is_alive()

    assert state["max_overlap"] == 1, (
        f"clipboard access overlapped ({state['max_overlap']} threads inside "
        "pyperclip at once) — the 0xC0000374 race is back")
    assert state["calls"] == ["paste", "paste"]


def test_copy_and_paste_share_one_lock(fake_pyperclip):
    """A copy on one thread must exclude a paste on another — they contend
    for the same Win32 clipboard, not two separate ones."""
    mod, state, barrier = fake_pyperclip
    clipboard_lock.install()

    threads = [threading.Thread(target=lambda: mod.paste()),
               threading.Thread(target=lambda: mod.copy("x"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive()

    assert state["max_overlap"] == 1
    assert sorted(state["calls"]) == ["copy", "paste"]


def test_lock_is_reentrant():
    """A skill may copy() while already inside a paste()-driven flow on the
    same thread; that must not self-deadlock."""
    with clipboard_lock.CLIPBOARD_LOCK:
        acquired = clipboard_lock.CLIPBOARD_LOCK.acquire(timeout=2)
        assert acquired, "CLIPBOARD_LOCK must be reentrant"
        clipboard_lock.CLIPBOARD_LOCK.release()


def test_return_values_pass_through(fake_pyperclip):
    mod, _, _ = fake_pyperclip
    clipboard_lock.install()
    # Single-threaded: barrier times out, paste still returns its value.
    assert mod.paste() == "text"
