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
  GET /subsystems    → per-subsystem boot/health state (up, reconnecting,
                       failed + why) from ``core.subsystem_registry``
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

# A client that closes the socket mid-response (curl ^C, a poll loop reading
# then disconnecting, a browser tab close) makes wfile.write raise one of
# these. It's not a server fault — debug-log it, never a full traceback, and
# never try to write an error response back into the dead socket.
_CLIENT_GONE = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)


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
            elif path == "/subsystems":
                self._serve_json(_collect_subsystems())
            elif path == "/mind":
                self._serve_html(_MIND_HTML)
            elif path == "/mind.json":
                self._serve_json(_collect_mind())
            elif path == "/privacy.json":
                from core import privacy_view
                self._serve_json({"stores": privacy_view.snapshot()})
            elif path == "/shutdown":
                self._handle_shutdown()
            else:
                self._serve_json({"error": "not found", "path": path},
                                 status=HTTPStatus.NOT_FOUND)
        except _CLIENT_GONE as e:
            # Client hung up before we finished — expected, not an error.
            log.debug("[health] client disconnected: %s", e.__class__.__name__)
        except Exception as e:  # noqa: BLE001
            log.exception("[health] handler raised")
            try:
                self._serve_json({"error": str(e)},
                                 status=HTTPStatus.INTERNAL_SERVER_ERROR)
            except _CLIENT_GONE:
                pass            # don't double-fault writing the error response

    # ── helpers ──
    def do_POST(self):  # noqa: N802 — stdlib API
        path = self.path.split("?", 1)[0]
        try:
            if path.startswith("/trust/"):
                self._handle_trust_action(path[len("/trust/"):])
            elif path.startswith("/privacy/"):
                self._handle_guarded_post(
                    path[len("/privacy/"):],
                    lambda a, p: __import__("core.privacy_view",
                                            fromlist=["apply_action"])
                    .apply_action(a, p))
            else:
                self._serve_json({"error": "not found", "path": path},
                                 status=HTTPStatus.NOT_FOUND)
        except _CLIENT_GONE as e:
            log.debug("[health] client disconnected: %s", e.__class__.__name__)
        except Exception as e:  # noqa: BLE001
            log.exception("[health] POST handler raised")
            try:
                self._serve_json({"error": str(e)},
                                 status=HTTPStatus.INTERNAL_SERVER_ERROR)
            except _CLIENT_GONE:
                pass

    def _handle_guarded_post(self, action: str, apply_fn) -> None:
        """Shared guard for state-changing POSTs: loopback-only + the
        X-AERIS-LOCAL header (same policy as /trust)."""
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._serve_json({"error": "loopback-only"},
                             status=HTTPStatus.FORBIDDEN)
            return
        if self.headers.get("X-AERIS-LOCAL") != "1":
            self._serve_json({"error": "missing X-AERIS-LOCAL header"},
                             status=HTTPStatus.FORBIDDEN)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            params = json.loads(raw or b"{}")
        except Exception:
            params = {}
        try:
            res = apply_fn(action, params)
        except ValueError as e:
            self._serve_json({"ok": False, "error": str(e)},
                             status=HTTPStatus.BAD_REQUEST)
            return
        self._serve_json(res)

    def _handle_trust_action(self, action: str) -> None:
        # State-changing: loopback-only (defence in depth beyond the bind) AND a
        # custom header a cross-site page can't forge without CORS approval.
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self._serve_json({"error": "loopback-only"},
                             status=HTTPStatus.FORBIDDEN)
            return
        if self.headers.get("X-AERIS-LOCAL") != "1":
            self._serve_json({"error": "missing X-AERIS-LOCAL header"},
                             status=HTTPStatus.FORBIDDEN)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            params = json.loads(raw or b"{}")
        except Exception:
            params = {}
        from core import trust_view
        try:
            res = trust_view.apply_action(action, params)
        except ValueError as e:
            self._serve_json({"ok": False, "error": str(e)},
                             status=HTTPStatus.BAD_REQUEST)
            return
        res["trust"] = trust_view.snapshot()
        self._serve_json(res)

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

