"""Local service bus — the foundation of the process-isolation architecture
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1).

Runs a "service" (e.g. the Brain: torch + sentence-transformers + skills) in
its OWN child process, so its native heap is isolated from the GUI's. A native
fault in the service can no longer corrupt the GUI process — the supervisor
just restarts the service. Communication is plain ``multiprocessing`` queues
(zero extra deps, offline, Windows-spawn safe).

Contract:
  * A *service* is built by a top-level ``handler_factory() -> handler`` where
    ``handler(kind: str, payload: dict) -> dict`` answers requests. The factory
    runs INSIDE the child, so heavy imports (torch) never touch the parent.
  * ``ServiceProxy`` (parent side) does request/response with correlation ids
    and a timeout, streams unsolicited events, and can stop/restart the child.

Design notes:
  * Replies that don't match the awaited id are buffered (out-of-order safe).
  * Events (kind starting with ``event:``) are delivered to an event queue the
    caller polls — this is how a proactive service pushes "sleep mode karu?".
  * Everything is best-effort and never raises across the boundary uncaught.
"""
from __future__ import annotations

import inspect
import logging
import multiprocessing as mp
import queue as _queue
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_STOP = "__stop__"
_FATAL = "__fatal__"
_READY = "__ready__"


@dataclass
class Msg:
    kind: str
    id: str = ""
    payload: dict = field(default_factory=dict)
    ok: bool = True
    error: str = ""


def _wants_emit(fn: Callable) -> bool:
    """True if the factory accepts an ``emit`` argument (proactive services)."""
    try:
        return len(inspect.signature(fn).parameters) >= 1
    except (ValueError, TypeError):
        return False


def _service_loop(handler_factory: Callable[..., Callable[[str, dict], dict]],
                  req_q: "mp.Queue", rep_q: "mp.Queue") -> None:
    """Child-process entry point. Builds the handler, then serves requests.

    An emit-aware factory (``handler_factory(emit)``) gets an ``emit(kind,
    payload)`` callback it can call from a background thread to push
    unsolicited ``event:*`` messages (e.g. a proactive "sleep mode karu?").
    """
    def emit(event_kind: str, payload: Optional[dict] = None) -> None:
        try:
            rep_q.put(Msg(kind=f"event:{event_kind}", payload=payload or {}))
        except Exception:
            pass

    try:
        handler = (handler_factory(emit) if _wants_emit(handler_factory)
                   else handler_factory())
    except Exception as e:  # heavy init failed → tell the parent, exit
        try:
            rep_q.put(Msg(kind=_FATAL, ok=False, error=f"init failed: {e!r}"))
        except Exception:
            pass
        return
    try:
        rep_q.put(Msg(kind=_READY))
    except Exception:
        pass
    while True:
        try:
            msg = req_q.get(timeout=0.25)
        except _queue.Empty:
            continue
        except (EOFError, OSError):
            break
        if msg is None or getattr(msg, "kind", None) == _STOP:
            break
        try:
            result = handler(msg.kind, dict(msg.payload or {}))
            if not isinstance(result, dict):
                result = {"result": result}
            rep_q.put(Msg(kind=msg.kind, id=msg.id, payload=result, ok=True))
        except Exception as e:
            rep_q.put(Msg(kind=msg.kind, id=msg.id, ok=False, error=repr(e)))


