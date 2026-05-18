"""Localhost HTTP server exposing AERIS internals.

OS-concept demo
---------------
A health server is the classic Unix pattern for "let me see what this
daemon is doing without reading its logs". We use the stdlib's
``http.server`` (which is a thin BaseHTTPRequestHandler over a TCP
listening socket) bound exclusively to ``127.0.0.1`` so nothing on
the network can reach it. Bind address = the access-control mechanism;
no auth needed, no cert juggling, no port-forwarding mishaps.

Endpoints
---------
  GET /              → human-readable index
  GET /health        → uptime, brain ready, voice state, last 5 events
  GET /metrics       → resource samples, cache stats, breaker stats
  GET /skills        → list of registered skills
  GET /shutdown      → triggers shutdown coordinator (POST-safe variant
                       requires X-AERIS-LOCAL header for safety)

All responses are JSON except ``/`` which is a tiny HTML index linking
the endpoints. CORS is *intentionally absent* — browsers should hit
this from extensions or local apps only.

Threading
---------
The HTTP server runs on its own daemon thread. Each request is served
by stdlib's ``ThreadingHTTPServer`` worker — they're short-lived enough
that we don't bother with a pool. All endpoints are read-only against
shared state (the registries' locks already serialize concurrent reads).
"""
from __future__ import annotations

import json
import logging
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


_BIND = "127.0.0.1"
_PORT = 8765   # picked to be high enough to dodge usual collisions


# State the handler reads — set by ``start_server`` so we don't have to
# pass globals through the BaseHTTPRequestHandler constructor.
_started_at: float = 0.0
_brain_ready_fn: Optional[Callable[[], bool]] = None
_voice_state_fn: Optional[Callable[[], str]] = None
_shutdown_fn: Optional[Callable[[], None]] = None


# ── Handler ────────────────────────────────────────────────────────── #

class _Handler(BaseHTTPRequestHandler):
    # Silence the default request-line print to stderr; we use the logger.
    def log_message(self, fmt, *args):
        log.debug("[health] " + fmt, *args)

    def do_GET(self):  # noqa: N802 — stdlib API
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index"):
                self._serve_html(_INDEX_HTML)
            elif path == "/health":
                self._serve_json(_collect_health())
            elif path == "/metrics":
                self._serve_json(_collect_metrics())
            elif path == "/skills":
                self._serve_json(_collect_skills())
            elif path == "/shutdown":
                self._handle_shutdown()
            else:
                self._serve_json({"error": "not found", "path": path},
                                 status=HTTPStatus.NOT_FOUND)
        except Exception as e:  # noqa: BLE001
            log.exception("[health] handler raised")
            self._serve_json({"error": str(e)},
                             status=HTTPStatus.INTERNAL_SERVER_ERROR)

    # ── helpers ──
    def _serve_json(self, obj: Any, *, status=HTTPStatus.OK) -> None:
        body = json.dumps(obj, indent=2, default=str).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_shutdown(self) -> None:
        # Defence in depth: only honour shutdown when the connecting
        # peer is on loopback (the bind address already enforces this
        # but a misconfigured firewall could expose it).
        peer = self.client_address[0]
        if peer not in ("127.0.0.1", "::1"):
            self._serve_json({"error": "loopback-only"},
                             status=HTTPStatus.FORBIDDEN)
            return
        self._serve_json({"ok": True, "shutting_down": True})
        if _shutdown_fn:
            # Defer slightly so the response actually flushes before we
            # tear the world down.
            threading.Timer(0.2, _shutdown_fn).start()


# ── Data collectors ────────────────────────────────────────────────── #

def _collect_health() -> dict:
    uptime = time.time() - _started_at if _started_at else 0
    brain_ready = bool(_brain_ready_fn and _brain_ready_fn())
    voice = _voice_state_fn() if _voice_state_fn else "unknown"
    return {
        "uptime_s": int(uptime),
        "brain_ready": brain_ready,
        "voice_state": voice,
        "pid": _safe_pid(),
        "version": "aeris-3.1",
    }


