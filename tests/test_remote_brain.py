"""RemoteBrain adapter — fake proxy, no spawn. Proves the GUI seam + graceful
degradation (never hangs, never crashes when the brain is down)."""

from __future__ import annotations

from core.remote_brain import RemoteBrain
from core.service_bus import Msg


class _FakeProxy:
    def __init__(self, ready=True):
        self._ready = ready
        self.restarted = False
        self.events = []
        self.mode = "ok"          # ok | raise | error

    def start(self, ready_timeout=0):
        return self._ready

    def is_ready(self):
        return self._ready

    def stop(self):
        self._ready = False

    def restart(self, ready_timeout=0):
        self.restarted = True
        self._ready = True
        return True

    def request(self, kind, payload=None, timeout=0):
        if self.mode == "raise":
            raise TimeoutError("brain down")
        if self.mode == "error":
            return Msg(kind=kind, id="1", ok=False, error="boom")
        return Msg(kind=kind, id="1", ok=True,
                   payload={"reply": f"handled:{(payload or {}).get('text','')}",
                            "skill": "some_skill"})

    def poll_events(self):
        out, self.events = self.events, []
        return out


class TestHappyPath:
    def test_process_text_returns_reply_and_skill(self):
        rb = RemoteBrain(proxy=_FakeProxy())
        assert rb.process_text("hi") == "handled:hi"
        assert rb.last_dispatch == {"skill": "some_skill"}

    def test_is_ready_reflects_proxy(self):
        assert RemoteBrain(proxy=_FakeProxy(ready=True)).is_ready() is True
        assert RemoteBrain(proxy=_FakeProxy(ready=False)).is_ready() is False


class TestGracefulDegradation:
    def test_not_ready_gives_friendly_line(self):
        rb = RemoteBrain(proxy=_FakeProxy(ready=False))
        out = rb.process_text("hi")
        assert "load ho raha" in out          # never crashes/hangs

    def test_request_exception_restarts_and_degrades(self):
        fp = _FakeProxy()
        fp.mode = "raise"
        rb = RemoteBrain(proxy=fp)
        out = rb.process_text("hi")
        assert "reconnect" in out and fp.restarted is True

    def test_error_reply_is_soft(self):
        fp = _FakeProxy()
        fp.mode = "error"
        rb = RemoteBrain(proxy=fp)
        assert "gadbad" in rb.process_text("hi")


class TestEvents:
    def test_poll_events_passthrough(self):
        fp = _FakeProxy()
        fp.events = [Msg(kind="event:offer", payload={"text": "sleep mode?"})]
        rb = RemoteBrain(proxy=fp)
        evs = rb.poll_events()
        assert len(evs) == 1 and evs[0].payload["text"] == "sleep mode?"


# ── proactive offer drain (split-mode GUI poller) ────────────────────
# The child brain's initiative ticker pushes `event:offer` onto the bus and
# RemoteBrain buffers it, but nothing drained that buffer — so in split mode
# proactive offers reached the GUI process and died there. `extract_offers`
# is the Qt-free half of the drain the GUI now runs on a timer.

from core.remote_brain import extract_offers


class _Ev:
    def __init__(self, kind, payload):
        self.kind = kind
        self.payload = payload


def test_extract_offers_picks_offer_events():
    evs = [_Ev("event:offer", {"text": "Sleep mode karu?", "on_yes": "sleep"})]
    assert extract_offers(evs) == [
        ("Sleep mode karu?", {"text": "Sleep mode karu?", "on_yes": "sleep"})]


def test_extract_offers_accepts_unprefixed_kind():
    """The bus prefixes with 'event:', but tolerate the raw kind too."""
    assert extract_offers([_Ev("offer", {"text": "hi"})]) == [("hi", {"text": "hi"})]


def test_extract_offers_ignores_other_event_kinds():
    evs = [_Ev("event:health", {"text": "ok"}),
           _Ev("event:log", {"text": "noise"})]
    assert extract_offers(evs) == []


def test_extract_offers_drops_empty_text():
    """An offer with nothing to say must not become an empty chat bubble."""
    evs = [_Ev("event:offer", {"text": "   "}),
           _Ev("event:offer", {"text": ""}),
           _Ev("event:offer", {}),
           _Ev("event:offer", {"text": None})]
    assert extract_offers(evs) == []


def test_extract_offers_strips_whitespace():
    assert extract_offers([_Ev("event:offer", {"text": "  padded  "})])[0][0] == "padded"


def test_extract_offers_survives_malformed_events():
    """These come from a SEPARATE process that may be a different build —
    one bad message must not abort the drain."""
    good = _Ev("event:offer", {"text": "real one"})
    evs = [None, "garbage", _Ev("event:offer", "not-a-dict"),
           _Ev(None, None), good]
    assert extract_offers(evs) == [("real one", {"text": "real one"})]


def test_extract_offers_handles_empty_and_none():
    assert extract_offers([]) == []
    assert extract_offers(None) == []


def test_extract_offers_returns_a_copy_of_the_payload():
    """The caller marshals this across a Qt signal — it must not alias the
    buffer the brain proxy still owns."""
    payload = {"text": "hi", "on_yes": "x"}
    (_, got), = extract_offers([_Ev("event:offer", payload)])
    got["on_yes"] = "mutated"
    assert payload["on_yes"] == "x"


def test_poll_offers_uses_poll_events():
    from core.remote_brain import RemoteBrain

    class _Proxy:
        def poll_events(self):
            return [_Ev("event:offer", {"text": "break le lo"}),
                    _Ev("event:health", {"text": "ignored"})]

    rb = RemoteBrain(proxy=_Proxy(), auto_restart=False)
    assert rb.poll_offers() == [("break le lo", {"text": "break le lo"})]


def test_poll_offers_is_empty_without_a_proxy():
    from core.remote_brain import RemoteBrain
    assert RemoteBrain(proxy=None, auto_restart=False).poll_offers() == []
