"""Continuity C1 — envelopes, presence arbitration, router, memory slice
(fast lane; fake bridge everywhere per the mock-executor rule)."""

from __future__ import annotations

import pytest

from core.continuity import (
    Envelope, ContinuityRouter, DeviceRegistry,
    LAPTOP_PRIORITY_S, STALE_BEAT_S, memory_slice,
)
from core.goal_system import GoalStore


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class _Send:
    def __init__(self, ok=True):
        self.ok = ok
        self.sent: list[dict] = []

    def __call__(self, extra_env: dict) -> bool:
        self.sent.append(extra_env)
        return self.ok


# ── envelope ─────────────────────────────────────────────────────────── #

class TestEnvelope:
    def test_round_trip(self):
        env = Envelope(kind="goal.capture", payload={"text": "x"},
                       origin="phone")
        back = Envelope.from_extra(env.to_extra())
        assert back is not None
        assert (back.kind, back.payload, back.origin, back.id) == \
               ("goal.capture", {"text": "x"}, "phone", env.id)

    @pytest.mark.parametrize("bad", [
        None, "str", 42, {}, {"kind": "unknown.kind"},
        {"kind": "goal.capture", "ts": "not-a-number"},
    ])
    def test_malformed_is_none(self, bad):
        assert Envelope.from_extra(bad) is None

    def test_expiry_both_directions(self):
        env = Envelope(kind="presence.beat", ts=1000.0, ttl_s=120.0)
        assert not env.expired(now=1100.0)
        assert env.expired(now=1200.1)       # stale
        assert env.expired(now=800.0)        # future-dated beyond skew window


# ── device registry ──────────────────────────────────────────────────── #

class TestDeviceRegistry:
    def test_default_is_laptop(self):
        assert DeviceRegistry().active_device() == "laptop"

    def test_phone_active_laptop_quiet_routes_phone(self):
        clk = _Clock()
        reg = DeviceRegistry(now_fn=clk)
        reg.beat("laptop", "active")
        clk.t += LAPTOP_PRIORITY_S + 1        # laptop quiet beyond priority
        reg.beat("phone", "active")
        assert reg.active_device() == "phone"

    def test_recent_laptop_touch_wins_over_active_phone(self):
        clk = _Clock()
        reg = DeviceRegistry(now_fn=clk)
        reg.beat("phone", "active")
        reg.beat("laptop", "active")
        assert reg.active_device() == "laptop"

    def test_stale_phone_beat_falls_back_to_laptop(self):
        clk = _Clock()
        reg = DeviceRegistry(now_fn=clk)
        reg.beat("phone", "active")
        clk.t += STALE_BEAT_S + 1
        assert reg.active_device() == "laptop"

    def test_idle_phone_never_active(self):
        reg = DeviceRegistry(now_fn=_Clock())
        reg.beat("phone", "idle")
        assert reg.active_device() == "laptop"

    def test_garbage_device_and_state_are_safe(self):
        reg = DeviceRegistry(now_fn=_Clock())
        reg.beat("toaster", "active")
        reg.beat("phone", "warp")             # coerced to idle
        assert reg.active_device() == "laptop"
        assert "toaster" not in reg.snapshot()


# ── router inbound ───────────────────────────────────────────────────── #

def _router(tmp_path, clk=None, send=None, speak=None, mem=None):
    clk = clk or _Clock()
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=clk)
    r = ContinuityRouter(send, goal_store=store,
                         registry=DeviceRegistry(now_fn=clk),
                         speak_fn=speak, memory_slice_fn=mem, now_fn=clk)
    return r, store, clk