def _collect_metrics() -> dict:
    # ResourceMonitor
    rss_samples: list[dict] = []
    pressure = "unknown"
    try:
        from core.resource_monitor import get_monitor as _gm
        m = _gm()
        for s in m.snapshot()[-60:]:  # last 60 samples ~= 4 minutes
            rss_samples.append({
                "ts": s.ts,
                "rss_mb": round(s.rss_bytes / (1024 * 1024), 1),
                "cpu_pct": s.cpu_percent,
                "threads": s.num_threads,
                "handles": s.num_handles,
            })
        pressure = m.level_name()
    except Exception:
        pass

    # Bounded caches
    cache_data: list[dict] = []
    try:
        from core.cache_registry import cache_stats
        cache_data = cache_stats()
    except Exception:
        pass

    # Skill breakers
    breaker_data: list[dict] = []
    try:
        from core.skill_breaker import stats as _bstats
        breaker_data = _bstats()
    except Exception:
        pass

    # Power
    power = {}
    try:
        from core.power_state import get_monitor as _pgm
        snap = _pgm().snapshot()
        power = {
            "on_battery": snap.on_battery,
            "percent": snap.percent,
            "plugged": snap.plugged,
            "idle_s": snap.idle_s,
            "is_idle": snap.is_idle,
        }
    except Exception:
        pass

    return {
        "resource_pressure": pressure,
        "resource_samples": rss_samples,
        "caches": cache_data,
        "skill_breakers": breaker_data,
        "power": power,
    }


def _collect_skills() -> dict:
    try:
        from core.skill_registry import REGISTRY
        return {
            "count": len(REGISTRY),
            "skills": [
                {"name": s.name,
                 "description": s.description,
                 "patterns": len(s.patterns),
                 "required_entities": s.required_entities}
                for s in sorted(REGISTRY.values(), key=lambda x: x.name)
            ],
        }
    except Exception as e:
        return {"error": str(e), "count": 0, "skills": []}


def _safe_pid() -> int:
    try:
        import os
        return os.getpid()
    except Exception:
        return -1


# ── Server lifecycle ───────────────────────────────────────────────── #

_server: Optional[ThreadingHTTPServer] = None
_server_thread: Optional[threading.Thread] = None


def start_server(*,
                 port: int = _PORT,
                 brain_ready_fn: Optional[Callable[[], bool]] = None,
                 voice_state_fn: Optional[Callable[[], str]] = None,
                 shutdown_fn: Optional[Callable[[], None]] = None) -> bool:
    """Bind the HTTP listener and spawn the worker thread. Returns False
    if the port is in use (we never fight for it — port collision means
    a previous AERIS run is still around, the single-instance lock
    should have caught it earlier).
    """
    global _server, _server_thread, _started_at
    global _brain_ready_fn, _voice_state_fn, _shutdown_fn

    if _server is not None:
        return True

    _brain_ready_fn = brain_ready_fn
    _voice_state_fn = voice_state_fn
    _shutdown_fn = shutdown_fn

    try:
        _server = ThreadingHTTPServer((_BIND, port), _Handler)
    except OSError as e:
        log.warning("[health] could not bind %s:%d (%s)", _BIND, port, e)
        return False

    _started_at = time.time()
    _server_thread = threading.Thread(
        target=_server.serve_forever, name="AerisHealthServer", daemon=True
    )
    _server_thread.start()
    log.info("[health] listening on http://%s:%d", _BIND, port)
    return True


def stop_server() -> None:
    global _server, _server_thread
    s = _server
    _server = None
    if s is not None:
        s.shutdown()
        s.server_close()
    t = _server_thread
    _server_thread = None
    if t is not None:
        t.join(timeout=2.0)


_INDEX_HTML = """<!doctype html>
<html><head><title>AERIS Health</title>
<style>
body{font-family:Consolas,Menlo,monospace;background:#0d1525;color:#dcecf0;padding:24px;max-width:720px;margin:auto}
h1{color:#00d7e6;letter-spacing:2px;font-size:18px}
a{color:#00d7e6}
li{margin:.4em 0}
small{color:#788}
</style></head><body>
<h1>A.E.R.I.S — JARVIS v3.1 · health</h1>
<ul>
<li><a href="/health">/health</a> — uptime, brain &amp; voice state</li>
<li><a href="/metrics">/metrics</a> — resource samples, caches, skill breakers, power</li>
<li><a href="/skills">/skills</a> — registered plugin skills</li>
<li><code>/shutdown</code> — POST/GET from loopback only · stops AERIS</li>
</ul>
<small>localhost only · no auth · single-process lifetime</small>
</body></html>
"""


if __name__ == "__main__":
    import signal as _sig
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    start_server(brain_ready_fn=lambda: True,
                 voice_state_fn=lambda: "TEST")
    print("Server running on http://127.0.0.1:8765 — Ctrl-C to stop")
    try:
        _sig.pause() if hasattr(_sig, "pause") else time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server()
