"""Continuity — ek mind, do body (docs/CONTINUITY_ARCHITECTURE.md).

Laptop is the mind, the phone is a second body, the E2E bridge is the
spinal cord. This module is the nervous system's switchboard:

* **Envelope** — the typed message layer that rides INSIDE the existing
  bridge payload (``extra.env``), so nothing about the transport or the
  old phone app changes. TTL'd + deduped.
* **DeviceRegistry** — presence arbitration: which body is the user at
  right now? Laptop-authoritative, fail-safe default = laptop.
* **ContinuityRouter** — inbound envelope dispatch (presence beats, phone
  goal capture, memory requests) and ``route_reply`` — the one decision
  point for "is jawab ko kis body par bolna hai".
* **memory_slice** — the small, privacy-tiered set of personal facts the
  phone's Tier-3 (Gemini) brain may hold: KG triples only, never episodic
  chat.

Everything is injected (send_fn, goal store, registry, clock) so the whole
module unit-tests in the fast lane with a fake bridge. Wiring into the real
bridge/engine happens in ``core/cloud_bridge.py`` / ``core/main_engine.py``
(phase C2), never here.
"""

from __future__ import annotations

import logging
import secrets as _secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)

ENVELOPE_VERSION = 1

KINDS = ("presence.beat", "goal.capture", "reply.route",
         "mem.slice", "mem.request")

# Presence arbitration constants (§4 of the architecture doc).
STALE_BEAT_S = 180.0        # beats older than this don't count at all
LAPTOP_PRIORITY_S = 120.0   # laptop touched this recently → laptop wins

_DEDUPE_CAPACITY = 128
_DEFAULT_TTL_S = 120.0
_MEM_SLICE_K = 40


# ── envelope ─────────────────────────────────────────────────────────── #

@dataclass
class Envelope:
    kind: str
    payload: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: "c_" + _secrets.token_hex(4))
    origin: str = "laptop"
    ts: float = field(default_factory=time.time)
    ttl_s: float = _DEFAULT_TTL_S
    v: int = ENVELOPE_VERSION

    def to_extra(self) -> dict:
        """The dict that rides in the bridge message's ``extra['env']``."""
        return {"v": self.v, "kind": self.kind, "id": self.id,
                "origin": self.origin, "ts": self.ts, "ttl_s": self.ttl_s,
                "payload": dict(self.payload)}

    @staticmethod
    def from_extra(d: object) -> Optional["Envelope"]:
        """Tolerant parse — None for anything malformed (never raises)."""
        if not isinstance(d, dict):
            return None
        kind = d.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            return None
        try:
            payload = d.get("payload")
            return Envelope(
                kind=kind,
                payload=dict(payload) if isinstance(payload, dict) else {},
                id=str(d.get("id") or ""),
                origin=str(d.get("origin") or "phone"),
                ts=float(d.get("ts") or 0.0),
                ttl_s=float(d.get("ttl_s") or _DEFAULT_TTL_S),
                v=int(d.get("v") or ENVELOPE_VERSION),
            )
        except Exception:
            return None

    def expired(self, now: Optional[float] = None) -> bool:
        t = time.time() if now is None else now
        # Future-dated (clock skew) tolerated up to the same window.
        return abs(t - self.ts) > self.ttl_s


# ── presence arbitration ─────────────────────────────────────────────── #

class DeviceRegistry:
    """Which body is the user at? Laptop-authoritative, injectable clock.

    Rules (in order):
      1. Laptop active within LAPTOP_PRIORITY_S → laptop. (User is HERE —
         a push to the phone in your pocket helps nobody.)
      2. Else phone active within STALE_BEAT_S → phone.
      3. Else → laptop (TTS always exists there; fail-safe default).
    """

    def __init__(self, *, now_fn: Callable[[], float] = time.time):
        self._now = now_fn
        self._lock = threading.Lock()
        self._beats: dict[str, tuple[str, float]] = {}   # device → (state, ts)

    def beat(self, device: str, state: str,
             ts: Optional[float] = None) -> None:
        if device not in ("laptop", "phone"):
            return
        if state not in ("active", "idle", "away"):
            state = "idle"
        with self._lock:
            self._beats[device] = (state, self._now() if ts is None else ts)

    def _fresh_active(self, device: str, now: float, window: float) -> bool:
        state, ts = self._beats.get(device, ("away", 0.0))
        return state == "active" and (now - ts) <= window

    def active_device(self, now: Optional[float] = None) -> str:
        t = self._now() if now is None else now
        with self._lock:
            if self._fresh_active("laptop", t, LAPTOP_PRIORITY_S):
                return "laptop"
            if self._fresh_active("phone", t, STALE_BEAT_S):
                return "phone"
            return "laptop"

    def snapshot(self) -> dict:
        with self._lock:
            return {d: {"state": s, "ts": ts}
                    for d, (s, ts) in self._beats.items()}


