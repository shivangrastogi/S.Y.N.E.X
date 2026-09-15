"""Routine offers by voice (core.routine_voice) — the verb layer for the
learning loop. Pure, injectable: scripted offers/actives + capture hooks, no
tracker/engine/model.
"""
from types import SimpleNamespace as NS

from core import routine_voice as rv


def _offer(key, title="Auto-start CODING at ~10:00", left=1):
    return NS(key=key, accepts_left=left,
              suggestion=NS(title=title, confidence=0.9))


def _hooks(pending=None, active=None):
    calls = {"accept": [], "reject": [], "revert": []}
    graduates = {}

    def accept_fn(k):
        calls["accept"].append(k)
        return graduates.get(k, False)

    def reject_fn(k):
        calls["reject"].append(k)

    def revert_fn(k):
        calls["revert"].append(k)

    kw = dict(pending_fn=lambda: list(pending or []),
              active_fn=lambda: list(active or []),
              accept_fn=accept_fn, reject_fn=reject_fn, revert_fn=revert_fn)
    return kw, calls, graduates


# ── intent classification, incl. the must-NOT-hijack cases ────────────

def test_classify_accept_reject_revert():
    assert rv.classify("isko auto kar do") == "accept"
    assert rv.classify("routine bana do") == "accept"
    assert rv.classify("roz kar diya karo") == "accept"
    assert rv.classify("rehne do") == "reject"
    assert rv.classify("routine mat banao") == "reject"
    assert rv.classify("auto band kar do") == "revert"
    assert rv.classify("morning routine band karo") == "revert"
    assert rv.classify("undo that routine") == "revert"


def test_classify_ignores_ordinary_commands():
    # a bare stop/confirm must NOT be read as a routine action
    assert rv.classify("torch band karo") is None
    assert rv.classify("band karo") is None
    assert rv.classify("haan") is None
    assert rv.classify("gaana chalu kar do") is None
    assert rv.classify("mausam kaisa hai") is None


# ── accept flow ───────────────────────────────────────────────────────

def test_accept_progresses_then_graduates():
    kw, calls, grad = _hooks(pending=[_offer("arrival:CODING:10:00", left=2)])
    reply = rv.handle("isko auto kar do", **kw)
    assert calls["accept"] == ["arrival:CODING:10:00"]
    assert "2 aur" in reply                    # progress surfaced

    grad["arrival:CODING:10:00"] = True        # next accept graduates it
    reply2 = rv.handle("haan routine bana do", **kw)
    assert "khud chalega" in reply2
    assert "CODING" in reply2


def test_accept_with_no_pending_is_honest():
    kw, calls, _ = _hooks(pending=[])
    reply = rv.handle("routine bana do", **kw)
    assert reply is not None and "koi routine suggest" in reply
    assert calls["accept"] == []


# ── reject flow ───────────────────────────────────────────────────────

def test_reject_top_pending():
    kw, calls, _ = _hooks(pending=[_offer("winddown:22:30")])
    reply = rv.handle("nahi, rehne do", **kw)
    assert calls["reject"] == ["winddown:22:30"]
    assert "nahi banaya" in reply


# ── revert flow ───────────────────────────────────────────────────────

def test_revert_single_running_routine():
    active = [{"key": "arrival:CODING:10:00", "name": "auto coding start"}]
    kw, calls, _ = _hooks(active=active)
    reply = rv.handle("auto band kar do", **kw)
    assert calls["revert"] == ["arrival:CODING:10:00"]
    assert "band kar diya" in reply


def test_revert_names_the_right_routine():
    active = [
        {"key": "arrival:CODING:10:00", "name": "coding start"},
        {"key": "winddown:22:30", "name": "wind down"},
    ]
    kw, calls, _ = _hooks(active=active)
    reply = rv.handle("wind down routine band karo", **kw)
    assert calls["revert"] == ["winddown:22:30"]
    assert "band kar diya" in reply


def test_revert_ambiguous_asks_which():
    active = [
        {"key": "a", "name": "coding start"},
        {"key": "b", "name": "wind down"},
    ]
    kw, calls, _ = _hooks(active=active)
    reply = rv.handle("routine band karo", **kw)   # no name, 2 running
    assert calls["revert"] == []                   # didn't guess
    assert "Konsa" in reply
    assert "coding start" in reply and "wind down" in reply


def test_revert_with_nothing_running():
    kw, calls, _ = _hooks(active=[])
    reply = rv.handle("auto routine band karo", **kw)
    assert calls["revert"] == []
    assert "chal hi nahi raha" in reply


# ── non-routine utterance falls through ───────────────────────────────

def test_unrelated_returns_none():
    kw, _, _ = _hooks(pending=[_offer("x")])
    assert rv.handle("chrome kholo", **kw) is None
