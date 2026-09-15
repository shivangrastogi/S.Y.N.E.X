"""Reading `event:*` messages off the service bus, tolerantly.

Every GUI-side seam needs the same three lines: pull the kind, pull the
payload, skip anything malformed. `remote_brain.extract_offers` and
`remote_vision.extract_gestures` each grew their own copy, and voice was about
to make a third — at which point they stop being coincidence and start being a
place where one gets a fix the others don't.

Tolerance is the whole reason this is fiddly enough to share. These messages
are produced by a **separate process that may be a different build**, so a
missing key, a `None` payload or an unexpected shape is a normal event, not a
bug: it gets skipped. Raising here would take out a poller on the GUI thread
because a child process was mid-upgrade.

Two shapes are accepted for the same reason — `Msg` objects from
`core.service_bus`, and plain dicts, which is what tests and any future
JSON-over-stdio transport produce.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


def _field(ev: Any, name: str) -> Optional[Any]:
    v = getattr(ev, name, None)
    if v is None and isinstance(ev, dict):
        v = ev.get(name)
    return v


def payloads(events, *kinds: str) -> list:
    """Payload dicts of every event matching ``kinds``, in arrival order.

    Each name is matched bare and `event:`-prefixed — the bus prefixes
    whatever a service emits, but tests and direct callers use the bare form,
    and a seam should not care which it is handed.
    """
    wanted = set()
    for k in kinds:
        wanted.add(k)
        wanted.add(k if k.startswith("event:") else f"event:{k}")
    out = []
    for ev in events or []:
        try:
            if _field(ev, "kind") not in wanted:
                continue
            payload = _field(ev, "payload")
            if isinstance(payload, dict):
                out.append(payload)
        except Exception as e:      # one bad event must never kill the drain
            log.debug("[bus_events] skipping malformed event %r: %s", ev, e)
    return out


def texts(events, kind: str, field: str = "text") -> list:
    """The non-empty ``field`` of every matching event — the common case."""
    out = []
    for p in payloads(events, kind):
        try:
            v = (p.get(field) or "").strip()
        except Exception:
            continue
        if v:
            out.append(v)
    return out
