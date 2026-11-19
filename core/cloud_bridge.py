"""AERIS Cloud Bridge — phone ↔ laptop over the internet, zero config.

Architecture (see ROADMAP "AERIS Bridge"): both devices are OUTBOUND
clients of one Firebase project — no IPs, no port forwarding, no
hosting. Firestore is a dumb encrypted mailbox; FCM (phase 2) wakes the
phone app. Works from anywhere with internet.

Privacy: every payload is AES-256-GCM encrypted with a key that ONLY
the two devices hold — it travels via QR code at pairing (a local,
visual channel), never through the network. Google relays ciphertext.

Firestore layout (all under one random unguessable pair id):

    bridge/{pid}                    presence doc {laptop_ts, phone_ts}
    bridge/{pid}/toLaptop/{auto}    {n, ct, ts}   phone → laptop
    bridge/{pid}/toPhone/{auto}     {n, ct, ts}   laptop → phone

Message payload (inside the ciphertext):
    {"id": str, "type": "chat"|"command"|"response"|"phone_action"|
     "event", "text": str, "reply_to": str|None, "extra": dict}

Laptop lifecycle:
    configure() → paired() / new_pairing() → start(process_fn) → stop()
``process_fn(text) -> str`` is the brain hook (wired by the GUI/runner);
the bridge never imports the engine directly.

Requires: data/secrets/firebase_bridge.json (service-account key the
user downloads from Firebase console — stays on this disk, never
committed / synced).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets as _secrets
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SECRETS_DIR = os.path.join(_ROOT, "data", "secrets")
_SA_KEY_PATH = os.path.join(_SECRETS_DIR, "firebase_bridge.json")
_PAIR_PATH = os.path.join(_SECRETS_DIR, "bridge_pair.json")
_QR_PATH = os.path.join(_SECRETS_DIR, "pair_qr.png")

_PRESENCE_INTERVAL_S = 60.0
# Ignore mailbox docs older than this — stale commands from before a
# restart must not replay (e.g. an old "lock screen").
_MAX_MSG_AGE_S = 120.0


# ── crypto ───────────────────────────────────────────────────────────

def bridge_disabled() -> bool:
    """True when AERIS_DISABLE_BRIDGE forbids starting the phone bridge.

    `JarvisMainEngine.setup_iter` auto-starts the bridge whenever a pairing
    and a service-account key exist, which is right for the real app and
    wrong everywhere else: constructing an engine then opens a live Firestore
    `on_snapshot` listener against the user's real pairing and spawns the
    presence + clipboard-sync daemon threads. Under pytest that happened once
    per engine-building test, with nothing ever stopping them — the threads
    piled up across the session and were still polling the Win32 clipboard
    while later tests loaded torch/spaCy, which is where the suite kept
    dying with 0xC0000374.

    Also genuinely useful outside tests: run AERIS fully offline, or on a
    machine that shouldn't touch the phone pairing, without editing settings.
    """
    return str(os.environ.get("AERIS_DISABLE_BRIDGE", "")).strip().lower() in (
        "1", "true", "yes", "on")


def _aesgcm(key: bytes):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key)


def encrypt_payload(key: bytes, payload: dict) -> dict:
    """dict → {"n": b64 nonce, "ct": b64 ciphertext} (AES-256-GCM)."""
    nonce = _secrets.token_bytes(12)
    ct = _aesgcm(key).encrypt(
        nonce, json.dumps(payload, ensure_ascii=False).encode("utf-8"), None)
    return {"n": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode()}


def decrypt_payload(key: bytes, doc: dict) -> Optional[dict]:
    """Inverse of encrypt_payload. None on any tamper/garbage."""
    try:
        nonce = base64.b64decode(doc["n"])
        ct = base64.b64decode(doc["ct"])
        raw = _aesgcm(key).decrypt(nonce, ct, None)
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        log.warning("[bridge] undecryptable message dropped: %s", e)
        return None


# ── pairing ──────────────────────────────────────────────────────────

def load_pair() -> Optional[dict]:
    """{"pid": str, "key": bytes} or None when never paired."""
    try:
        with open(_PAIR_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {"pid": d["pid"], "key": base64.b64decode(d["key_b64"])}
    except Exception:
        return None


def new_pairing(project_id: str) -> dict:
    """Generate fresh pair id + key, persist, render the QR PNG.

    Returns {"pid", "key", "qr_path"}. Re-pairing rotates everything —
    an old phone is instantly locked out (kill switch).
    """
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    pid = _secrets.token_hex(16)              # 128-bit unguessable path
    key = _secrets.token_bytes(32)            # AES-256
    with open(_PAIR_PATH, "w", encoding="utf-8") as f:
        json.dump({"pid": pid, "key_b64": base64.b64encode(key).decode(),
                   "created": time.time()}, f, indent=2)

    qr_payload = json.dumps({
        "v": 1, "kind": "aeris-bridge",
        "project": project_id, "pid": pid,
        "key": base64.b64encode(key).decode(),
    })
    qr_path = None
    try:
        import qrcode
        img = qrcode.make(qr_payload)
        img.save(_QR_PATH)
        qr_path = _QR_PATH
    except Exception as e:
        log.warning("[bridge] QR render failed (%s) — pairing data still "
                    "saved at %s", e, _PAIR_PATH)
    log.info("[bridge] new pairing generated (pid=%s…)", pid[:8])
    return {"pid": pid, "key": key, "qr_path": qr_path}


# ── the bridge ───────────────────────────────────────────────────────

class CloudBridge:
    """Firestore mailbox listener + sender. One instance per process."""

    def __init__(self):
        self._db = None
        self._project_id: Optional[str] = None
        self._pair: Optional[dict] = None
        self._watch = None
        self._process_fn: Optional[Callable[[str], str]] = None
        # Wired by JarvisMainEngine at setup — lets voice skills start
        # the bridge without holding an engine reference themselves.
        self._engine_hook: Optional[Callable[[str], str]] = None
        # Phase 2: laptop → phone. FCM device token (for push when the app
        # is closed) + a callback the GUI/skills use to surface phone
        # status replies (e.g. phone battery %).
        self._device_token: Optional[str] = None
        self._on_phone_status: Optional[Callable[[dict], None]] = None
        # Phase 3: laptop sees the phone screen. Callback fired with
        # (jpeg_bytes, caption) when the phone sends its captured screen.
        self._on_phone_screen: Optional[Callable[[bytes, str], None]] = None
        self._on_phone_screen_np: Optional[Callable[[object], None]] = None
        # Phase 4: LIVE screen share (both ways). A control callback lets the
        # GUI react to phone-originated control (e.g. phone tapped "exit" on
        # its own sharing → close the laptop live window).
        self._on_control: Optional[Callable[[str], None]] = None
        # Fired when the phone first talks to us after a (re)pairing — the GUI
        # uses it to auto-close the QR dialog.
        self._on_phone_connected: Optional[Callable[[], None]] = None
        # Laptop → phone live stream (laptop screen shown on the phone).
        self._laptop_stream_stop = threading.Event()
        self._laptop_stream_thread: Optional[threading.Thread] = None
        self._laptop_streaming = False
        # Phase 4b: LAN fast-path session token (echoed by the phone on the
        # direct socket). Random per pairing session.
        self._lan_token: Optional[str] = None
        # JPEG-fallback capture state (shared dxcam via core.dx_capture).
        self._cam_last = None
        self._cam_last_send = 0.0
        # H.264 video streamer (LAN fast-path); None when not streaming video.
        self._video = None
        # Phase 5: WebRTC streamer (remote-desktop grade, anywhere).
        self._webrtc = None
        # Phase 5b: WebRTC receiver (phone screen → laptop, smooth).
        self._webrtc_rx = None
        # Phase 6: file transfer — reassembly buffers (tid → state) + callback.
        self._file_rx: dict = {}
        self._on_file_received: Optional[Callable[[str], None]] = None
        self._presence_stop = threading.Event()
        self._presence_thread: Optional[threading.Thread] = None
        self._started = False
        # start() has several callers — the engine's boot (now on its own
        # thread), the bridge subsystem's boot and retry, `rearm` after a key
        # rotation. The `_started` flag alone let two concurrent callers both
        # pass the check and install two Firestore listeners; this serialises
        # them so "idempotent" holds across threads too.
        self._start_lock = threading.Lock()
        self._seen_ids: set = set()
        # Phase 7: continuous two-way clipboard mirror. A poller watches the
        # laptop clipboard; _clip_last holds the last value we sent OR received,
        # so neither side echoes a change back and loops forever.
        self._clip_sync = True
        self._clip_last = ""
        self._clip_stop = threading.Event()
        self._clip_thread: Optional[threading.Thread] = None

    # ── setup ────────────────────────────────────────────────────
    def available(self) -> tuple[bool, str]:
        """(usable, human reason)."""
        if not os.path.isfile(_SA_KEY_PATH):
            return False, ("Service-account key missing — download it from "
                           "Firebase console → Project settings → Service "
                           f"accounts, save as {_SA_KEY_PATH}")
        try:
            import firebase_admin  # noqa: F401
        except Exception as e:
            return False, f"firebase-admin not importable: {e}"
        return True, "ok"

    def _connect(self) -> bool:
        if self._db is not None:
            return True
        ok, why = self.available()
        if not ok:
            log.info("[bridge] unavailable: %s", why)
            return False
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            cred = credentials.Certificate(_SA_KEY_PATH)
            with open(_SA_KEY_PATH, encoding="utf-8") as f:
                self._project_id = json.load(f).get("project_id")
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self._db = firestore.client()
            log.info("[bridge] connected to Firebase project %s",
                     self._project_id)
            return True
        except Exception as e:
            log.warning("[bridge] connect failed: %s", e)
            return False

    def pair(self) -> Optional[dict]:
        """Create a fresh pairing (rotates key). Returns pairing info."""
        if not self._connect():
            return None
        # Rotation kills any listener bound to the OLD pair id first.
        self.stop()
        info = new_pairing(self._project_id or "unknown")
        self._pair = {"pid": info["pid"], "key": info["key"]}
        return info

    def set_engine_hook(self, fn: Callable[[str], str]) -> None:
        self._engine_hook = fn

    # ── run ──────────────────────────────────────────────────────
    def start(self, process_fn: Optional[Callable[[str], str]] = None
              ) -> tuple[bool, str]:
        """Begin listening for phone messages. Idempotent.
        ``process_fn=None`` falls back to the engine hook."""
        with self._start_lock:
            return self._start_locked(process_fn)

    def _start_locked(self, process_fn: Optional[Callable[[str], str]] = None
                      ) -> tuple[bool, str]:
        if self._started:
            return True, "already running"
        if bridge_disabled():
            return False, "bridge disabled (AERIS_DISABLE_BRIDGE)"
        fn = process_fn or self._engine_hook
        if fn is None:
            return False, "brain hook not wired yet (boot incomplete?)"
        if not self._connect():
            # `available()` answers "are the preconditions there?", which is
            # NOT why we are here — _connect() can fail with a perfectly good
            # key when the network is down or Firebase is unreachable. In
            # that case available() says "ok", and returning it made a
            # connect failure report the reason "ok". Say what happened.
            ok, why = self.available()
            return False, (why if not ok else
                           "connect failed — Firebase unreachable "
                           "(network down?)")
        self._pair = load_pair()
        if not self._pair:
            return False, ("Not paired yet — say 'phone pair karo' to "
                           "generate the QR.")
        self._process_fn = fn
        # Clear the stop flag — a prior stop()/pair() set it, and without
        # this the new presence thread exits instantly so the phone shows
        # the laptop as OFFLINE forever despite commands working.
        self._presence_stop.clear()

        col = (self._db.collection("bridge").document(self._pair["pid"])
               .collection("toLaptop"))
        self._watch = col.on_snapshot(self._on_snapshot)

        self._presence_stop.clear()
        self._presence_thread = threading.Thread(
            target=self._presence_loop, name="BridgePresence", daemon=True)
        self._presence_thread.start()
        self._started = True
        if self._clip_sync:
            self.start_clipboard_sync()
        log.info("[bridge] listening (pid=%s…)", self._pair["pid"][:8])
        try:
            from core.log_setup import event
            event("bridge_started", pid_prefix=self._pair["pid"][:8])
        except Exception:
            pass
        return True, "listening"

    def stop(self) -> None:
        self._started = False
        self._presence_stop.set()
        self.stop_clipboard_sync()
        try:
            if self._watch is not None:
                self._watch.unsubscribe()
        except Exception:
            pass
        self._watch = None

    # ── Phase 7: continuous two-way clipboard mirror ─────────────────
    def start_clipboard_sync(self) -> None:
        """Watch the laptop clipboard and push any change to the phone.
        Idempotent. The phone→laptop direction rides the existing
        `set_clipboard` message; this adds the laptop→phone half so copy on
        either device shows up on the other, automatically."""
        if self._clip_thread and self._clip_thread.is_alive():
            return
        try:
            import pyperclip
            self._clip_last = (pyperclip.paste() or "")  # seed; don't send it
        except Exception:
            self._clip_last = ""
        self._clip_stop.clear()
        self._clip_thread = threading.Thread(
            target=self._clip_loop, name="BridgeClipboard", daemon=True)
        self._clip_thread.start()
        log.info("[bridge] clipboard sync started")

    def stop_clipboard_sync(self) -> None:
        self._clip_stop.set()
        self._clip_thread = None

    def set_clipboard_sync(self, on: bool) -> None:
        self._clip_sync = bool(on)
        if on and self._started:
            self.start_clipboard_sync()
        else:
            self.stop_clipboard_sync()

    def _clip_loop(self) -> None:
        try:
            import pyperclip
        except Exception as e:
            log.warning("[bridge] clipboard sync off (pyperclip: %s)", e)
            return
        # This loop and skills/clipboard_history's watcher both poll the Win32
        # clipboard from their own threads; unserialized that is a use-after-
        # free on the clipboard handle (0xC0000374). See core/clipboard_lock.
        from core.clipboard_lock import install as _install_clip_lock
        _install_clip_lock()
        while not self._clip_stop.is_set():
            try:
                cur = pyperclip.paste() or ""
                if cur and cur != self._clip_last:
                    self._clip_last = cur
                    self.send_to_phone({
                        "id": _secrets.token_hex(8), "type": "clipboard",
                        "text": cur[:8000], "reply_to": None,
                        "extra": {"auto": True},
                    })
                    log.info("[bridge] clipboard → phone (%d chars)", len(cur))
            except Exception:
                pass
            self._clip_stop.wait(1.0)

    def status(self) -> dict:
        ok, why = self.available()
        return {
            "sa_key": ok, "reason": why,
            "paired": bool(self._pair or load_pair()),
            "listening": self._started,
            "project": self._project_id,
        }

    # ── internals ────────────────────────────────────────────────
    def _on_snapshot(self, snapshot, changes, _read_time):
        """Runs on the Firestore SDK's own thread — hand work off fast."""
        for change in changes:
            if change.type.name != "ADDED":
                continue
            doc = change.document
            threading.Thread(target=self._handle_doc, args=(doc,),
                             name="BridgeMsg", daemon=True).start()

    def _handle_doc(self, doc) -> None:
        try:
            data = doc.to_dict() or {}
            # Delete first — even a crashing message must never replay.
            doc.reference.delete()
            ts = data.get("ts")
            if isinstance(ts, (int, float)) and \
                    time.time() - ts > _MAX_MSG_AGE_S:
                log.info("[bridge] stale message dropped (%.0fs old)",
                         time.time() - ts)
                return
            payload = decrypt_payload(self._pair["key"], data)
            if not payload:
                return
            # A message decrypted with the current key ⇒ the phone is paired
            # and talking. Signal the GUI (auto-closes the QR dialog).
            if self._on_phone_connected:
                try:
                    self._on_phone_connected()
                except Exception:
                    pass
            mid = payload.get("id") or ""
            if mid and mid in self._seen_ids:
                return
            if mid:
                self._seen_ids.add(mid)
                if len(self._seen_ids) > 500:
                    self._seen_ids = set(list(self._seen_ids)[-200:])

            ptype = payload.get("type") or "chat"
            extra = payload.get("extra") or {}

            # ── control messages from the phone (not chat) ──
            if ptype == "register_token":
                # Phone shared its FCM device token so the laptop can push
                # even when the app is closed. Persist it with the pairing.
                tok = extra.get("token") or payload.get("text") or ""
                if tok:
                    self._save_device_token(tok)
                    log.info("[bridge] registered phone FCM token (…%s)",
                             tok[-8:])
                return
            if ptype == "phone_status":
                # Reply to a "phone battery"/status request — surface it on
                # the laptop (chat panel / logs) via the status callback.
                if self._on_phone_status:
                    try:
                        self._on_phone_status(extra)
                    except Exception:
                        pass
                log.info("[bridge] phone status: %s", extra)
                return
            if ptype == "phone_screen":
                # Phone → laptop: the phone captured its own screen and
                # sent it (base64 JPEG). Hand the bytes to the callback,
                # which OCRs / displays it laptop-side.
                b64 = extra.get("b64") or ""
                if b64 and self._on_phone_screen:
                    try:
                        self._on_phone_screen(base64.b64decode(b64),
                                              payload.get("text") or "")
                    except Exception as e:
                        log.warning("[bridge] phone_screen handle failed: %s", e)
                return
            if ptype == "file_chunk":
                self._recv_file_chunk(extra)
                return
            if ptype == "webrtc_answer":
                if self._webrtc:
                    self._webrtc.on_answer(extra.get("sdp") or "")
                return
            if ptype == "webrtc_ice":
                if self._webrtc:
                    self._webrtc.on_ice(extra)
                return
            if ptype == "phone_webrtc_offer":
                if self._webrtc_rx:
                    self._webrtc_rx.on_offer(extra.get("sdp") or "")
                return
            if ptype == "phone_webrtc_ice":
                if self._webrtc_rx:
                    self._webrtc_rx.on_ice(extra)
                return
            if ptype == "control":
                # Phase 4: live screen-share control from the phone.
                action = extra.get("action") or payload.get("text") or ""
                log.info("[bridge] phone control: %s", action)
                if action == "start_laptop_stream":
                    self.start_laptop_stream()
                elif action == "stop_laptop_stream":
                    self.stop_webrtc_stream()
                    self.stop_laptop_stream()
                elif action in ("stop_phone_stream", "phone_stream_stopped"):
                    # Phone stopped sharing its own screen — let the GUI close
                    # the laptop-side live window.
                    if self._on_control:
                        try:
                            self._on_control(action)
                        except Exception:
                            pass
                return
            if ptype == "set_clipboard":
                # Phone → laptop clipboard sync: put the phone's clipboard
                # text onto the laptop clipboard.
                txt = payload.get("text") or extra.get("text") or ""
                if txt:
                    try:
                        import pyperclip
                        # Remember it BEFORE copying so our own poller sees the
                        # value as "already known" and doesn't bounce it back.
                        self._clip_last = txt
                        pyperclip.copy(txt)
                        log.info("[bridge] clipboard set from phone (%d chars)",
                                 len(txt))
                    except Exception as e:
                        log.warning("[bridge] clipboard set failed: %s", e)
                return

            # Continuity envelope (extra.env) — typed messages (presence
            # beats, goal capture, mem requests) bypass the brain hook and
            # go to the ContinuityRouter. An ack (e.g. goal-capture "yaad
            # rakhunga") is spoken back on the phone as a normal response.
            _extra = payload.get("extra")
            _env = _extra.get("env") if isinstance(_extra, dict) else None
            if _env is not None:
                try:
                    from core.continuity import get_router
                    ack = get_router().inbound(_env)
                    if ack:
                        self.send_to_phone({
                            "id": _secrets.token_hex(8), "type": "response",
                            "text": ack, "reply_to": mid, "extra": {},
                        })
                except Exception as e:
                    log.debug("[bridge] continuity inbound failed: %s", e)
                return

            text = (payload.get("text") or "").strip()
            log.info("[bridge] phone → laptop: %r", text[:60])
            if not text or self._process_fn is None:
                return
            try:
                reply = self._process_fn(text) or ""
            except Exception as e:
                reply = f"Bridge error: {e}"
            self.send_to_phone({
                "id": _secrets.token_hex(8), "type": "response",
                "text": reply, "reply_to": mid, "extra": {},
            })
        except Exception as e:
            log.warning("[bridge] message handling failed: %s", e)

    # ── laptop → phone (Phase 2) ─────────────────────────────────────
    def _token_path(self) -> str:
        return os.path.join(_SECRETS_DIR, "phone_token.txt")

    def _save_device_token(self, token: str) -> None:
        self._device_token = token
        try:
            os.makedirs(_SECRETS_DIR, exist_ok=True)
            with open(self._token_path(), "w", encoding="utf-8") as f:
                f.write(token)
        except Exception as e:
            log.warning("[bridge] could not persist phone token: %s", e)

    def _load_device_token(self) -> Optional[str]:
        if self._device_token:
            return self._device_token
        try:
            with open(self._token_path(), encoding="utf-8") as f:
                self._device_token = f.read().strip() or None
        except Exception:
            self._device_token = None
        return self._device_token

    def on_phone_status(self, fn: Callable[[dict], None]) -> None:
        """Register a callback invoked with the phone's status reply
        (e.g. {'battery': 82, 'charging': True})."""
        self._on_phone_status = fn

    def on_phone_screen(self, fn: Callable[[bytes, str], None]) -> None:
        """Register a callback invoked with (jpeg_bytes, caption) when the
        phone sends its captured screen (Phase 3, laptop sees phone)."""
        self._on_phone_screen = fn

    def on_phone_screen_np(self, fn: Callable[[object], None]) -> None:
        """Register a numpy sink for phone→laptop WebRTC frames (Phase 2). When
        set, decoded BGR frames go straight to the GUI with no JPEG round-trip.
        The JPEG callback (on_phone_screen) stays the fallback for relay/LAN."""
        self._on_phone_screen_np = fn

    def on_control(self, fn: Callable[[str], None]) -> None:
        """Register a callback for phone-originated control actions (Phase 4
        live share) — e.g. 'stop_phone_stream' so the GUI closes its live
        window when the phone taps exit."""
        self._on_control = fn

    def on_phone_connected(self, fn: Callable[[], None]) -> None:
        """Register a callback fired when the phone first talks to us with the
        current key (paired) — GUI auto-closes the QR dialog."""
        self._on_phone_connected = fn

    def request_phone_screen(self) -> bool:
        """Ask the phone to capture + send its screen (single frame)."""
        return self.send_action("request_screen")

    # ── Phase 4: LIVE screen share ───────────────────────────────────
    def start_phone_stream(self) -> bool:
        """Ask the phone to start streaming ITS screen (repeated frames)
        until stopped — laptop shows them live (LAN if same WiFi)."""
        self._ensure_lan_and_advertise()
        return self.send_action("start_screen_stream")

    def stop_phone_stream(self) -> bool:
        """Tell the phone to stop streaming its screen — over LAN (instant,
        reliable) AND the relay (fallback if not on LAN)."""
        self.stop_phone_webrtc()
        try:
            from core import lan_link
            lan_link.get().send_control("stop_screen_stream")
        except Exception:
            pass
        return self.send_action("stop_screen_stream")

    # ── LAN fast-path (Phase 4b) ─────────────────────────────────────
    def _ensure_lan_and_advertise(self) -> None:
        """Start the LAN server (idempotent) and hand the phone our LAN
        endpoints + session token through the ENCRYPTED relay so it can
        connect directly. Best-effort — failure just keeps us on the relay."""
        try:
            from core import lan_link
            link = lan_link.get()
            if not self._lan_token:
                self._lan_token = _secrets.token_hex(16)
            link.start(self._lan_token)
            # Phone frames arriving over LAN feed the SAME callback the relay
            # path uses, so the GUI live window updates from either transport.
            link.on_phone_frame(
                lambda jpg: self._on_phone_screen(jpg, "")
                if self._on_phone_screen else None)
            # Phone → laptop control over LAN (reliable stop, no flaky relay).
            link.on_control(self._handle_lan_control)
            ep = link.endpoints()
            self.send_to_phone({
                "id": _secrets.token_hex(8), "type": "lan_offer",
                "text": "", "reply_to": None,
                "extra": {"ips": ep["ips"], "port": ep["port"],
                          "token": self._lan_token},
            })
            log.info("[bridge] lan_offer sent (ips=%s port=%s)",
                     ep["ips"], ep["port"])
        except Exception as e:
            log.info("[bridge] LAN advertise skipped: %s", e)

    # ── Phase 5: WebRTC remote-desktop mirroring ─────────────────────
    def start_webrtc_stream(self) -> bool:
        """Offer a WebRTC screen-mirror session to the phone. Signalling goes
        over the relay; the video flows peer-to-peer (UDP, adaptive, STUN)."""
        self.stop_webrtc_stream()
        if self._db is None or self._pair is None:
            if not self._connect():
                return False
            self._pair = self._pair or load_pair()
        try:
            from core import webrtc_stream

            def _send_signal(kind: str, payload: dict) -> None:
                self.send_to_phone({
                    "id": _secrets.token_hex(8), "type": kind,
                    "text": "", "reply_to": None, "extra": payload,
                })

            # Tunable via data/settings.json. Defaults measured best on this
            # laptop: 1280 wide @ 60 (the CPU colour-convert makes 1920 a net
            # loss — see docs/MIRRORING_V2_ARCHITECTURE.md Phase 1). Phase 6's
            # adaptive ladder lowers width automatically on a weak link.
            try:
                from core import settings
                max_px = int(settings.get("mirror_max_width", 1280))
                fps = int(settings.get("mirror_fps", 60))
            except Exception:
                max_px, fps = 1280, 60
            self._webrtc = webrtc_stream.WebRTCStreamer(
                _send_signal, max_px=max(320, min(1920, max_px)),
                fps=max(10, min(60, fps)))
            ok = self._webrtc.start()
            if not ok:
                self._webrtc = None
                return False
            # If P2P can't establish (strict NAT + no TURN), fall back to the
            # relay/LAN path so the user still sees SOMETHING.
            threading.Thread(target=self._webrtc_fallback_watch,
                             args=(self._webrtc,), name="WebRTCFallback",
                             daemon=True).start()
            return True
        except Exception as e:
            log.warning("[bridge] WebRTC start failed: %s", e)
            self._webrtc = None
            return False

    def _webrtc_fallback_watch(self, vs) -> None:
        """After ~13s, if WebRTC still hasn't connected, switch to the
        relay/LAN path (laggy but visible) instead of leaving a black screen."""
        time.sleep(13)
        try:
            if self._webrtc is vs and not vs.is_connected():
                log.info("[bridge] WebRTC not connected in 13s — "
                         "falling back to relay/LAN screen path")
                self.stop_webrtc_stream()
                self.start_laptop_stream()
        except Exception as e:
            log.info("[bridge] webrtc fallback check failed: %s", e)

    # ── Phase 5b: phone screen → laptop over WebRTC ──────────────────
    def start_phone_webrtc(self) -> bool:
        """Ask the phone to stream ITS screen to the laptop over WebRTC
        (smooth). The phone is the offerer; we answer via the receiver."""
        self.stop_phone_webrtc()
        if self._db is None or self._pair is None:
            if not self._connect():
                return False
            self._pair = self._pair or load_pair()
        try:
            from core import webrtc_stream

            def _send_signal(kind: str, payload: dict) -> None:
                self.send_to_phone({
                    "id": _secrets.token_hex(8), "type": kind,
                    "text": "", "reply_to": None, "extra": payload,
                })

            def _on_frame(jpg: bytes) -> None:
                if self._on_phone_screen:
                    try:
                        self._on_phone_screen(jpg, "")
                    except Exception:
                        pass

            def _on_frame_np(img) -> None:
                if self._on_phone_screen_np:
                    try:
                        self._on_phone_screen_np(img)
                    except Exception:
                        pass

            self._webrtc_rx = webrtc_stream.WebRTCReceiver(
                _send_signal, _on_frame, quality=60,
                on_frame_np=(_on_frame_np if self._on_phone_screen_np
                             else None))
            self._webrtc_rx.start()
            # Tell the phone to capture + offer its screen. Pass the same ICE
            # servers (STUN + optional TURN) so NAT traversal works both ways.
            try:
                ice = webrtc_stream.load_ice_servers()
            except Exception:
                ice = []
            return self.send_action("start_phone_webrtc", {"ice": ice})
        except Exception as e:
            log.warning("[bridge] phone WebRTC start failed: %s", e)
            self._webrtc_rx = None
            return False

    def stop_phone_webrtc(self) -> None:
        if self._webrtc_rx is not None:
            try:
                self._webrtc_rx.stop()
            except Exception:
                pass
            self._webrtc_rx = None

    def stop_webrtc_stream(self) -> None:
        if self._webrtc is not None:
            try:
                self._webrtc.stop()
            except Exception:
                pass
            self._webrtc = None

    # ── Phase 6: file transfer (chunked over the relay, works anywhere) ──
    _FILE_CHUNK = 400_000     # raw bytes/chunk → ~533 KB b64, under 1 MB doc

    def on_file_received(self, fn: Callable[[str], None]) -> None:
        self._on_file_received = fn

    def send_file_to_phone(self, path: str) -> tuple[bool, str]:
        """Chunk a file and stream it to the phone (reassembled there)."""
        if not os.path.isfile(path):
            return False, "file nahi mila"
        try:
            name = os.path.basename(path)
            with open(path, "rb") as f:
                data = f.read()
            total = max(1, (len(data) + self._FILE_CHUNK - 1) //
                        self._FILE_CHUNK)
            tid = _secrets.token_hex(8)
            for i in range(total):
                piece = data[i * self._FILE_CHUNK:(i + 1) * self._FILE_CHUNK]
                ok = self.send_to_phone({
                    "id": _secrets.token_hex(8), "type": "file_chunk",
                    "text": name, "reply_to": None,
                    "extra": {"tid": tid, "name": name, "index": i,
                              "total": total, "size": len(data),
                              "data": base64.b64encode(piece).decode()},
                })
                if not ok:
                    return False, "send fail (chunk %d)" % i
            return True, f"{name} bhej diya ({total} chunk, {len(data)//1024} KB)"
        except Exception as e:
            return False, f"file send error: {e}"

    def _recv_file_chunk(self, extra: dict) -> None:
        """Reassemble an incoming file from the phone; save to ~/Downloads."""
        tid = extra.get("tid")
        if not tid:
            return
        st = self._file_rx.setdefault(
            tid, {"chunks": {}, "total": int(extra.get("total", 1)),
                  "name": extra.get("name", "aeris_file")})
        try:
            st["chunks"][int(extra.get("index", 0))] = \
                base64.b64decode(extra.get("data", ""))
        except Exception:
            return
        if len(st["chunks"]) < st["total"]:
            return
        self._file_rx.pop(tid, None)
        try:
            data = b"".join(st["chunks"][i] for i in range(st["total"]))
            dl = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(dl, exist_ok=True)
            dest = os.path.join(dl, st["name"])
            base, ext = os.path.splitext(dest)
            n = 1
            while os.path.exists(dest):
                dest = f"{base} ({n}){ext}"
                n += 1
            with open(dest, "wb") as f:
                f.write(data)
            log.info("[bridge] file received from phone → %s", dest)
            if self._on_file_received:
                try:
                    self._on_file_received(dest)
                except Exception:
                    pass
        except Exception as e:
            log.warning("[bridge] file reassembly failed: %s", e)

    def _handle_lan_control(self, action: str) -> None:
        """Control action from the phone over the LAN socket."""
        log.info("[bridge] LAN control: %s", action)
        if action == "stop_laptop_stream":
            self.stop_webrtc_stream()
            self.stop_laptop_stream()
        elif action in ("stop_phone_stream", "phone_stream_stopped"):
            if self._on_control:
                try:
                    self._on_control(action)
                except Exception:
                    pass

    def _emit_laptop_frame(self, jpg: bytes) -> None:
        """Send a laptop-screen frame — over the LAN socket if the phone is
        connected there, else fall back to the relay."""
        try:
            from core import lan_link
            if lan_link.get().send_laptop_frame(jpg):
                return
        except Exception:
            pass
        self.send_laptop_frame(jpg)

    def is_laptop_streaming(self) -> bool:
        return self._laptop_streaming

    def _paint_cursor(self, frame, scale: float) -> None:
        """Draw the mouse cursor onto a (writable) captured frame — dxcam/mss
        don't include the hardware pointer overlay."""
        try:
            from core.webrtc_stream import _cursor_xy, _draw_cursor
            cx, cy = _cursor_xy()
            _draw_cursor(frame, int(cx * scale), int(cy * scale))
        except Exception:
            pass

    def _capture_laptop_jpeg(self, max_px: int = 1000,
                             quality: int = 45) -> Optional[bytes]:
        """Grab the primary monitor, downscale hard + JPEG-compress for a
        light live frame (small doc → cheap + fast over the relay).

        Runs under ENCODER_LOCK: mss/PIL native work must NOT overlap a torch
        SentenceTransformer encode on the brain thread — concurrent native
        heap activity triggers 0xC0000374 heap corruption (the same class of
        crash the shared encoder had). Serializing them keeps the GUI alive
        when the user types a command mid-stream."""
        import time as _t
        try:
            import cv2
            from core.encoder_lock import ENCODER_LOCK
            from core import dx_capture
            now = _t.time()
            cam = dx_capture.get()
            if cam is not None:
                # dxcam (Desktop Duplication): grab() returns a NEW frame only
                # when the screen changed, else None → we reuse the last frame
                # and skip re-encoding a static screen (huge CPU saving) except
                # for a periodic keepalive so a just-connected phone syncs.
                with ENCODER_LOCK:
                    fr = cam.grab()
                changed = fr is not None
                if changed:
                    self._cam_last = fr
                if not changed and (now - self._cam_last_send) < 0.7:
                    return None
                frame = self._cam_last
                if frame is None:
                    # No dxcam history yet (e.g. just after the WebRTC→relay
                    # fallback) and a static screen gives no new frame — seed
                    # the first frame with a one-shot mss grab so the phone
                    # isn't stuck blank until something on screen changes.
                    try:
                        import mss
                        import numpy as np
                        with ENCODER_LOCK:
                            sct = self._mss_for_thread()
                            mon = sct.monitors[1] if len(sct.monitors) > 1 \
                                else sct.monitors[0]
                            raw = sct.grab(mon)
                            bgra = np.asarray(raw)
                            frame = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
                        self._cam_last = frame
                    except Exception:
                        return None
                with ENCODER_LOCK:
                    h, w = frame.shape[:2]
                    scale = min(1.0, max_px / float(max(w, h)))
                    if scale < 1.0:
                        frame = cv2.resize(
                            frame, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_AREA)
                    else:
                        frame = frame.copy()   # writable for cursor draw
                    self._paint_cursor(frame, scale)
                    ok, enc = cv2.imencode(
                        ".jpg", frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
                if not ok:
                    return None
                self._cam_last_send = now
                return enc.tobytes()
            # ── Fallback: mss + cv2 (no dxcam) ──
            import mss
            import numpy as np
            sct = self._mss_for_thread()
            with ENCODER_LOCK:
                mon = sct.monitors[1] if len(sct.monitors) > 1 \
                    else sct.monitors[0]
                raw = sct.grab(mon)
                frame = np.asarray(raw)               # BGRA
                h, w = frame.shape[:2]
                scale = min(1.0, max_px / float(max(w, h)))
                if scale < 1.0:
                    frame = cv2.resize(
                        frame, (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_AREA)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self._paint_cursor(frame, scale)
                ok, enc = cv2.imencode(
                    ".jpg", frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
            self._cam_last_send = now
            return enc.tobytes() if ok else None
        except Exception as e:
            log.warning("[bridge] laptop capture failed: %s", e)
            return None

    def _mss_for_thread(self):
        """One mss instance per capture thread (mss objects are not shareable
        across threads). Rebuilt when the stream thread changes."""
        import mss
        cur = threading.current_thread()
        if getattr(self, "_mss_owner", None) is not cur or \
                getattr(self, "_mss", None) is None:
            self._mss = mss.mss()
            self._mss_owner = cur
        return self._mss

    def send_laptop_frame(self, jpeg: bytes, caption: str = "") -> bool:
        """Send one laptop-screen frame to the phone's live view."""
        try:
            b64 = base64.b64encode(jpeg).decode()
        except Exception:
            return False
        return self.send_to_phone({
            "id": _secrets.token_hex(8), "type": "laptop_screen",
            "text": caption, "reply_to": None,
            "extra": {"format": "jpeg", "b64": b64},
        })

    def start_laptop_stream(self, interval: float = 1.3,
                            max_seconds: int = 300) -> bool:
        """Stream the laptop screen to the phone every ``interval`` seconds
        until stopped (or the ``max_seconds`` free-tier safety cap)."""
        # Always tear down any prior loop FIRST — otherwise a quick
        # stop→start leaves the old (exiting) thread alive and this call
        # no-ops, so the restart silently does nothing.
        self.stop_laptop_stream()
        if self._db is None or self._pair is None:
            if not self._connect():
                return False
            self._pair = self._pair or load_pair()
        self._ensure_lan_and_advertise()
        self._laptop_stream_stop.clear()

        def _loop():
            started = time.time()
            try:
                while not self._laptop_stream_stop.is_set():
                    try:
                        from core import lan_link
                        on_lan = lan_link.get().is_connected()
                    except Exception:
                        on_lan = False

                    if on_lan:
                        # Same WiFi → smooth H.264 video (60 fps, GPU-encoded).
                        if self._video is None or not self._video.is_running():
                            self._ensure_video()
                        if self._video is not None and self._video.is_running():
                            # ffmpeg + streamer threads do the work; idle here.
                            self._laptop_stream_stop.wait(0.25)
                            continue
                        # H.264 unavailable → JPEG frames over the socket.
                        jpg = self._capture_laptop_jpeg(max_px=1366, quality=55)
                        if jpg:
                            self._emit_laptop_frame(jpg)
                        if self._laptop_stream_stop.wait(0.02):
                            break
                        continue

                    # Off-LAN → relay JPEG (laggy but works anywhere).
                    if self._video is not None:
                        self._video.stop()
                        self._video = None
                    jpg = self._capture_laptop_jpeg(max_px=1000, quality=40)
                    if jpg:
                        self._emit_laptop_frame(jpg)
                    if time.time() - started > max_seconds:
                        log.info("[bridge] laptop stream auto-stopped "
                                 "(%ss cap)", max_seconds)
                        break
                    if self._laptop_stream_stop.wait(interval):
                        break
            finally:
                if self._video is not None:
                    try:
                        self._video.stop()
                    except Exception:
                        pass
                    self._video = None
                self._laptop_streaming = False
                log.info("[bridge] laptop screen stream ended")

        self._laptop_streaming = True
        self._laptop_stream_stop.clear()
        self._laptop_stream_thread = threading.Thread(
            target=_loop, name="LaptopScreenStream", daemon=True)
        self._laptop_stream_thread.start()
        log.info("[bridge] laptop screen stream started")
        return True

    def _ensure_video(self) -> None:
        """Spin up the H.264 video streamer (idempotent). Frames + info go
        straight down the LAN socket via lan_link."""
        if self._video is not None and self._video.is_running():
            return
        try:
            from core import lan_link, video_stream
            link = lan_link.get()
            vs = video_stream.VideoStreamer(
                send_au=link.send_video_au,
                send_info=link.send_video_info,
                fps=30, bitrate="2500k", out_width=1280)
            # A phone that (re)connects mid-stream needs the params again.
            link.on_client_connect(vs.resend_info)
            if vs.start():
                self._video = vs
            else:
                self._video = None
        except Exception as e:
            log.warning("[bridge] H.264 video start failed: %s", e)
            self._video = None

    def stop_laptop_stream(self) -> None:
        """Stop the loop and WAIT for it to actually exit, so a following
        start() begins from a clean slate."""
        self._laptop_stream_stop.set()
        if self._video is not None:
            try:
                self._video.stop()
            except Exception:
                pass
            self._video = None
        t = self._laptop_stream_thread
        if t is not None and t.is_alive() \
                and t is not threading.current_thread():
            t.join(timeout=3.0)
        self._laptop_stream_thread = None
        self._laptop_streaming = False

    def send_action(self, action: str, extra: Optional[dict] = None) -> bool:
        """Send a laptop → phone ACTION over the encrypted mailbox
        (ring / get_battery / …). Delivered when the app is open; use
        send_push() for closed-app delivery."""
        return self.send_to_phone({
            "id": _secrets.token_hex(8), "type": "phone_action",
            "text": action, "reply_to": None,
            "extra": {"action": action, **(extra or {})},
        })

    def send_push(self, title: str, body: str,
                  data: Optional[dict] = None) -> tuple[bool, str]:
        """Send an FCM push so the phone reacts even when the app is
        CLOSED (find-my-phone ring, alerts). Needs a registered token."""
        token = self._load_device_token()
        if not token:
            return False, ("Phone token nahi mila — app kholo aur ek baar "
                           "pair/connect karo taaki token register ho.")
        if not self._connect():
            return False, "Firebase connect fail."
        try:
            from firebase_admin import messaging
            msg = messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                android=messaging.AndroidConfig(priority="high"),
            )
            mid = messaging.send(msg)
            log.info("[bridge] FCM push sent: %s", mid)
            return True, mid
        except Exception as e:
            log.warning("[bridge] FCM push failed: %s", e)
            return False, str(e)

    def send_image_to_phone(self, path: str, caption: str = "") -> tuple[bool, str]:
        """Downscale + JPEG-compress an image and send it to the phone as a
        base64 payload (no Firebase Storage needed — fits a Firestore doc).

        A full screenshot is downscaled to ≤1280px and ~q55 so the
        encrypted+base64 doc stays well under Firestore's 1 MB limit.
        """
        if not os.path.isfile(path):
            return False, "image file nahi mila"
        try:
            from PIL import Image
            import io
            img = Image.open(path).convert("RGB")
            w, h = img.size
            scale = min(1.0, 1280.0 / max(w, h))
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)),
                                 Image.LANCZOS)
            buf = io.BytesIO()
            q = 55
            img.save(buf, format="JPEG", quality=q)
            # If still too big, drop quality until it fits ~650 KB raw
            # (base64 grows ~4/3 → ~870 KB, under the 1 MB doc cap).
            while buf.tell() > 650_000 and q > 25:
                q -= 10
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=q)
            b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            return False, f"image process fail: {e}"
        ok = self.send_to_phone({
            "id": _secrets.token_hex(8), "type": "image",
            "text": caption, "reply_to": None,
            "extra": {"format": "jpeg", "b64": b64},
        })
        return (ok, "sent" if ok else "send fail")

    def send_to_phone(self, payload: dict) -> bool:
        """Encrypt + drop a message in the phone's mailbox."""
        if self._db is None or self._pair is None:
            return False
        try:
            doc = encrypt_payload(self._pair["key"], payload)
            doc["ts"] = time.time()
            (self._db.collection("bridge").document(self._pair["pid"])
             .collection("toPhone").add(doc))
            return True
        except Exception as e:
            log.warning("[bridge] send failed: %s", e)
            return False

    def _presence_loop(self) -> None:
        # Write the FIRST heartbeat immediately so the phone flips to
        # "online" within a second of pairing (not after the first 60 s
        # interval), then refresh on each tick.
        while True:
            try:
                (self._db.collection("bridge")
                 .document(self._pair["pid"])
                 .set({"laptop_ts": time.time()}, merge=True))
            except Exception:
                pass
            if self._presence_stop.wait(_PRESENCE_INTERVAL_S):
                return


_BRIDGE: Optional[CloudBridge] = None
_BRIDGE_LOCK = threading.Lock()


def get_bridge() -> CloudBridge:
    global _BRIDGE
    with _BRIDGE_LOCK:
        if _BRIDGE is None:
            _BRIDGE = CloudBridge()
        return _BRIDGE