class ServiceProxy:
    """Parent-side handle to a service running in a child process."""

    def __init__(self, name: str,
                 handler_factory: Callable[[], Callable[[str, dict], dict]]):
        self.name = name
        self._factory = handler_factory
        self._ctx = mp.get_context("spawn")
        self._req_q: Optional[mp.Queue] = None
        self._rep_q: Optional[mp.Queue] = None
        self._proc: Optional[mp.Process] = None
        self._reply_buf: dict[str, Msg] = {}
        self._events: list[Msg] = []
        self._ready = False

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self, ready_timeout: float = 30.0) -> bool:
        self._req_q = self._ctx.Queue()
        self._rep_q = self._ctx.Queue()
        self._reply_buf.clear()
        self._events.clear()
        self._ready = False
        self._proc = self._ctx.Process(
            target=_service_loop, args=(self._factory, self._req_q, self._rep_q),
            name=f"svc-{self.name}", daemon=True)
        self._proc.start()
        # wait for the READY (or FATAL) handshake so callers know it's usable
        deadline = time.time() + ready_timeout
        while time.time() < deadline:
            m = self._drain_once(timeout=deadline - time.time())
            if m is None:
                continue
            if m.kind == _READY:
                self._ready = True
                return True
            if m.kind == _FATAL:
                log.warning("[bus] %s failed to start: %s", self.name, m.error)
                return False
        log.warning("[bus] %s start timed out", self.name)
        return False

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    def is_ready(self) -> bool:
        return self._ready and self.is_alive()

    def stop(self, timeout: float = 3.0) -> None:
        try:
            if self._req_q is not None:
                self._req_q.put(Msg(kind=_STOP))
        except Exception:
            pass
        if self._proc is not None:
            self._proc.join(timeout)
            if self._proc.is_alive():
                self._proc.terminate()
                self._proc.join(1.0)
        self._ready = False

    def restart(self, ready_timeout: float = 30.0) -> bool:
        self.stop()
        return self.start(ready_timeout=ready_timeout)

    # ── messaging ────────────────────────────────────────────────────
    def _drain_once(self, timeout: float = 0.0) -> Optional[Msg]:
        """Pull one message off the reply queue; file events/replies away."""
        if self._rep_q is None:
            return None
        try:
            m: Msg = self._rep_q.get(timeout=max(0.0, timeout))
        except (_queue.Empty, ValueError):
            return None
        except (EOFError, OSError):
            return None
        if m.kind in (_READY, _FATAL):
            return m
        if m.kind.startswith("event:"):
            self._events.append(m)
            return None
        if m.id:
            self._reply_buf[m.id] = m
        return m

    def request(self, kind: str, payload: Optional[dict] = None,
                timeout: float = 10.0) -> Msg:
        """Send a request, block for the correlated reply (or raise TimeoutError)."""
        if not self.is_alive():
            raise RuntimeError(f"{self.name} service is not running")
        mid = uuid.uuid4().hex
        self._req_q.put(Msg(kind=kind, id=mid, payload=payload or {}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            if mid in self._reply_buf:
                return self._reply_buf.pop(mid)
            self._drain_once(timeout=min(0.25, deadline - time.time()))
        raise TimeoutError(f"{self.name}.{kind} timed out after {timeout}s")

    def poll_events(self) -> list[Msg]:
        """Return (and clear) any unsolicited ``event:*`` messages queued."""
        # sweep the queue non-blockingly first
        while self._drain_once(timeout=0.0) is not None:
            pass
        out, self._events = self._events, []
        return out


# ── demo handlers (module-level so Windows 'spawn' can import them) ──────

def echo_handler_factory() -> Callable[[str, dict], dict]:
    def handler(kind: str, payload: dict) -> dict:
        if kind == "echo":
            return {"text": payload.get("text", "")}
        if kind == "boom":
            raise ValueError("intentional failure")
        return {"error": f"unknown kind {kind!r}"}
    return handler


def counting_handler_factory() -> Callable[[str, dict], dict]:
    state = {"n": 0}

    def handler(kind: str, payload: dict) -> dict:
        state["n"] += 1
        return {"count": state["n"], "kind": kind}
    return handler


def bad_init_factory() -> Callable[[str, dict], dict]:
    raise RuntimeError("cannot build service")


def emitting_handler_factory(emit):
    """Emit-aware demo: a 'fire' request pushes an unsolicited event:offer."""
    def handler(kind: str, payload: dict) -> dict:
        if kind == "fire":
            emit("offer", {"text": payload.get("text", "ping-offer")})
            return {"fired": True}
        if kind == "ping":
            return {"pong": True}
        return {"error": f"unknown kind {kind!r}"}
    return handler
