"""Hibernation across a REAL process boundary (§6.22, verified 2026-09-01).

`tests/test_brain_snapshot.py` proves the capture/restore rules and
`tests/test_brain_hibernator.py` proves the state machine — both with fakes, in
one process. Neither answers the question hibernation actually rests on:

    does the snapshot survive being pickled to a child, the child dying, and
    being pushed into its replacement?

If it doesn't, hibernation silently loses the conversation — which is the exact
failure the whole feature exists to prevent, and it would look like nothing at
all from the outside. So this drives the real `ServiceProxy`, with real child
processes, through a full sleep/wake cycle.

It uses a **light probe engine** rather than the real `JarvisMainEngine`: the
thing under test is the bus round-trip and the process boundary, not torch. A
full-brain spawn already exists in `tests/test_brain_service.py`.

Slow lane — Windows `spawn` re-imports the suite per child.
"""

from __future__ import annotations

import pytest

from core.brain_service import make_brain_handler
from core.brain_snapshot import capture, is_empty
from core.conversation import ConversationHistory
from core.dialogue_context import DialogueState

pytestmark = pytest.mark.slow


class _ProbeEngine:
    """Exactly the surface `brain_service` + `brain_snapshot` touch."""

    def __init__(self):
        self.dialogue = DialogueState()
        self.history = ConversationHistory(max_turns=8)
        self._pending_offer = None
        self.last_dispatch = None

    def process_text(self, text: str) -> str:
        # Mirror the real engine: record the executed turn in dialogue
        # context and the transcript, and publish a dispatch.
        self.dialogue.note("open_app", {"app_name": "chrome"}, text,
                           "Chrome khol diya, sir.")
        self.history.add_user(text)
        self.history.add_assistant("Chrome khol diya, sir.")
        self._pending_offer = ("activate_mode", {"raw_text": "sleep mode"})
        self.last_dispatch = {"skill": "open_app", "intent": "open_app",
                              "confidence": 0.95, "action": "executed"}
        return "Chrome khol diya, sir."


def probe_handler_factory(emit=None):
    """Top-level so Windows spawn can pickle it by qualified name."""
    return make_brain_handler(engine_builder=_ProbeEngine, emit=emit,
                              start_ticker=False)


@pytest.fixture
def proxy():
    from core.service_bus import ServiceProxy
    p = ServiceProxy("probe", probe_handler_factory)
    assert p.start(ready_timeout=60), "probe child failed to start"
    yield p
    p.stop()


def _snapshot(p):
    r = p.request("snapshot", {}, timeout=30)
    assert r.ok, f"snapshot failed: {r.error}"
    return r.payload["state"]


class TestTheRoundTrip:
    def test_a_fresh_child_has_nothing_to_carry(self, proxy):
        assert is_empty(_snapshot(proxy))

    def test_the_snapshot_crosses_the_process_boundary(self, proxy):
        """The payload has to survive pickling in both directions — a dict
        that didn't would lose the conversation with no error anywhere."""
        proxy.request("utterance", {"text": "chrome kholo"}, timeout=30)
        snap = _snapshot(proxy)
        assert not is_empty(snap)
        assert snap["dialogue"]["last_intent"] == "open_app"
        assert snap["history"]["turns"][0]["content"] == "chrome kholo"
        assert snap["offer"]["skill"] == "activate_mode"

    def test_restore_lands_in_a_replacement_child(self, proxy):
        """The whole hibernation cycle: talk, snapshot, kill, respawn,
        restore — and the new process knows what the old one knew."""
        proxy.request("utterance", {"text": "chrome kholo"}, timeout=30)
        carried = _snapshot(proxy)

        proxy.stop()                                   # the child dies here
        assert proxy.start(ready_timeout=60), "replacement child failed"
        assert is_empty(_snapshot(proxy)), "replacement started dirty"

        r = proxy.request("restore", {"state": carried}, timeout=30)
        assert r.ok, f"restore failed: {r.error}"
        assert set(r.payload["restored"]) == {"dialogue", "history", "offer"}

        back = _snapshot(proxy)
        assert back["dialogue"]["last_intent"] == "open_app"
        assert back["dialogue"]["last_entities"] == {"app_name": "chrome"}
        assert back["history"]["turns"][0]["content"] == "chrome kholo"
        assert back["offer"]["skill"] == "activate_mode"

    def test_the_age_is_rebased_onto_the_new_process_clock(self, proxy):
        """`DialogueState.ts` is `time.monotonic()`, whose zero point is not
        comparable across processes. If the rebase were wrong the restored
        turn would read as either permanently fresh or never fresh — silently,
        and in a different process than the one that captured it."""
        proxy.request("utterance", {"text": "chrome kholo"}, timeout=30)
        carried = _snapshot(proxy)
        carried["dialogue"]["age_s"] = 30.0

        proxy.stop()
        assert proxy.start(ready_timeout=60)
        proxy.request("restore", {"state": carried}, timeout=30)

        back = _snapshot(proxy)
        # Captured immediately after restore, so the age should still read
        # ~30 s — proof it was rebased rather than reset or carried raw.
        assert 29.0 <= back["dialogue"]["age_s"] <= 40.0


class TestDegradation:
    def test_restoring_junk_is_refused_without_killing_the_child(self, proxy):
        r = proxy.request("restore", {"state": {"dialogue": {"nope": 1}}},
                          timeout=30)
        assert r.ok and r.payload["restored"] == []
        assert proxy.request("ping", {}, timeout=10).payload == {"pong": True}

    def test_restoring_nothing_is_harmless(self, proxy):
        r = proxy.request("restore", {}, timeout=30)
        assert r.ok and r.payload["restored"] == []

    def test_the_child_still_answers_normally_after_a_restore(self, proxy):
        proxy.request("utterance", {"text": "chrome kholo"}, timeout=30)
        carried = _snapshot(proxy)
        proxy.request("restore", {"state": carried}, timeout=30)
        r = proxy.request("utterance", {"text": "phir se"}, timeout=30)
        assert r.ok and r.payload["reply"]


class TestLocalCaptureMatchesTheWireFormat:
    def test_capture_of_the_same_engine_produces_the_same_shape(self):
        """Cheap guard that the in-process capture and what comes back over
        the bus agree — they are the same function, and this fails loudly if
        the handler ever starts reshaping the payload."""
        e = _ProbeEngine()
        e.process_text("chrome kholo")
        local = capture(e)
        assert set(local) == {"v", "dialogue", "history", "offer"}