# ── the router ───────────────────────────────────────────────────────── #

class ContinuityRouter:
    """Inbound envelope dispatch + the route_reply decision.

    ``send_fn(extra_env: dict) -> bool`` delivers an envelope to the phone
    (C2 wires it to ``bridge.send_to_phone`` with the event wrapper); None
    means "no phone link" and every route falls back to the laptop.
    ``speak_fn(text)`` is the laptop's own voice (None = caller speaks).
    """

    def __init__(self,
                 send_fn: Optional[Callable[[dict], bool]] = None,
                 *,
                 goal_store=None,
                 registry: Optional[DeviceRegistry] = None,
                 speak_fn: Optional[Callable[[str], None]] = None,
                 push_fn: Optional[Callable[[str, str], bool]] = None,
                 memory_slice_fn: Optional[Callable[[], dict]] = None,
                 now_fn: Callable[[], float] = time.time):
        self.send_fn = send_fn
        self.registry = registry or DeviceRegistry(now_fn=now_fn)
        self.speak_fn = speak_fn
        # push_fn(title, body): FCM nudge so a routed reply still reaches a
        # backgrounded phone app (the mailbox doc alone needs the app open).
        self.push_fn = push_fn
        self._goal_store = goal_store
        self._memory_slice_fn = memory_slice_fn
        self._now = now_fn
        self._seen: "OrderedDict[str, None]" = OrderedDict()
        self._lock = threading.Lock()

    # -- outbound ------------------------------------------------------ #

    def outbound(self, kind: str, payload: dict,
                 ttl_s: float = _DEFAULT_TTL_S) -> Optional[Envelope]:
        """Build + send an envelope to the phone. None when unsendable."""
        env = Envelope(kind=kind, payload=payload, origin="laptop",
                       ts=self._now(), ttl_s=ttl_s)
        if self.send_fn is None:
            log.debug("[continuity] no send_fn — %s dropped", kind)
            return None
        try:
            if self.send_fn(env.to_extra()):
                return env
        except Exception as e:
            log.warning("[continuity] send failed for %s: %s", kind, e)
        return None

    # -- inbound ------------------------------------------------------- #

    def inbound(self, extra_env: object) -> Optional[str]:
        """Dispatch one received envelope. Returns an ack/reply text when
        the sender's body should speak something, else None."""
        env = Envelope.from_extra(extra_env)
        if env is None:
            return None
        if env.expired(self._now()):
            log.debug("[continuity] expired %s dropped", env.kind)
            return None
        if env.id and self._duplicate(env.id):
            return None

        if env.kind == "presence.beat":
            state = str(env.payload.get("state") or "idle")
            # Beat timestamps use OUR clock, not the sender's — phone clock
            # skew must not make a live phone look stale.
            self.registry.beat(env.origin, state)
            return None

        if env.kind == "goal.capture":
            return self._capture_goal(str(env.payload.get("text") or ""))

        if env.kind == "mem.request":
            self.push_memory_slice()
            return None

        # reply.route / mem.slice are phone-side kinds; the mind ignores
        # its own medicine.
        return None

    def _duplicate(self, env_id: str) -> bool:
        with self._lock:
            if env_id in self._seen:
                return True
            self._seen[env_id] = None
            while len(self._seen) > _DEDUPE_CAPACITY:
                self._seen.popitem(last=False)
            return False

    def _capture_goal(self, text: str) -> Optional[str]:
        text = text.strip()
        if not text:
            return None
        store = self._goal_store
        if store is None:
            try:
                from core.goal_system import get_goal_store
                store = get_goal_store()
            except Exception as e:
                log.warning("[continuity] goal store unavailable: %s", e)
                return None
        try:
            g = store.capture(text, source="phone")
            if g is None:
                # The phone's regex already decided this is a goal; a port
                # drift on the laptop must not silently drop the intention.
                from core.goal_system import Goal
                g = store.add(Goal(text=text, source="phone"))
            from core.goal_system import capture_ack
            return capture_ack(g)
        except Exception as e:
            log.warning("[continuity] goal capture failed: %s", e)
            return None

    # -- reply routing (§5a) ------------------------------------------- #

    def route_reply(self, text: str, reason: str = "reply") -> str:
        """Deliver a proactive utterance to the ACTIVE body.

        Returns "phone" when it went out as an envelope, "laptop" when the
        laptop spoke (or should speak — speak_fn optional). Phone-send
        failure falls back to the laptop so nothing is ever lost silently.
        """
        text = (text or "").strip()
        if not text:
            return "laptop"
        if self.registry.active_device() == "phone" and self.send_fn is not None:
            if self.outbound("reply.route",
                             {"text": text, "reason": reason}) is not None:
                if self.push_fn is not None:
                    try:
                        self.push_fn("AERIS", text[:120])
                    except Exception as e:
                        log.debug("[continuity] push failed: %s", e)
                return "phone"
        if self.speak_fn is not None:
            try:
                self.speak_fn(text)
            except Exception as e:
                log.warning("[continuity] laptop speak failed: %s", e)
        return "laptop"

    # -- memory slice -------------------------------------------------- #

    def push_memory_slice(self) -> bool:
        """Send the phone a fresh personal-facts slice (mem.slice)."""
        slice_fn = self._memory_slice_fn or memory_slice
        try:
            data = slice_fn()
        except Exception as e:
            log.warning("[continuity] memory slice failed: %s", e)
            return False
        if not data.get("facts"):
            return False
        return self.outbound("mem.slice", data, ttl_s=3600.0) is not None


