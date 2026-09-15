"""Phone pairing — LAN HTTP server that lets a phone fire AERIS skills.

Stdlib only (no Flask). Endpoints:

  GET  /              — minimal HTML page listing every skill with a "fire" button
  GET  /skills        — JSON list of skills + descriptions
  POST /fire          — JSON body: {"name": "<skill>", "raw_text": "..."}
                        → runs the skill, returns its result

Security: by default binds to the local network interface (the one the
kernel would use to talk to the internet); requires a per-session token
in the X-Aeris-Token header. Token printed once on start. Disable
anytime via the off skill.

Public API:
    start(host=None, port=8787) -> dict   {url, token, ok}
    stop() -> None
    status() -> dict
"""
from __future__ import annotations

import json
import logging
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

log = logging.getLogger(__name__)


_DEFAULT_PORT = 8787
_STATE: dict = {
    "server": None,            # ThreadingHTTPServer
    "thread": None,            # serving thread
    "host": "",
    "port": 0,
    "token": "",
    "started_at": 0.0,
}
_LOCK = threading.RLock()


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return "127.0.0.1"


def _fire_skill(name: str, raw_text: str) -> tuple[bool, str]:
    try:
        from core.skill_registry import get_skill
    except Exception as e:
        return False, f"registry load fail: {e}"
    sk = get_skill(name)
    if sk is None:
        return False, f"skill '{name}' not registered"
    try:
        result = sk.run({"raw_text": raw_text or "", "source": "phone_bridge"})
        return True, (result or "").strip() or "(no output)"
    except Exception as e:
        return False, f"skill '{name}' raised: {e}"


# ── HTML payload ─────────────────────────────────────────────────


def _index_html(token: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>AERIS Phone Bridge</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ font-family: -apple-system, Segoe UI, sans-serif;
          background: #0d1117; color: #e6edf3; padding: 16px; }}
  h1 {{ font-size: 18px; color: #7ee787; }}
  input, button {{ font-size: 15px; padding: 8px;
                   background: #21262d; color: #e6edf3;
                   border: 1px solid #30363d; border-radius: 6px; }}
  button {{ background: #1f6feb; color: white; cursor: pointer; }}
  ul {{ padding: 0; list-style: none; }}
  li {{ padding: 8px; border-bottom: 1px solid #21262d; }}
  .desc {{ color: #8b949e; font-size: 13px; }}
  pre {{ background:#161b22; padding:8px; border-radius:6px;
         max-height: 200px; overflow:auto; }}
</style></head><body>
<h1>AERIS Phone Bridge</h1>
<p>Tap a skill to fire it on the desktop.</p>
<input id="q" placeholder="Filter skills…" style="width:100%">
<ul id="list"></ul>
<h3>Last result</h3>
<pre id="out">(none yet)</pre>
<script>
const token = "{token}";
async function load() {{
  const r = await fetch('/skills', {{headers: {{'X-Aeris-Token': token}}}});
  const arr = await r.json();
  window._skills = arr;
  render();
}}
function render() {{
  const q = document.getElementById('q').value.toLowerCase();
  const ul = document.getElementById('list');
  ul.innerHTML = '';
  for (const s of window._skills) {{
    if (q && !s.name.toLowerCase().includes(q) &&
        !(s.description || '').toLowerCase().includes(q)) continue;
    const li = document.createElement('li');
    li.innerHTML = `<b>${{s.name}}</b>
      <button onclick="fire('${{s.name}}')">▶</button>
      <div class="desc">${{s.description || ''}}</div>`;
    ul.appendChild(li);
  }}
}}
async function fire(name) {{
  const r = await fetch('/fire', {{
    method: 'POST',
    headers: {{'X-Aeris-Token': token, 'Content-Type': 'application/json'}},
    body: JSON.stringify({{name, raw_text: name}}),
  }});
  const j = await r.json();
  document.getElementById('out').textContent =
    (j.ok ? '' : '[FAIL] ') + (j.result || j.error || '');
}}
document.getElementById('q').addEventListener('input', render);
load();
</script>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet — we use our own logger
        log.debug("[phone_bridge] %s %s", self.address_string(), fmt % args)

    def _bad(self, code: int, msg: str) -> None:
        body = json.dumps({"ok": False, "error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _token_ok(self) -> bool:
        tok = _STATE.get("token") or ""
        provided = self.headers.get("X-Aeris-Token") or ""
        # Constant-time compare to mitigate timing leak.
        return bool(tok) and secrets.compare_digest(tok, provided)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            body = _index_html(_STATE.get("token") or "").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/skills":
            if not self._token_ok():
                self._bad(401, "missing or invalid X-Aeris-Token header"); return
            try:
                from core.skill_registry import all_skills
                rows = sorted([
                    {"name": k, "description": (v.description or "")[:160]}
                    for k, v in all_skills().items()
                ], key=lambda r: r["name"])
            except Exception as e:
                self._bad(500, f"registry error: {e}"); return
            body = json.dumps(rows).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._bad(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/fire":
            self._bad(404, "not found"); return
        if not self._token_ok():
            self._bad(401, "missing or invalid X-Aeris-Token header"); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw) if raw else {}
            name = str(payload.get("name") or "").strip()
            raw_text = str(payload.get("raw_text") or name)
        except Exception as e:
            self._bad(400, f"bad request: {e}"); return
        if not name:
            self._bad(400, "missing 'name' in body"); return
        ok, result = _fire_skill(name, raw_text)
        body = json.dumps({"ok": ok, "name": name,
                           "result": result if ok else "",
                           "error": result if not ok else ""}).encode("utf-8")
        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── lifecycle ────────────────────────────────────────────────────


def is_running() -> bool:
    return _STATE.get("server") is not None


def status() -> dict:
    return {
        "running": is_running(),
        "host": _STATE.get("host") or "",
        "port": _STATE.get("port") or 0,
        "token": "(set)" if _STATE.get("token") else "",
        "url":   ((f"http://{_STATE['host']}:{_STATE['port']}/")
                  if is_running() else ""),
    }


def start(host: Optional[str] = None, port: int = _DEFAULT_PORT) -> dict:
    if is_running():
        return {"ok": True, "msg": "Already running.",
                **status()}
    bind_host = host or _local_ip()
    token = secrets.token_urlsafe(12)
    try:
        server = ThreadingHTTPServer(("0.0.0.0", int(port)), _Handler)
    except Exception as e:
        return {"ok": False, "msg": f"bind {port} failed: {e}"}
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                              name="PhoneBridge")
    thread.start()
    with _LOCK:
        _STATE.update({
            "server": server,
            "thread": thread,
            "host":   bind_host,
            "port":   int(port),
            "token":  token,
            "started_at": __import__("time").monotonic(),
        })
    url = f"http://{bind_host}:{port}/"
    log.info("[phone_bridge] up at %s (token=%s)", url, token)
    return {
        "ok": True,
        "msg": (f"Phone bridge ON: {url}  ·  "
                f"token: {token} (send as X-Aeris-Token header)"),
        "url": url, "token": token, "host": bind_host, "port": int(port),
    }


def stop() -> None:
    with _LOCK:
        server = _STATE.get("server")
        if server is None:
            return
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        _STATE.update({"server": None, "thread": None,
                       "host": "", "port": 0, "token": ""})
    log.info("[phone_bridge] stopped.")
