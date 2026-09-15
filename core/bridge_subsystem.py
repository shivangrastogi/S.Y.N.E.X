"""The phone bridge as a supervised subsystem.

`core/cloud_bridge.py` already has the lifecycle verbs — `start()`, `stop()`,
`status()`. What it never had is a *policy*: who calls them, what to do when
`start` says no, and how anyone finds out that a bridge which started fine has
quietly stopped receiving. This module is that policy, kept out of
`cloud_bridge` so the transport stays a transport.

Why `start()` returning False is not one thing
----------------------------------------------
`CloudBridge.start()` reports failure as `(False, reason)` — one channel for
five very different situations. Treating them alike is why the bridge either
retried things that could never succeed, or gave up on things that would have
worked ten seconds later. The classifier below splits them the way
`subsystem_registry` splits states:

  ``RETRY``     the brain hook is not wired yet (boot ordering — this
                resolves itself), or `_connect()` failed because the network
                was down or Firebase was unreachable. A race. Try again.

  ``UNAVAILABLE`` no service-account key, not paired yet, or
                `AERIS_DISABLE_BRIDGE` is set. The precondition is absent.
                Retrying cannot conjure a pairing, and logging an error for a
                user who simply has not paired their phone is noise — this is
                DISABLED, not FAILED. Pairing (`phone pair karo`) calls
                `rearm()` and it comes straight back.

  ``FAILED``    anything unrecognised. Loud, once, with the reason.

Matching on reason strings is admittedly brittle, so the mapping is table-
driven and pinned by tests against the actual strings `cloud_bridge.start`
returns; if one is reworded, a test fails rather than the bridge silently
falling into the wrong bucket.

The silent-death problem
------------------------
The sharper bug this closes is not at boot. `start()` installs a Firestore
`on_snapshot` listener owned by the SDK's own thread, and sets `_started =
True`. If that listener dies — token expiry, a dropped socket, the laptop
sleeping — nothing flips the flag back. `status()["listening"]` keeps saying
True and the bridge keeps looking healthy while receiving nothing, until the
user notices their phone has stopped working and restarts AERIS.

`check_liveness()` compares the SDK's own view of the subscription against
that flag. When they disagree, the bridge is marked DEGRADED and the registry
reconnects it on its normal backoff. Ridden from the same idle tick as every
other subsystem sweep — no new thread.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from core.subsystem_registry import (
    SubsystemRegistry,
    SubsystemUnavailable,
    get_registry,
)

log = logging.getLogger(__name__)

#: Registry key. Human-readable — it is shown in the log panel and at
#: /subsystems.
NAME = "phone bridge"

# Two reconnects, spaced widely: a network blip clears in seconds, but the
# bridge is not on any critical path, so there is no reason to be eager about
# it. 30 s then 60 s.
_MAX_RETRIES = 2
_BACKOFF_S = 30.0

#: reason-substring → category. Order matters: first match wins, so put the
#: specific strings above anything that could also match them.
_UNAVAILABLE_MARKERS = (
    "bridge disabled",          # AERIS_DISABLE_BRIDGE
    "not paired",               # no pairing yet — needs `phone pair karo`
    "service-account key missing",
    "firebase-admin not importable",
)
_RETRY_MARKERS = (
    "brain hook not wired",     # boot ordering — resolves itself
    "connect failed",
    "unreachable",
    "timeout",
    "network",
)


def classify(reason: str) -> str:
    """``"unavailable"`` | ``"retry"`` | ``"failed"`` for a start() reason."""
    low = (reason or "").strip().lower()
    if not low:
        return "failed"
    for marker in _UNAVAILABLE_MARKERS:
        if marker in low:
            return "unavailable"
    for marker in _RETRY_MARKERS:
        if marker in low:
            return "retry"
    return "failed"


def _bridge():
    # Imported lazily: `cloud_bridge` pulls firebase-admin on first real use,
    # and a machine with no pairing should never pay for that import just
    # because this module was loaded.
    from core.cloud_bridge import get_bridge
    return get_bridge()


def make_installer(process_fn: Optional[Callable[[str], str]] = None
                   ) -> Callable[[], None]:
    """Build the install callable the registry will run.

    Raises ``SubsystemUnavailable`` for absent preconditions and a plain
    ``RuntimeError`` for retryable/unknown failures — which is exactly the
    vocabulary ``SubsystemRegistry.boot`` reads.
    """
    def _install() -> None:
        ok, reason = _bridge().start(process_fn)
        if ok:
            return
        kind = classify(reason)
        if kind == "unavailable":
            raise SubsystemUnavailable(reason)
        # RETRY and FAILED are the same exception; which one the subsystem
        # lands in is decided by whether it has retry budget left, which is
        # the registry's job, not ours. The distinction still matters for the
        # log line, so it goes there.
        log.info("[bridge] start failed (%s): %s", kind, reason)
        raise RuntimeError(reason)

    return _install


def _teardown() -> None:
    """Stop before a reconnect: `start()` is idempotent and returns
    "already running" while `_started` is True, so a reconnect that skipped
    this would be a no-op that reported success."""
    _bridge().stop()


def register(registry: Optional[SubsystemRegistry] = None,
             process_fn: Optional[Callable[[str], str]] = None
             ) -> SubsystemRegistry:
    """Register the bridge as a supervised subsystem. Idempotent."""
    reg = registry or get_registry()
    reg.register(NAME, make_installer(process_fn), teardown=_teardown,
                 max_retries=_MAX_RETRIES, backoff_s=_BACKOFF_S)
    return reg


def check_liveness(registry: Optional[SubsystemRegistry] = None) -> bool:
    """Detect a listener that died without telling anyone.

    Returns True if the bridge is believed live. Marks it DEGRADED (which
    schedules a reconnect) when the bridge thinks it is listening but the
    Firestore subscription underneath is gone.

    Cheap by design — attribute reads, no network — because this runs on the
    GUI's 5 s idle tick. Never raises: a liveness probe that throws would be
    a worse failure than the one it is looking for.
    """
    reg = registry or get_registry()
    rec = reg.get(NAME)
    if rec is None or not rec.healthy:
        return False           # not up; not this function's problem
    try:
        b = _bridge()
        if not getattr(b, "_started", False):
            # Something called stop() behind the registry's back (a pairing
            # rotation, a skill). Not an error, but the registry's OK is now
            # a lie, so correct it.
            reg.mark_degraded(NAME, "bridge stopped outside the supervisor")
            return False
        watch = getattr(b, "_watch", None)
        if watch is None:
            reg.mark_degraded(NAME, "Firestore listener gone")
            return False
        # The SDK's Watch exposes its own liveness. Attribute names differ
        # across firebase-admin versions, so absence is treated as "no
        # opinion" rather than "dead" — a false reconnect every 5 s would be
        # far worse than a missed one.
        for attr in ("_closed", "closed"):
            if getattr(watch, attr, False):
                reg.mark_degraded(NAME, "Firestore listener closed")
                return False
        return True
    except Exception as e:  # noqa: BLE001
        log.debug("[bridge] liveness probe failed (ignored): %s", e)
        return True


def rearm(registry: Optional[SubsystemRegistry] = None) -> bool:
    """The precondition is now met — try again.

    Call after pairing, or after the user drops in a service-account key. An
    UNAVAILABLE bridge is DISABLED and therefore invisible to retries by
    design; this is the door back in. Also clears any earlier FAILED verdict
    so a fresh pairing gets a full retry budget rather than inheriting a bad
    session's history.
    """
    reg = registry or get_registry()
    if reg.get(NAME) is None:
        register(reg)
    reg.enable(NAME)
    reg.reset(NAME)
    return reg.boot(NAME)