def memory_slice(k: int = _MEM_SLICE_K) -> dict:
    """Personal facts the phone may hold: KG triples only (facts and
    preferences by construction — fact_bridge / preference_learner feed
    the KG). NEVER episodic chat, screenshots, or ledger entries."""
    try:
        from core.kg_memory import get_kg
        triples = get_kg().all_triples()
    except Exception as e:
        log.debug("[continuity] KG unavailable: %s", e)
        return {"facts": [], "ver": int(time.time())}
    facts = []
    for t in triples[-k:]:                     # newest-added last → keep tail
        raw = (t.get("raw") or "").strip()
        line = raw or f"{t.get('s', '')} {t.get('p', '')} {t.get('o', '')}".strip()
        if line:
            facts.append(line)
    return {"facts": facts, "ver": int(time.time())}


# ── singleton (wired lazily; C2 injects the real bridge send) ────────── #

_ROUTER: Optional[ContinuityRouter] = None
_ROUTER_LOCK = threading.Lock()


def get_router() -> ContinuityRouter:
    global _ROUTER
    with _ROUTER_LOCK:
        if _ROUTER is None:
            _ROUTER = ContinuityRouter(send_fn=_bridge_send,
                                       push_fn=_bridge_push)
        return _ROUTER


def _bridge_push(title: str, body: str) -> bool:
    """Best-effort FCM nudge for routed replies (phone may be backgrounded)."""
    try:
        from core.cloud_bridge import get_bridge
        return bool(get_bridge().send_push(title, body))
    except Exception as e:
        log.debug("[continuity] bridge push unavailable: %s", e)
        return False


def _bridge_send(extra_env: dict) -> bool:
    """Default send_fn: wrap the envelope in a standard bridge message.

    Old phone builds see an unknown 'event' and ignore it — back-compat by
    construction. Import is lazy so tests never touch Firebase."""
    try:
        from core.cloud_bridge import get_bridge
        b = get_bridge()
        return bool(b.send_to_phone({
            "id": extra_env.get("id", ""),
            "type": "event",
            "text": "",
            "reply_to": None,
            "extra": {"env": extra_env},
        }))
    except Exception as e:
        log.debug("[continuity] bridge send unavailable: %s", e)
        return False
