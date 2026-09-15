"""Brain service — the full NLU + skills engine, ready to run in its OWN process
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1 keystone).

``brain_handler_factory(emit)`` is a top-level, emit-aware factory (picklable
for Windows spawn): a ``ServiceProxy`` runs it and ``JarvisMainEngine`` — torch
+ encoder + spaCy + all skills — is built INSIDE the child. The GUI sends
``utterance`` requests over the bus and gets ``reply`` back; a background ticker
pushes proactive ``event:offer`` messages (the initiative engine's "sleep mode
karu?"). None of that heavy native stack ever touches the GUI's heap.

Handler logic, the proactive tick, and engine construction are all separated
(injection) so everything is unit-tested with fakes — no model load, no spawn —
while the real spawn is a single slow smoke test.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)


def _default_engine():
    # Headless: no STT/TTS/GUI in the brain process — pure text pipeline.
    # enable_scheduler=False is important: the brain_service TICKER
    # (run_ticker_pass + _default_initiative_tick) is the ONE consumer of
    # proactive offers, pushing them to the GUI over the bus. If the engine
    # ALSO ran its internal initiative scheduler, both would call
    # initiative_engine.tick() and offers would randomly vanish into this
    # process's SKIP tts instead of reaching the user. One consumer only.
    from core.main_engine import JarvisMainEngine
    return JarvisMainEngine(stt="SKIP", tts="SKIP", verbose=False,
                            enable_scheduler=False)


def _default_initiative_tick() -> list:
    """Surface proactive offers from the initiative engine as plain dicts."""
    try:
        from core.initiative_engine import get_engine
        out = []
        for ini in get_engine().tick():
            sid = getattr(ini, "source_id", "") or ""
            offer = {"text": getattr(ini, "text", ""),
                     "kind": getattr(ini, "kind", "")}
            # mode_suggest carries an on_yes so the GUI can act on "haan"
            if getattr(ini, "kind", "") == "mode_suggest" and ":" in sid:
                offer["on_yes"] = {"skill": "activate_mode",
                                   "slots": {"raw_text": sid.split(":", 1)[1]}}
            out.append(offer)
        return out
    except Exception as e:  # never let a tick failure crash the service
        log.debug("[brain_service] initiative tick failed: %s", e)
        return []


def run_ticker_pass(tick_fn: Callable[[], list],
                    emit: Callable[[str, dict], None],
                    park: Optional[Callable[[str, dict], None]] = None) -> int:
    """One proactive pass: pull offers from ``tick_fn`` and ``emit`` each.
    Returns how many were emitted. Pure + testable.

    ``park(skill, slots)`` — when given, an offer carrying ``on_yes`` is also
    parked so the user's next turn can accept it with "haan". Without this the
    split brain surfaced offers the user could see but could not act on: the
    in-process path parks ``engine._pending_offer`` inside
    ``_surface_initiatives``, which this ticker bypasses entirely by calling
    ``initiative_engine.tick()`` directly. Last offer wins, matching the
    in-process loop, which also overwrites per surfaced initiative.
    """
    n = 0
    try:
        offers = tick_fn() or []
    except Exception:
        return 0
    for offer in offers:
        if isinstance(offer, dict) and offer.get("text"):
            emit("offer", offer)
            n += 1
            if park is not None:
                on_yes = offer.get("on_yes")
                if isinstance(on_yes, dict) and on_yes.get("skill"):
                    try:
                        park(on_yes["skill"], on_yes.get("slots") or {})
                    except Exception as e:
                        log.debug("[brain_service] parking offer failed: %s", e)
    return n


def make_brain_handler(engine_builder: Optional[Callable] = None,
                       emit: Optional[Callable[[str, dict], None]] = None,
                       initiative_tick: Optional[Callable[[], list]] = None,
                       tick_interval: float = 60.0,
                       start_ticker: bool = True):
    """Build the request handler. ``engine_builder() -> engine`` (injected in
    tests; defaults to the real headless JarvisMainEngine). If ``emit`` is
    given, a daemon ticker pushes proactive offers every ``tick_interval`` s."""
    engine = (engine_builder or _default_engine)()

    if emit is not None and start_ticker:
        tick_fn = initiative_tick or _default_initiative_tick
        stop = threading.Event()

        def _park(skill: str, slots: dict) -> None:
            """Arm the child engine's one-turn "haan" gate for this offer.

            A plain attribute assignment, from the ticker thread, exactly as
            the in-process path does it from the scheduler thread — the
            engine's own `_pt_lock` covers the turn that consumes it, and
            taking that lock here would let a tick block on a long turn.
            """
            engine._pending_offer = (skill, slots)

        def _loop():
            while not stop.wait(tick_interval):
                run_ticker_pass(tick_fn, emit, park=_park)

        threading.Thread(target=_loop, name="brain-initiative-ticker",
                         daemon=True).start()

    def handler(kind: str, payload: dict) -> dict:
        if kind == "ping":
            return {"pong": True}
        if kind == "utterance":
            text = (payload or {}).get("text", "") or ""
            # Clear the side-channel first (like the in-process BrainWorker) so a
            # chat/fallback turn never reports the PREVIOUS turn's dispatch.
            try:
                engine.last_dispatch = None
            except Exception:
                pass
            try:
                reply = engine.process_text(text) or ""
            except Exception as e:
                return {"reply": "", "error": repr(e)}
            ld = getattr(engine, "last_dispatch", None)
            dispatch = ld if isinstance(ld, dict) else None
            # Forward the FULL dispatch (intent/confidence/action/latency_ms) so
            # the split-brain GUI chip matches in-process instead of "general".
            # Keep top-level "skill" for back-compat with existing callers/tests.
            skill = dispatch.get("skill") if dispatch else None
            return {"reply": reply, "skill": skill, "dispatch": dispatch}
        # ── hibernation support (§4.2) ───────────────────────────────
        # The child owns the only copy of the conversation, so retiring it
        # while idle needs these two before/after the process is replaced.
        if kind == "snapshot":
            from core.brain_snapshot import capture
            return {"state": capture(engine)}
        if kind == "restore":
            from core.brain_snapshot import restore
            done = restore(engine, (payload or {}).get("state"))
            return {"restored": done}
        return {"error": f"unknown kind {kind!r}"}

    return handler


def brain_handler_factory(emit=None):
    """Top-level emit-aware factory for ServiceProxy(spawn). Builds the REAL
    brain and (if the bus supplied ``emit``) the proactive ticker."""
    return make_brain_handler(emit=emit)