def _collect_mind() -> dict:
    """The Self-Model snapshot for the Mind dashboard (read-only)."""
    try:
        from core.self_model import get_self_model
        d = get_self_model().snapshot().to_dict()
    except Exception as e:  # never let the dashboard crash the server
        d = {"error": str(e), "awake": True, "skills_count": 0,
             "capabilities": {}, "active_goals": [], "recent_actions": [],
             "recent_errors": [], "confidence": 1.0, "mood": "unknown"}
    # What AERIS wants to surface right now — READ-ONLY preview. A GET must
    # never consume the anti-nag budget (that's tick()'s job when a real
    # surfacing channel fires).
    try:
        from core.initiative_engine import get_engine
        d["pending_initiatives"] = get_engine().preview()
    except Exception:
        d["pending_initiatives"] = []
    # The learning loop, observable: routines still awaiting the user's yes/no,
    # and the ones that earned auto-run. READ-ONLY (no accept/graduate here).
    try:
        from core import routine_offers as _ro
        d["learned_offers"] = [
            {"key": o.key, "title": o.suggestion.title,
             "confidence": o.suggestion.confidence,
             "accepts": o.accepts, "accepts_left": o.accepts_left}
            for o in _ro.pending_offers()
        ]
        d["auto_routines"] = [
            {"key": s.get("key"), "name": s.get("name"),
             "enabled": s.get("enabled"),
             "needs_confirm": s.get("needs_confirm", False)}
            for s in _ro.active_routines()
        ]
    except Exception:
        d["learned_offers"], d["auto_routines"] = [], []
    # Trust & audit: what AERIS may do autonomously + the "what did it do, why"
    # ledger. Makes "trust before autonomy" visible. READ-ONLY snapshot.
    try:
        from core import trust_view
        d["trust"] = trust_view.snapshot(audit_n=12)
    except Exception:
        d["trust"] = {}
    return d


def _collect_subsystems() -> dict:
    """Per-subsystem boot/health state from the in-process registry.

    This is the endpoint that makes a degraded session diagnosable from
    outside: which staged installs came up, which are mid-reconnect, which
    gave up, and why. Kept separate from ``/health`` because it is a list
    that grows, and ``/health`` is polled by the mobile companion.
    """
    try:
        from core.subsystem_registry import get_registry
        return get_registry().snapshot()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "subsystems": []}


def _collect_health() -> dict:
    uptime = time.time() - _started_at if _started_at else 0
    brain_ready = bool(_brain_ready_fn and _brain_ready_fn())
    voice = _voice_state_fn() if _voice_state_fn else "unknown"
    # Ollama / LLM reachability — cached (15 s TTL) so hammering /health never
    # fans out into a network call per request. Best-effort: a probe failure
    # must not break the health endpoint.
    ollama = {"status": "unknown"}
    try:
        from core.llm_chat import probe_cached
        p = probe_cached(ttl=15.0)
        ollama = {
            "status": p["status"],            # ok | no_model | unreachable
            "reachable": p["reachable"],
            "model": p["model"],
            "model_present": p["model_present"],
        }
    except Exception as e:
        ollama = {"status": "error", "error": str(e)}
    return {
        "uptime_s": int(uptime),
        "brain_ready": brain_ready,
        "voice_state": voice,
        "llm_ollama": ollama,
        "pid": _safe_pid(),
        "version": "aeris-3.1",
        # Compact roll-up only — the per-subsystem list lives at
        # /subsystems. A monitor polling /health should be able to see "not
        # everything is up" without a second request.
        "subsystems": _subsystem_rollup(),
    }


