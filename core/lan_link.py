"""AERIS LAN fast-path — direct phone↔laptop socket on the same WiFi.

Why: the Firebase relay is great for "anywhere" reach but every frame is an
internet round-trip (~1-3s) — too slow for a smooth live screen and unusable
for mouse control. When both devices are on the same network we open a direct
TCP socket instead: ~20-50ms latency, 10-20 fps, and real remote-mouse.

Zero-config: the laptop's LAN IPs + port + a random session token are handed
to the phone through the ENCRYPTED bridge (``lan_offer``), so nothing is typed
and Google only ever saw ciphertext. The phone connects, echoes the token, and
we're live. No same-WiFi? The phone just never connects and everything stays
on the relay (screen laggy, mouse off).

Wire protocol (after a ``AERIS <token>\n`` / ``OK\n`` handshake), framed as
1 type byte + 4-byte big-endian length + payload:

    'L'  laptop → phone   JPEG of the laptop screen (fallback mode)
    'I'  laptop → phone   video stream info JSON {"w","h","fps","codec"}
    'V'  laptop → phone   one H.264 access unit (Annex-B) — 60 fps video
    'P'  phone  → laptop  JPEG of the phone screen
    'M'  phone  → laptop  mouse event  {"t":"move","dx":..,"dy":..} / click / scroll
"""
from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, List, Optional

log = logging.getLogger(__name__)


def local_ips() -> List[str]:
    """Best-effort list of this machine's LAN IPv4 addresses."""
    ips: set[str] = set()
    # The UDP-connect trick reveals the primary outbound interface IP.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return [ip for ip in ips if not ip.startswith("169.254.")]