class TestInbound:
    def test_presence_beat_updates_registry_with_local_clock(self, tmp_path):
        r, _, clk = _router(tmp_path)
        env = Envelope(kind="presence.beat", origin="phone",
                       payload={"state": "active"},
                       ts=clk() - 500)         # skewed phone clock…
        env.ttl_s = 1000                       # …but within ttl
        assert r.inbound(env.to_extra()) is None
        # Beat stored at OUR clock → phone counts as fresh-active.
        assert r.registry.active_device() == "phone"

    def test_goal_capture_matching_and_nonmatching_text(self, tmp_path):
        r, store, clk = _router(tmp_path)
        ack = r.inbound(Envelope(kind="goal.capture", origin="phone",
                                 ts=clk(),
                                 payload={"text": "rahul ko follow up"}
                                 ).to_extra())
        assert ack and "rahul" in ack.lower()
        # Non-regex text still captured (phone already decided it's a goal).
        r.inbound(Envelope(kind="goal.capture", origin="phone", ts=clk(),
                           payload={"text": "kal gym jana hai pakka"}
                           ).to_extra())
        texts = [g.text for g in store.all()]
        assert "rahul ko follow up" in texts
        assert "kal gym jana hai pakka" in texts
        assert all(g.source == "phone" for g in store.all())

    def test_ttl_and_dedupe_drops(self, tmp_path):
        r, store, clk = _router(tmp_path)
        stale = Envelope(kind="goal.capture", origin="phone",
                         ts=clk() - 999, ttl_s=120,
                         payload={"text": "stale goal"})
        assert r.inbound(stale.to_extra()) is None
        fresh = Envelope(kind="goal.capture", origin="phone", ts=clk(),
                         payload={"text": "fresh goal"})
        assert r.inbound(fresh.to_extra()) is not None
        assert r.inbound(fresh.to_extra()) is None        # same id → dropped
        assert len(store.all()) == 1

    def test_mem_request_triggers_slice_push(self, tmp_path):
        send = _Send()
        r, _, clk = _router(tmp_path, send=send,
                            mem=lambda: {"facts": ["sara is my sister"],
                                         "ver": 1})
        r.inbound(Envelope(kind="mem.request", origin="phone",
                           ts=clk()).to_extra())
        assert len(send.sent) == 1
        assert send.sent[0]["kind"] == "mem.slice"
        assert send.sent[0]["payload"]["facts"] == ["sara is my sister"]

    def test_empty_slice_not_pushed(self, tmp_path):
        send = _Send()
        r, _, _ = _router(tmp_path, send=send,
                          mem=lambda: {"facts": [], "ver": 1})
        assert r.push_memory_slice() is False
        assert send.sent == []


# ── reply routing ────────────────────────────────────────────────────── #

class TestRouteReply:
    def test_phone_active_sends_envelope(self, tmp_path):
        send = _Send()
        r, _, clk = _router(tmp_path, send=send)
        r.registry.beat("phone", "active")
        assert r.route_reply("Sir, retrain due hai.",
                             reason="initiative") == "phone"
        env = send.sent[0]
        assert env["kind"] == "reply.route"
        assert env["payload"]["reason"] == "initiative"

    def test_laptop_active_speaks_locally(self, tmp_path):
        spoken = []
        send = _Send()
        r, _, _ = _router(tmp_path, send=send, speak=spoken.append)
        r.registry.beat("laptop", "active")
        assert r.route_reply("hello") == "laptop"
        assert spoken == ["hello"] and send.sent == []

    def test_phone_send_failure_falls_back_to_laptop(self, tmp_path):
        spoken = []
        r, _, _ = _router(tmp_path, send=_Send(ok=False),
                          speak=spoken.append)
        r.registry.beat("phone", "active")
        assert r.route_reply("important ask") == "laptop"
        assert spoken == ["important ask"]

    def test_no_send_fn_defaults_laptop(self, tmp_path):
        r, _, _ = _router(tmp_path)
        r.registry.beat("phone", "active")
        assert r.route_reply("x") == "laptop"

    def test_phone_route_fires_push_nudge(self, tmp_path):
        pushes = []
        send = _Send()
        r, _, _ = _router(tmp_path, send=send)
        r.push_fn = lambda title, body: pushes.append((title, body)) or True
        r.registry.beat("phone", "active")
        assert r.route_reply("Sir, retrain due hai.") == "phone"
        assert pushes == [("AERIS", "Sir, retrain due hai.")]

    def test_laptop_route_never_pushes(self, tmp_path):
        pushes = []
        r, _, _ = _router(tmp_path, speak=lambda t: None)
        r.push_fn = lambda *a: pushes.append(a)
        r.registry.beat("laptop", "active")
        r.route_reply("hello")
        assert pushes == []

    def test_push_failure_still_routes_phone(self, tmp_path):
        send = _Send()
        r, _, _ = _router(tmp_path, send=send)
        def _boom(*a):
            raise RuntimeError("fcm down")
        r.push_fn = _boom
        r.registry.beat("phone", "active")
        assert r.route_reply("ask") == "phone"     # push is best-effort only


# ── memory slice ─────────────────────────────────────────────────────── #

class TestMemorySlice:
    def test_kg_triples_capped_and_formatted(self, monkeypatch):
        import core.kg_memory as kg

        class _FakeKG:
            def all_triples(self):
                return [{"s": f"s{i}", "p": "is", "o": f"o{i}",
                         "raw": f"s{i} is o{i}" if i % 2 else ""}
                        for i in range(60)]
        monkeypatch.setattr(kg, "get_kg", lambda: _FakeKG())
        out = memory_slice(k=40)
        assert len(out["facts"]) == 40
        assert out["facts"][-1] == "s59 is o59"       # raw preferred
        assert out["facts"][-2] == "s58 is o58"       # s-p-o fallback

    def test_kg_unavailable_is_empty_not_crash(self, monkeypatch):
        import core.kg_memory as kg
        def _boom():
            raise RuntimeError("no kg")
        monkeypatch.setattr(kg, "get_kg", _boom)
        assert memory_slice()["facts"] == []
