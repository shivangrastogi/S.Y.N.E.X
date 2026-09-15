"""Brain-service request/response contract (fast, fake engine) + one real
spawn smoke test (slow — actually loads the brain in a child process)."""

from __future__ import annotations

import pytest

from core.brain_service import (
    brain_handler_factory, make_brain_handler, run_ticker_pass,
)


class _FakeEngine:
    def __init__(self):
        self.last_dispatch = None

    def process_text(self, text):
        # The real engine sets last_dispatch DURING process_text (per turn);
        # the service clears it before each call, so model that here.
        self.last_dispatch = {"skill": "greet", "intent": "greet",
                              "confidence": 0.9, "action": "executed"}
        return f"echo:{text}"


class TestContract:
    def test_ping(self):
        h = make_brain_handler(engine_builder=_FakeEngine)
        assert h("ping", {}) == {"pong": True}

    def test_utterance(self):
        h = make_brain_handler(engine_builder=_FakeEngine)
        r = h("utterance", {"text": "hi"})
        assert r["reply"] == "echo:hi" and r["skill"] == "greet"

    def test_unknown_kind(self):
        h = make_brain_handler(engine_builder=_FakeEngine)
        assert "unknown" in h("weird", {})["error"]

    def test_engine_exception_is_caught(self):
        class _Boom:
            last_dispatch = None

            def process_text(self, text):
                raise RuntimeError("nope")
        h = make_brain_handler(engine_builder=_Boom)
        r = h("utterance", {"text": "x"})
        assert r["reply"] == "" and "nope" in r["error"]


@pytest.mark.slow
def test_real_brain_runs_in_child_process():
    """The full brain (torch + encoder + skills) answers over the bus from its
    OWN process — proves the GUI can be ML-free."""
    from core.service_bus import ServiceProxy
    p = ServiceProxy("brain", brain_handler_factory)
    assert p.start(ready_timeout=240), "brain child process failed to start"
    try:
        r = p.request("utterance", {"text": "hello"}, timeout=60)
        assert r.ok, f"brain error: {r.error}"
        assert isinstance(r.payload.get("reply"), str) and r.payload["reply"].strip()
    finally:
        p.stop()


class TestProactiveTicker:
    def test_run_ticker_pass_emits_each_offer(self):
        from core.brain_service import run_ticker_pass
        emitted = []
        offers = [{"text": "sleep mode karu?", "kind": "mode_suggest"},
                  {"text": "", "kind": "skip"},          # no text → skipped
                  {"text": "work mode?", "kind": "mode_suggest"}]
        n = run_ticker_pass(lambda: offers, lambda k, p: emitted.append((k, p)))
        assert n == 2
        assert emitted[0] == ("offer", {"text": "sleep mode karu?", "kind": "mode_suggest"})
        assert emitted[1][1]["text"] == "work mode?"

    def test_run_ticker_pass_swallows_tick_errors(self):
        from core.brain_service import run_ticker_pass
        def boom():
            raise RuntimeError("nope")
        assert run_ticker_pass(boom, lambda k, p: None) == 0

    def test_no_ticker_without_emit(self):
        import threading
        before = {t.name for t in threading.enumerate()}
        make_brain_handler(engine_builder=_FakeEngine)   # emit=None → no thread
        after = {t.name for t in threading.enumerate()}
        assert "brain-initiative-ticker" not in (after - before)

    def test_handler_still_works_with_emit(self):
        h = make_brain_handler(engine_builder=_FakeEngine, emit=lambda k, p: None,
                               initiative_tick=lambda: [], start_ticker=False)
        assert h("utterance", {"text": "hi"})["reply"] == "echo:hi"


# ── split-mode "haan": offers must be ACTIONABLE, not just visible ───
# The in-process path parks engine._pending_offer inside
# _surface_initiatives. This ticker bypasses that entirely (it calls
# initiative_engine.tick() directly), so the split brain used to surface
# offers the user could see but could not accept.

def _offer(text="Sleep mode karu?", mode="sleep", with_on_yes=True):
    o = {"text": text, "kind": "mode_suggest"}
    if with_on_yes:
        o["on_yes"] = {"skill": "activate_mode", "slots": {"raw_text": mode}}
    return o


def test_ticker_parks_the_on_yes_offer():
    emitted, parked = [], []
    n = run_ticker_pass(lambda: [_offer()],
                        lambda k, p: emitted.append((k, p)),
                        park=lambda s, sl: parked.append((s, sl)))
    assert n == 1
    assert emitted and emitted[0][0] == "offer"
    assert parked == [("activate_mode", {"raw_text": "sleep"})]


def test_ticker_without_park_still_emits():
    """Back-compat: existing callers pass no park and must be unaffected."""
    emitted = []
    assert run_ticker_pass(lambda: [_offer()],
                           lambda k, p: emitted.append((k, p))) == 1
    assert len(emitted) == 1


def test_offer_without_on_yes_is_emitted_but_not_parked():
    """A plain nudge ("paani pi lo") has nothing to run on "haan"."""
    emitted, parked = [], []
    run_ticker_pass(lambda: [_offer(with_on_yes=False)],
                    lambda k, p: emitted.append(p),
                    park=lambda s, sl: parked.append(s))
    assert len(emitted) == 1
    assert parked == []


def test_malformed_on_yes_is_ignored():
    parked = []
    offers = [
        {"text": "a", "on_yes": "not-a-dict"},
        {"text": "b", "on_yes": {}},                 # no skill
        {"text": "c", "on_yes": {"slots": {"x": 1}}},  # no skill
    ]
    n = run_ticker_pass(lambda: offers, lambda k, p: None,
                        park=lambda s, sl: parked.append(s))
    assert n == 3, "malformed on_yes must not stop the offer surfacing"
    assert parked == []


def test_last_offer_wins_like_in_process():
    """The in-process loop overwrites _pending_offer per surfaced initiative;
    the ticker must not diverge from that."""
    parked = []
    offers = [_offer(mode="work"), _offer(mode="sleep")]
    run_ticker_pass(lambda: offers, lambda k, p: None,
                    park=lambda s, sl: parked.append(sl["raw_text"]))
    assert parked == ["work", "sleep"]


def test_a_raising_park_does_not_break_surfacing():
    """Parking is a nicety; the user must still SEE the offer if it fails."""
    emitted = []

    def boom(skill, slots):
        raise RuntimeError("engine mid-restart")

    n = run_ticker_pass(lambda: [_offer()],
                        lambda k, p: emitted.append(p), park=boom)
    assert n == 1 and len(emitted) == 1


def test_handler_ticker_parks_on_the_real_engine():
    """End-to-end through make_brain_handler: the engine it built must come
    out of a tick with its one-turn gate armed."""
    class _Eng:
        def __init__(self):
            self._pending_offer = None
            self.last_dispatch = None

        def process_text(self, t):
            return "ok"

    eng = _Eng()
    emitted = []
    make_brain_handler(
        engine_builder=lambda: eng,
        emit=lambda k, p: emitted.append((k, p)),
        initiative_tick=lambda: [_offer(mode="work")],
        tick_interval=0.05,
        start_ticker=True,
    )
    import time as _t
    deadline = _t.time() + 10
    while eng._pending_offer is None and _t.time() < deadline:
        _t.sleep(0.05)

    assert eng._pending_offer == ("activate_mode", {"raw_text": "work"}), \
        "split brain surfaced an offer the user cannot accept"
    assert emitted