def _subsystem_rollup() -> dict:
    """Three fields: is everything up, how many, and what is not."""
    try:
        from core.subsystem_registry import get_registry
        s = get_registry().snapshot()
        return {
            "ok": s["ok"],
            "healthy": s["healthy"],
            "total": s["total"],
            "down": s["failed"] + s["degraded"],
        }
    except Exception:
        return {"ok": None, "healthy": 0, "total": 0, "down": []}


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

    # Activity / telemetry façade (skills, changes, latency, last_dispatch).
    activity: dict = {}
    try:
        from core.metrics import snapshot as _msnap
        activity = _msnap(window_h=1.0)
    except Exception:
        pass

    return {
        "resource_pressure": pressure,
        "resource_samples": rss_samples,
        "caches": cache_data,
        "skill_breakers": breaker_data,
        "power": power,
        "activity": activity,
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
<li><a href="/subsystems">/subsystems</a> — boot stages: up, reconnecting, or down (and why)</li>
<li><a href="/mind">/mind</a> — the Mind dashboard (self-model: state, goals, why)</li>
<li><code>/shutdown</code> — POST/GET from loopback only · stops AERIS</li>
</ul>
<small>localhost only · no auth · single-process lifetime</small>
</body></html>
"""


# The Mind dashboard — AERIS's self-model, live. Static HTML that polls
# /mind.json every 3 s (keeps the server dumb, the page always current).
_MIND_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AERIS · Mind</title><style>
:root{--bg:#0A0C11;--panel:#12151D;--line:#242A36;--cyan:#37E0EA;
--violet:#7C6CFF;--mint:#54F0C0;--hot:#FF5A6E;--text:#ECEFF6;--muted:#8A93A6;
--faint:#565F70}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#141a2b,var(--bg));
color:var(--text);font-family:Consolas,Menlo,monospace;padding:24px;
max-width:900px;margin:auto}
.hdr{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.core{width:16px;height:16px;border-radius:50%;background:var(--cyan);
box-shadow:0 0 0 0 rgba(55,224,234,.6);animation:pulse 2.4s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(55,224,234,.5)}
70%{box-shadow:0 0 0 14px rgba(55,224,234,0)}100%{box-shadow:0 0 0 0 rgba(55,224,234,0)}}
h1{font-size:16px;letter-spacing:4px;margin:0;font-weight:800}
.tag{font-size:10px;letter-spacing:1.5px;color:var(--faint);
border:1px solid var(--line);border-radius:6px;padding:3px 8px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;
padding:16px}
.k{font-size:10px;letter-spacing:2px;color:var(--faint);margin-bottom:10px}
.big{font-size:30px;font-weight:800}
.row{display:flex;justify-content:space-between;align-items:center;
padding:7px 0;border-bottom:1px solid var(--line);font-size:13px}
.row:last-child{border:0}
.why{color:var(--muted);font-size:11px;margin-top:2px}
.bar{height:6px;border-radius:4px;background:var(--line);overflow:hidden;
margin-top:4px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--violet),var(--cyan))}
.pill{font-size:10px;padding:2px 7px;border-radius:20px;color:var(--bg)}
.mint{background:var(--mint)}.violet{background:var(--violet)}.hot{background:var(--hot)}
.empty{color:var(--faint);font-size:12px;padding:8px 0}
.state{color:var(--cyan)}
.btn{cursor:pointer;background:var(--panel);border:1px solid var(--line);
color:var(--fg);border-radius:6px;padding:2px 7px;font-size:11px;
font-family:inherit;margin-left:3px}
.btn:hover{border-color:var(--cyan)}
.btn.danger{border-color:var(--hot);color:var(--hot)}
.btn.danger:hover{background:var(--hot);color:var(--bg)}
</style></head><body>
<div class="hdr"><div class="core" id="core"></div>
<h1>AERIS · MIND</h1><div class="tag" id="awake">—</div>
<div style="flex:1"></div><div class="tag" id="clock">live</div></div>
<div class="grid">
 <div class="card"><div class="k">STATE</div>
   <div class="big" id="mood">—</div>
   <div class="row"><span>Confidence</span><b class="state" id="conf">—</b></div>
   <div class="row"><span>Autonomy</span><b id="auto">—</b></div>
   <div class="row"><span>Skills</span><b id="skills">—</b></div></div>
 <div class="card"><div class="k">CAPABILITIES</div><div id="caps"></div></div>
 <div class="card"><div class="k">ACTIVE GOALS</div><div id="goals"></div></div>
 <div class="card"><div class="k">RECENTLY DID · WHY</div><div id="did"></div></div>
</div>
<div class="card" style="margin-top:14px">
 <div class="k">WANTS TO SAY · INITIATIVE</div><div id="pend"></div></div>
<div class="card" style="margin-top:14px">
 <div class="k">LEARNED ROUTINES · OFFERS &amp; AUTO-RUN</div><div id="learn"></div></div>
<div class="card" style="margin-top:14px">
 <div class="k">TRUST · AUTONOMY PER CLASS</div>
 <div id="truststate" style="margin-bottom:8px"></div>
 <div id="grants"></div></div>
<div class="card" style="margin-top:14px">
 <div class="k">AUDIT · KYA KIYA, KYUN</div><div id="audit"></div></div>
<div class="card" style="margin-top:14px"><div class="k">RECENT ERRORS</div>
 <div id="errs"></div></div>
<script>
const $=id=>document.getElementById(id);
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
window.tpost=async(action,params)=>{
 try{await fetch('/trust/'+action,{method:'POST',
   headers:{'X-AERIS-LOCAL':'1','Content-Type':'application/json'},
   body:JSON.stringify(params||{})})}catch(e){}
 tick();
}
async function tick(){
 let d;try{d=await (await fetch('/mind.json',{cache:'no-store'})).json()}catch(e){return}
 const acc=d.awake?'var(--cyan)':'var(--hot)';
 $('core').style.background=acc;
 $('awake').textContent=d.awake?'AWAKE':'PANIC · L0';
 $('awake').style.color=d.awake?'var(--mint)':'var(--hot)';
 $('mood').textContent=d.mood||'—';
 const c=Math.round((d.confidence||0)*100);
 $('conf').textContent=c+'%';
 $('auto').textContent=d.autonomy||'—';
 $('skills').textContent=(d.skills_count||0)+'+';
 const caps=Object.entries(d.capabilities||{}).sort((a,b)=>b[1]-a[1]);
 const mx=Math.max(1,...caps.map(x=>x[1]));
 $('caps').innerHTML=caps.length?caps.map(([k,v])=>
   `<div class="row" style="display:block;border:0;padding:5px 0">
    <div style="display:flex;justify-content:space-between"><span>${esc(k)}</span>
    <b>${v}</b></div><div class="bar"><i style="width:${v/mx*100}%"></i></div></div>`
   ).join(''):'<div class="empty">koi skill nahi</div>';
 const gs=d.active_goals||[];
 $('goals').innerHTML=gs.length?gs.map(g=>{
   const cls=g.state==='acting'?'mint':g.state==='blocked'?'hot':'violet';
   return `<div class="row"><span>${esc(g.text)}</span>
    <span class="pill ${cls}">${esc(g.state)}</span></div>`}).join('')
   :'<div class="empty">koi active goal nahi</div>';
 const dd=d.recent_actions||[];
 $('did').innerHTML=dd.length?dd.slice().reverse().map(a=>
   `<div style="padding:7px 0;border-bottom:1px solid var(--line)">
    <div>${esc(a.action)}</div><div class="why">${esc(a.why)}</div></div>`
   ).join(''):'<div class="empty">abhi tak kuch autonomous nahi kiya</div>';
 const pd=d.pending_initiatives||[];
 $('pend').innerHTML=pd.length?pd.map(p=>{
   const cls=p.route==='act'?'mint':'violet';
   return `<div class="row"><span>${esc(p.text)}</span>
    <span class="pill ${cls}">${esc(p.route)} ${(p.salience||0).toFixed(2)}</span></div>`
   }).join(''):'<div class="empty">abhi kuch kehna nahi — sab shaant</div>';
 const lo=d.learned_offers||[],ar=d.auto_routines||[];
 let lh=ar.map(r=>{
   const cls=r.enabled?'mint':'hot';
   const tag=r.enabled?'AUTO-RUN':'CONFIRM';
   return `<div class="row"><span>${esc(r.name||r.key)}</span>
    <span class="pill ${cls}">${tag}</span></div>`}).join('');
 lh+=lo.map(o=>{
   const need=o.accepts_left;
   return `<div class="row" style="display:block;border-bottom:1px solid var(--line);padding:7px 0">
    <div style="display:flex;justify-content:space-between"><span>${esc(o.title)}</span>
    <span class="pill violet">${o.accepts}/${o.accepts+need}</span></div>
    <div class="why">${need} aur haan → khud chalega</div></div>`}).join('');
 $('learn').innerHTML=lh||'<div class="empty">abhi koi routine nahi seekha</div>';
 const tr=d.trust||{};
 const qh=tr.quiet_hours||{};
 const chips=[];
 if(tr.panic)chips.push('<span class="pill hot">PANIC · L0</span>');
 if(qh.active)chips.push('<span class="pill violet">QUIET HOURS</span>');
 const st=tr.stats||{};
 chips.push(`<span class="pill mint">allow ${st.allow||0}</span>`);
 chips.push(`<span class="pill violet">confirm ${st.confirm||0}</span>`);
 chips.push(`<span class="pill hot">deny ${st.deny||0}</span>`);
 if((tr.spend_today||0)>0)chips.push(`<span class="pill violet">₹${tr.spend_today} today</span>`);
 const pbtn=tr.panic
   ?`<button class="btn danger" onclick="tpost('panic',{on:false})">▶ Resume</button>`
   :`<button class="btn danger" onclick="tpost('panic',{on:true})">⏻ PANIC · halt all</button>`;
 $('truststate').innerHTML=chips.join(' ')+' '+pbtn;
 const gr=tr.grants||[];
 $('grants').innerHTML=gr.length?gr.map(g=>{
   const cls=g.granted>=3?'mint':g.granted>=2?'violet':'hot';
   const cap=g.capped?` <span class="pill hot">CAP L${g.hard_cap}</span>`:'';
   const ceil=(g.hard_cap!=null)?g.hard_cap:5;
   const up=g.granted<ceil?`<button class="btn" onclick="tpost('grant',{cls:'${g.cls}',level:${g.granted+1}})">▲</button>`:'';
   const dn=g.granted>0?`<button class="btn" onclick="tpost('grant',{cls:'${g.cls}',level:${g.granted-1}})">▼</button>`:'';
   return `<div class="row"><span>${esc(g.cls)} <span class="why">${esc(g.blurb)}</span></span>
    <span><span class="pill ${cls}">${esc(g.granted_name)}</span>${cap}${dn}${up}</span></div>`
   }).join(''):'<div class="empty">grants load nahi hue</div>';
 const au=tr.audit||[];
 $('audit').innerHTML=au.length?au.map(a=>{
   const cls=a.decision==='allow'?'mint':a.decision==='confirm'?'violet':'hot';
   return `<div style="padding:7px 0;border-bottom:1px solid var(--line)">
    <div style="display:flex;justify-content:space-between">
     <span>${esc(a.action)} <span class="why">${esc(a.cls)}</span></span>
     <span><span class="pill ${cls}">${esc(a.decision)}</span>
      <span class="why">${esc(a.time)}</span></span></div>
    <div class="why">${esc(a.why)}</div></div>`
   }).join(''):'<div class="empty">abhi tak kuch autonomous nahi kiya</div>';
 const er=d.recent_errors||[];
 $('errs').innerHTML=er.length?er.map(e=>
   `<div class="row" style="color:var(--hot)">${esc(String(e))}</div>`).join('')
   :'<div class="empty">koi error nahi 🎉</div>';
 $('clock').textContent=new Date().toLocaleTimeString();
}
tick();setInterval(tick,3000);
</script></body></html>
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