class LanLink:
    """One TCP server the phone connects into. Holds a single active client
    (the paired phone); re-connect replaces the old socket."""

    def __init__(self):
        self._srv: Optional[socket.socket] = None
        self._port = 0
        self._token: Optional[str] = None
        self._client: Optional[socket.socket] = None
        self._client_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._on_phone_frame: Optional[Callable[[bytes], None]] = None
        self._on_client_connect: Optional[Callable[[], None]] = None
        self._on_lan_control: Optional[Callable[[str], None]] = None
        self._mouse_seen = False

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self, token: str) -> int:
        """Start (idempotent) the server and return the listening port."""
        self._token = token
        if self._srv is not None:
            return self._port
        self._stop.clear()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", 0))
        srv.listen(1)
        self._srv = srv
        self._port = srv.getsockname()[1]
        threading.Thread(target=self._accept_loop, name="LanAccept",
                         daemon=True).start()
        log.info("[lan] server listening on 0.0.0.0:%d", self._port)
        return self._port

    def set_token(self, token: str) -> None:
        self._token = token

    def on_phone_frame(self, cb: Callable[[bytes], None]) -> None:
        self._on_phone_frame = cb

    def on_control(self, cb: Callable[[str], None]) -> None:
        """Phone → laptop control action over LAN ('C'): stop_laptop_stream /
        stop_phone_stream. Reliable — bypasses the flaky relay."""
        self._on_lan_control = cb

    def _apply_control(self, payload: bytes) -> None:
        try:
            import json
            action = json.loads(payload.decode("utf-8")).get("action") or ""
        except Exception:
            return
        cb = getattr(self, "_on_lan_control", None)
        if action and cb:
            try:
                cb(action)
            except Exception:
                pass

    def send_control(self, action: str) -> bool:
        """Laptop → phone control action over LAN ('C')."""
        import json
        return self._send_typed(
            "C", json.dumps({"action": action}).encode("utf-8"))

    def on_client_connect(self, cb: Callable[[], None]) -> None:
        """Called (on the client thread) right after a phone handshakes —
        used to re-announce an in-progress video stream."""
        self._on_client_connect = cb

    def is_connected(self) -> bool:
        with self._client_lock:
            return self._client is not None

    def endpoints(self) -> dict:
        return {"ips": local_ips(), "port": self._port}

    # ── server internals ─────────────────────────────────────────────
    def _accept_loop(self) -> None:
        while not self._stop.is_set() and self._srv is not None:
            try:
                conn, addr = self._srv.accept()
            except Exception:
                break
            threading.Thread(target=self._handle_client, args=(conn, addr),
                             name="LanClient", daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr) -> None:
        try:
            conn.settimeout(10)
            line = b""
            while not line.endswith(b"\n") and len(line) < 256:
                ch = conn.recv(1)
                if not ch:
                    conn.close()
                    return
                line += ch
            parts = line.decode("utf-8", "ignore").strip().split()
            if len(parts) != 2 or parts[0] != "AERIS" \
                    or not self._token or parts[1] != self._token:
                try:
                    conn.sendall(b"NO\n")
                finally:
                    conn.close()
                log.info("[lan] rejected client %s (bad token)", addr)
                return
            conn.sendall(b"OK\n")
            conn.settimeout(None)
            # Low-latency: no Nagle batching on video/mouse packets.
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            with self._client_lock:
                old = self._client
                self._client = conn
            if old is not None:
                try:
                    old.close()
                except Exception:
                    pass
            log.info("[lan] phone connected from %s", addr)
            if self._on_client_connect:
                try:
                    self._on_client_connect()
                except Exception:
                    pass
            self._read_loop(conn)
        except Exception as e:
            log.info("[lan] client error: %s", e)
        finally:
            with self._client_lock:
                if self._client is conn:
                    self._client = None
            try:
                conn.close()
            except Exception:
                pass
            log.info("[lan] phone disconnected")

    def _recvn(self, conn: socket.socket, n: int) -> Optional[bytes]:
        buf = b""
        while len(buf) < n:
            try:
                chunk = conn.recv(n - len(buf))
            except Exception:
                return None
            if not chunk:
                return None
            buf += chunk
        return buf

    def _read_loop(self, conn: socket.socket) -> None:
        while not self._stop.is_set():
            hdr = self._recvn(conn, 5)
            if hdr is None:
                break
            t = hdr[0]
            ln = int.from_bytes(hdr[1:5], "big")
            if ln < 0 or ln > 20_000_000:
                break
            payload = self._recvn(conn, ln) if ln else b""
            if payload is None:
                break
            if t == ord("P"):
                if self._on_phone_frame:
                    try:
                        self._on_phone_frame(payload)
                    except Exception:
                        pass
            elif t == ord("M"):
                self._apply_mouse(payload)
            elif t == ord("C"):
                self._apply_control(payload)

    # ── laptop → phone ───────────────────────────────────────────────
    def _send_typed(self, type_char: str, payload: bytes) -> bool:
        with self._client_lock:
            conn = self._client
        if conn is None:
            return False
        try:
            hdr = bytes([ord(type_char)]) + len(payload).to_bytes(4, "big")
            with self._send_lock:
                conn.sendall(hdr + payload)
            return True
        except Exception:
            with self._client_lock:
                if self._client is conn:
                    self._client = None
            return False

    def send_laptop_frame(self, jpg: bytes) -> bool:
        """Send a laptop-screen JPEG over LAN. False if no phone connected
        (caller then falls back to the relay)."""
        return self._send_typed("L", jpg)

    def send_video_info(self, info: dict) -> bool:
        """Announce H.264 stream parameters to the phone."""
        import json
        return self._send_typed("I", json.dumps(info).encode("utf-8"))

    def send_video_au(self, au: bytes) -> bool:
        """Send one H.264 access unit (Annex-B) to the phone."""
        return self._send_typed("V", au)

    # ── remote mouse ─────────────────────────────────────────────────
    def _apply_mouse(self, payload: bytes) -> None:
        try:
            import json
            d = json.loads(payload.decode("utf-8"))
        except Exception:
            return
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0        # no artificial delay between calls
            if not self._mouse_seen:
                self._mouse_seen = True
                log.info("[lan] remote mouse ACTIVE (first event: %s)", d.get("t"))
            t = d.get("t")
            if t == "move":
                pyautogui.moveRel(int(round(float(d.get("dx", 0)))),
                                  int(round(float(d.get("dy", 0)))),
                                  duration=0, _pause=False)
            elif t == "click":
                pyautogui.click(button=d.get("b", "left"), _pause=False)
            elif t == "double":
                pyautogui.doubleClick(_pause=False)
            elif t == "scroll":
                pyautogui.scroll(int(d.get("dy", 0)))
            elif t == "down":
                pyautogui.mouseDown(button=d.get("b", "left"), _pause=False)
            elif t == "up":
                pyautogui.mouseUp(button=d.get("b", "left"), _pause=False)
            elif t == "type":
                pyautogui.write(str(d.get("text", "")), interval=0)
            elif t == "key":
                k = str(d.get("key", "")).lower()
                if k:
                    pyautogui.press(k)
            elif t == "hotkey":
                keys = [str(x).lower() for x in (d.get("keys") or []) if x]
                if keys:
                    pyautogui.hotkey(*keys)
        except Exception as e:
            log.warning("[lan] mouse apply failed: %s", e)

    def stop(self) -> None:
        self._stop.set()
        with self._client_lock:
            c = self._client
            self._client = None
        for s in (c, self._srv):
            try:
                if s:
                    s.close()
            except Exception:
                pass
        self._srv = None
        self._port = 0


_LINK: Optional[LanLink] = None
_LOCK = threading.Lock()


def get() -> LanLink:
    global _LINK
    with _LOCK:
        if _LINK is None:
            _LINK = LanLink()
        return _LINK
