"""Split-mode driver — run_repl core with fakes (no process spawn) + the
RemoteBrain auto_restart=False behaviour (supervisor owns restarts)."""

from __future__ import annotations

from core.remote_brain import RemoteBrain
from core.service_bus import Msg
from run_split import run_repl


class _FakeProxy:
    def __init__(self):
        self.events = []
        self.restarted = False
        self.mode = "ok"

    def is_ready(self):
        return True

    def restart(self, ready_timeout=0):
        self.restarted = True
        return True

    def request(self, kind, payload=None, timeout=0):
        if self.mode == "raise":
            raise TimeoutError("down")
        return Msg(kind=kind, id="1", ok=True,
                   payload={"reply": f"handled:{(payload or {}).get('text','')}",
                            "skill": "s"})

    def poll_events(self):
        out, self.events = self.events, []
        return out


class _Entry:
    def __init__(self, proxy):
        self.proxy = proxy


class _FakeSup:
    def __init__(self, proxy):
        self._svcs = {"brain": _Entry(proxy)}


def _driver(inputs, proxy):
    """Run run_repl over a scripted input list; return the printed lines."""
    seq = iter(inputs)
    out = []

    def _read():
        return next(seq, None)

    run_repl(_read, out.append, _FakeSup(proxy))
    return out


class TestReplCore:
    def test_echoes_replies_and_quits(self):
        out = _driver(["hi", "", "quit", "should-not-run"], _FakeProxy())
        assert out[0].startswith("AERIS online")
        assert "AERIS: handled:hi" in out
        # blank line skipped, and 'quit' stops before 'should-not-run'
        assert not any("should-not-run" in x for x in out)

    def test_eof_ends_session(self):
        out = _driver([], _FakeProxy())        # immediate EOF
        assert out == ["AERIS online — crash-isolated brain. Type 'quit' to exit."]

    def test_proactive_event_surfaced(self):
        fp = _FakeProxy()
        fp.events = [Msg(kind="event:offer", payload={"text": "sleep mode karu?"})]
        out = _driver(["hi", "quit"], fp)
        assert any("AERIS (proactive): sleep mode karu?" in x for x in out)


class TestSupervisedRestart:
    def test_remotebrain_does_not_self_restart_when_supervised(self):
        fp = _FakeProxy()
        fp.mode = "raise"
        rb = RemoteBrain(proxy=fp, auto_restart=False)
        out = rb.process_text("hi")
        assert "reconnect" in out and fp.restarted is False   # supervisor owns it

    def test_remotebrain_self_restarts_when_standalone(self):
        fp = _FakeProxy()
        fp.mode = "raise"
        rb = RemoteBrain(proxy=fp, auto_restart=True)
        rb.process_text("hi")
        assert fp.restarted is True


class TestHibernationWiring:
    """The driver must tell the supervisor a hibernation stop is deliberate —
    otherwise the monitor resurrects the brain a second later."""

    class _Sup(_FakeSup):
        def __init__(self, proxy):
            super().__init__(proxy)
            self.suspended = self.resumed = 0

        def suspend(self, name):
            self.suspended += 1
            return True

        def resume(self, name):
            self.resumed += 1
            return True

    def test_off_by_default_the_banner_stays_one_line(self):
        out = _driver([], _FakeProxy())
        assert len(out) == 1

    def test_sleep_and_wake_bracket_the_supervisor(self, monkeypatch):
        monkeypatch.setenv("AERIS_BRAIN_HIBERNATE_S", "60")
        fp = _FakeProxy()
        fp.snapshot_calls = 0

        def _request(kind, payload=None, timeout=0):
            if kind == "snapshot":
                fp.snapshot_calls += 1
                return Msg(kind=kind, id="1", ok=True, payload={"state": {"v": 1}})
            if kind == "restore":
                return Msg(kind=kind, id="2", ok=True, payload={"restored": []})
            return Msg(kind=kind, id="3", ok=True,
                       payload={"reply": "handled:" + (payload or {}).get("text", ""),
                                "skill": "s"})

        fp.request = _request
        fp.start = lambda ready_timeout=0: True
        fp.stop = lambda timeout=0: None

        sup = self._Sup(fp)
        rb = RemoteBrain(proxy=fp, auto_restart=False,
                         suspend=lambda: sup.suspend("brain"),
                         resume=lambda: sup.resume("brain"))
        assert rb.hibernation_status()["enabled"] is True
        assert rb._hib.hibernate_now() is True
        assert sup.suspended == 1 and fp.snapshot_calls == 1
        rb.process_text("wake up")
        assert sup.resumed == 1
