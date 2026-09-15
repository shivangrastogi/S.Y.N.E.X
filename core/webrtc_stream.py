"""WebRTC screen mirroring — remote-desktop-grade laptop → phone (Phase 5).

Why WebRTC (over the earlier H.264-over-TCP path): it is exactly what
AnyDesk / Parsec / Google Meet use, so it brings the three things a raw
socket can't:

  * UDP transport with congestion control + loss concealment — a late/lost
    packet degrades quality briefly instead of stalling the whole stream
    (no more "backlog — waiting IDR" freezes);
  * ADAPTIVE bitrate — the encoder tracks the real link and scales quality
    up/down automatically, so a weak 2.4 GHz WiFi still stays fluid;
  * NAT traversal (STUN/ICE) — a direct peer link forms even across
    different networks, so same-WiFi (and the USB cable) stop being a
    requirement.

Signalling (the tiny SDP offer/answer handshake) rides the existing
Firebase relay; the video itself flows peer-to-peer over UDP. aiortc
gathers ICE non-trickle (candidates are embedded in the SDP), so the phone
only has to trickle its own — kept simple below.

The laptop is the OFFERER: it adds a screen VideoStreamTrack + a
'control' datachannel (phone → laptop mouse), makes the offer, and waits
for the phone's answer.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)

# Phase 1: swap aiortc's stock libx264-*medium* encoder for a low-latency one
# (real hardware if a usable NVENC/AMF GPU is present, else libx264-ultrafast).
# Best-effort — on failure aiortc keeps its default and mirroring still works.
try:
    from core import hw_encoder as _hw_encoder
    _HW_ENCODER = _hw_encoder.install()
    log.info("[webrtc] low-latency encoder installed: %s", _HW_ENCODER)
except Exception as _e:  # noqa: BLE001
    _HW_ENCODER = None
    log.warning("[webrtc] low-latency encoder unavailable, "
                "using aiortc default: %s", _e)

_STUN = "stun:stun.l.google.com:19302"

# Optional TURN relay for the ~10% of cases where P2P can't punch through
# (both peers behind strict/symmetric NAT — e.g. mobile data ↔ office WiFi).
# Drop a JSON file here to enable "works truly anywhere":
#   data/secrets/turn.json  →  [{"urls": "turn:host:3478",
#                                "username": "u", "credential": "p"}]
import os as _os
_TURN_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    "data", "secrets", "turn.json")


def load_ice_servers() -> list:
    """[{urls, username?, credential?}] — Google STUN always, plus any TURN
    servers the user configured. Sent to the phone so both sides match."""
    servers = [{"urls": _STUN}]
    try:
        if _os.path.isfile(_TURN_PATH):
            import json
            with open(_TURN_PATH, encoding="utf-8") as f:
                extra = json.load(f)
            if isinstance(extra, dict):
                extra = [extra]
            for s in extra:
                if isinstance(s, dict) and s.get("urls"):
                    servers.append({k: v for k, v in s.items()
                                    if k in ("urls", "username", "credential")})
            log.info("[webrtc] loaded %d TURN server(s)", len(servers) - 1)
    except Exception as e:
        log.info("[webrtc] turn.json load skipped: %s", e)
    return servers


def _cursor_xy():
    """Current mouse position in screen pixels (Windows)."""
    import ctypes

    class _P(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    p = _P()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _draw_cursor(frame, x, y):
    """Draw a classic arrow cursor (white fill, black outline) at (x, y).

    dxcam / Desktop Duplication captures the framebuffer WITHOUT the hardware
    cursor overlay, so the phone would never see the pointer — we paint it in
    ourselves each frame."""
    import cv2
    import numpy as np
    pts = np.array([[0, 0], [0, 18], [4, 14], [8, 21], [11, 19],
                    [6, 12], [13, 12]], dtype=np.int32) + np.array([x, y])
    cv2.fillPoly(frame, [pts], (255, 255, 255))
    cv2.polylines(frame, [pts], True, (0, 0, 0), 1, cv2.LINE_AA)


def _make_screen_track(res: dict, fps: int):
    """Build a VideoStreamTrack that pulls frames from the shared dxcam.

    ``res`` is a mutable holder ``{'max_px': N}`` so the Phase-6 adaptive ladder
    can shrink/grow the encoded width live (read fresh on every frame)."""
    import av
    from aiortc import VideoStreamTrack
    from aiortc.mediastreams import MediaStreamError
    from core import dx_capture

    class ScreenTrack(VideoStreamTrack):
        def __init__(self):
            super().__init__()
            self._started = False
            self._w = 0
            self._h = 0

        def _ensure(self):
            if self._started:
                return
            cam = dx_capture.get()
            if cam is None:
                raise MediaStreamError("dxcam unavailable")
            cam.start(target_fps=fps, video_mode=True)
            self._started = True

        async def recv(self):
            import cv2
            pts, time_base = await self.next_timestamp()
            self._ensure()
            cam = dx_capture.get()
            frame = cam.get_latest_frame()
            if frame is None:
                # feed a black frame until dxcam produces one
                import numpy as np
                frame = np.zeros((720, 1280, 3), dtype="uint8")
            h, w = frame.shape[:2]
            scale = 1.0
            max_px = int(res.get("max_px", 1280))  # live-adjusted by the ladder
            if w > max_px:
                nh = int(h * max_px / w)
                nh -= nh % 2
                frame = cv2.resize(frame, (max_px, nh),
                                   interpolation=cv2.INTER_AREA)
                scale = max_px / float(w)
            # Paint the mouse cursor in (dxcam doesn't capture the overlay).
            try:
                cx, cy = _cursor_xy()
                frame = frame.copy()   # dxcam buffers are read-only
                _draw_cursor(frame, int(cx * scale), int(cy * scale))
            except Exception:
                pass
            # Convert BGR → I420 (yuv420p) here with OpenCV (SIMD, ~1.3× faster
            # than PyAV's swscale) and hand aiortc a ready yuv420p frame, so the
            # encoder never reformats. 4:2:0 needs even dimensions.
            h2, w2 = frame.shape[:2]
            if h2 % 2 or w2 % 2:
                frame = frame[:h2 - (h2 % 2), :w2 - (w2 % 2)]
            try:
                yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_I420)
                vf = av.VideoFrame.from_ndarray(yuv, format="yuv420p")
            except Exception:
                vf = av.VideoFrame.from_ndarray(frame, format="bgr24")
            vf.pts = pts
            vf.time_base = time_base
            return vf

        def stop(self):
            super().stop()
            try:
                from core import dx_capture
                cam = dx_capture.get()
                if cam is not None and self._started:
                    cam.stop()
            except Exception:
                pass
            self._started = False

    return ScreenTrack()


def _make_audio_track():
    """WASAPI loopback (whatever the laptop is playing) → an aiortc audio
    track, so the phone hears the laptop too (true remote desktop). Returns
    None if system-audio capture isn't available."""
    try:
        import av
        import fractions
        import threading
        import time as _t
        from collections import deque
        import numpy as np
        import soundcard as sc
        from aiortc.mediastreams import MediaStreamTrack
    except Exception as e:
        log.info("[webrtc] audio unavailable: %s", e)
        return None

    class AudioLoopbackTrack(MediaStreamTrack):
        kind = "audio"

        def __init__(self):
            super().__init__()
            self._sr = 48000
            self._n = 960                    # 20 ms @ 48 kHz
            self._pts = 0
            self._q: deque = deque(maxlen=25)
            self._stop = threading.Event()
            self._thr = threading.Thread(target=self._capture,
                                         name="WebRTCAudio", daemon=True)
            self._thr.start()

        def _capture(self):
            try:
                spk = sc.default_speaker()
                mic = sc.get_microphone(spk.name, include_loopback=True)
                with mic.recorder(samplerate=self._sr, channels=2,
                                  blocksize=self._n) as rec:
                    while not self._stop.is_set():
                        data = rec.record(numframes=self._n)  # (n,2) float32
                        s16 = (np.clip(data, -1.0, 1.0) * 32767.0)\
                            .astype(np.int16).reshape(1, -1)
                        self._q.append(s16)
            except Exception as e:
                log.info("[webrtc] audio capture stopped: %s", e)

        async def recv(self):
            import asyncio
            while not self._q and not self._stop.is_set():
                await asyncio.sleep(0.005)
            if self._q:
                arr = self._q.popleft()
            else:
                arr = np.zeros((1, self._n * 2), dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(arr, format="s16",
                                               layout="stereo")
            frame.sample_rate = self._sr
            frame.pts = self._pts
            frame.time_base = fractions.Fraction(1, self._sr)
            self._pts += self._n
            return frame

        def stop(self):
            self._stop.set()
            super().stop()

    try:
        return AudioLoopbackTrack()
    except Exception as e:
        log.info("[webrtc] audio track init failed: %s", e)
        return None


def _summarize_stats(report, prev: dict) -> tuple[dict, dict]:
    """Turn an aiortc getStats() report into a flat {bitrate_kbps, rtt_ms,
    loss} dict. `prev` carries the last byte-count + timestamp so we can derive
    bitrate from the delta; it's mutated and returned for the next call."""
    import time as _t
    now = _t.time()
    out = {"bitrate_kbps": 0, "rtt_ms": 0, "loss": 0.0}
    cur_bytes = None
    for s in report.values():
        t = getattr(s, "type", "")
        if t == "outbound-rtp":
            b = getattr(s, "bytesSent", None)
            if b is not None:
                cur_bytes = b
        elif t == "inbound-rtp":
            b = getattr(s, "bytesReceived", None)
            if b is not None:
                cur_bytes = b
            pl = getattr(s, "packetsLost", None)
            pr = getattr(s, "packetsReceived", None)
            if pl is not None and pr:
                out["loss"] = round(100.0 * pl / max(1, pl + pr), 2)
        elif t == "remote-inbound-rtp":
            rtt = getattr(s, "roundTripTime", None)
            if rtt is not None:
                out["rtt_ms"] = round(rtt * 1000)
    dt = now - prev.get("t", now)
    if cur_bytes is not None and prev.get("bytes") is not None and dt > 0:
        out["bitrate_kbps"] = round((cur_bytes - prev["bytes"]) * 8 / dt / 1000)
    if cur_bytes is not None:
        prev["bytes"] = cur_bytes
    prev["t"] = now
    return out, prev


class WebRTCStreamer:
    """One laptop→phone WebRTC session. Lives on its own asyncio loop thread
    so it never blocks the GUI / bridge threads."""

    def __init__(self, send_signal: Callable[[str, dict], object],
                 max_px: int = 1280, fps: int = 60):
        # send_signal(kind, payload) → relay to phone ('webrtc_offer' | 'webrtc_ice')
        self._send_signal = send_signal
        self._max_px = max_px
        self._fps = fps
        # Phase 6: adaptive resolution ladder. `_res` is shared (by reference)
        # with the ScreenTrack so a step change takes effect on the next frame.
        # The ladder is capped at the configured width — on this CPU-bound
        # colour-convert path there's nothing to gain above ~1280.
        _full = [1280, 960, 720, 540]
        self._ladder = [p for p in _full if p <= max_px] or [max_px]
        self._lvl = 0
        self._res = {"max_px": self._ladder[0]}
        self._bad = 0
        self._good = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._pc = None
        self._track = None
        self._audio = None
        self._running = False
        self._want = False        # True while a session should stay up
        self._retries = 0
        self._connected = False
        self._stats: dict = {}    # Phase 0: latest {bitrate_kbps, rtt_ms, loss}

    def get_stats(self) -> dict:
        return dict(self._stats)

    async def _stats_loop(self) -> None:
        prev: dict = {}
        while self._want and self._pc is not None:
            await asyncio.sleep(2)
            try:
                report = await self._pc.getStats()
                s, prev = _summarize_stats(report, prev)
                self._stats = s
                self._adapt(s)
                log.info("[webrtc-stats] tx br=%dkbps rtt=%dms loss=%.1f%% "
                         "res=%dpx", s["bitrate_kbps"], s["rtt_ms"], s["loss"],
                         self._res["max_px"])
            except Exception:
                pass

    def _adapt(self, s: dict) -> None:
        """Phase 6: step the encode width down under RTT/loss stress, back up
        after a sustained clean spell. 3 bad reads (~6 s) → down; 7 clean reads
        (~14 s) → up one rung. Bitrate self-adjusts via aiortc's REMB."""
        rtt = s.get("rtt_ms", 0)
        loss = s.get("loss", 0.0)
        stressed = (rtt and rtt > 150) or (loss and loss > 5.0)
        if stressed:
            self._bad += 1
            self._good = 0
            if self._bad >= 3 and self._lvl < len(self._ladder) - 1:
                self._lvl += 1
                self._res["max_px"] = self._ladder[self._lvl]
                self._bad = 0
                log.info("[webrtc] link stressed (rtt=%dms loss=%.1f%%) → "
                         "%dpx", rtt, loss, self._ladder[self._lvl])
        else:
            self._good += 1
            self._bad = 0
            if self._good >= 7 and self._lvl > 0:
                self._lvl -= 1
                self._res["max_px"] = self._ladder[self._lvl]
                self._good = 0
                log.info("[webrtc] link clean → %dpx", self._ladder[self._lvl])

    # ── lifecycle (called from bridge/GUI threads) ───────────────────
    def start(self) -> bool:
        if self._running:
            return True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="WebRTCLoop", daemon=True)
        self._thread.start()
        self._running = True
        self._want = True
        self._retries = 0
        fut = asyncio.run_coroutine_threadsafe(self._start(), self._loop)
        try:
            return bool(fut.result(timeout=15))
        except Exception as e:
            log.warning("[webrtc] start failed: %s", e)
            self.stop()
            return False

    def stop(self) -> None:
        self._want = False        # intentional stop — don't auto-reconnect
        if self._loop is not None and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._stop(), self._loop)\
                    .result(timeout=5)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._running = False
        self._pc = None
        self._track = None

    def is_running(self) -> bool:
        return self._running and self._pc is not None

    def is_connected(self) -> bool:
        return self._connected

    def on_answer(self, sdp: str) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._on_answer(sdp), self._loop)

    def on_ice(self, cand: dict) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._on_ice(cand), self._loop)

    # ── coroutines (run on the WebRTC loop) ──────────────────────────
    async def _start(self) -> bool:
        from aiortc import (RTCPeerConnection, RTCConfiguration,
                            RTCIceServer)
        ice = load_ice_servers()
        cfg = RTCConfiguration(iceServers=[
            RTCIceServer(urls=s["urls"], username=s.get("username"),
                         credential=s.get("credential")) for s in ice])
        pc = RTCPeerConnection(cfg)
        self._pc = pc
        self._ice_for_phone = ice

        @pc.on("connectionstatechange")
        async def _state():
            st = pc.connectionState
            log.info("[webrtc] connection state: %s", st)
            self._connected = (st == "connected")
            if st == "connected":
                self._retries = 0
            elif st in ("failed", "disconnected") and self._want:
                # Link dropped unexpectedly — re-negotiate so the phone
                # reconnects without the user re-issuing the command.
                asyncio.ensure_future(self._reconnect())

        # Two phone → laptop input channels (Phase 4):
        #  • "control" — reliable + ordered: clicks, keys, scroll, hotkeys.
        #  • "mouse"   — unordered + lossy (maxRetransmits=0): cursor MOVES only,
        #    so a dropped move is skipped instead of stalling the queue behind
        #    it (a lost reliable packet would TCP-style block every later move).
        dc = pc.createDataChannel("control")

        @dc.on("message")
        def _on_ctl(msg):
            self._apply_control(msg)

        mouse_dc = pc.createDataChannel(
            "mouse", ordered=False, maxRetransmits=0)

        @mouse_dc.on("message")
        def _on_mouse(msg):
            self._apply_control(msg)

        self._track = _make_screen_track(self._res, self._fps)
        pc.addTrack(self._track)
        # Laptop audio (loopback) → phone. Best-effort; video works regardless.
        self._audio = _make_audio_track()
        if self._audio is not None:
            try:
                pc.addTrack(self._audio)
                log.info("[webrtc] audio track added")
            except Exception as e:
                log.info("[webrtc] audio addTrack failed: %s", e)
                self._audio = None

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        # Non-trickle: localDescription now carries the gathered candidates.
        self._send_signal("webrtc_offer",
                          {"sdp": pc.localDescription.sdp,
                           "type": pc.localDescription.type,
                           "ice": self._ice_for_phone})
        log.info("[webrtc] offer sent (%d chars)",
                 len(pc.localDescription.sdp))
        asyncio.ensure_future(self._stats_loop())
        return True

    async def _on_answer(self, sdp: str) -> None:
        from aiortc import RTCSessionDescription
        if self._pc is None:
            return
        try:
            await self._pc.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type="answer"))
            log.info("[webrtc] answer applied — connecting")
        except Exception as e:
            log.warning("[webrtc] answer failed: %s", e)

    async def _on_ice(self, cand: dict) -> None:
        from aiortc import RTCIceCandidate
        from aiortc.sdp import candidate_from_sdp
        if self._pc is None:
            return
        try:
            c = candidate_from_sdp(cand["candidate"].split(":", 1)[1]
                                   if cand.get("candidate", "").startswith("candidate:")
                                   else cand.get("candidate", ""))
            c.sdpMid = cand.get("sdpMid")
            c.sdpMLineIndex = cand.get("sdpMLineIndex")
            await self._pc.addIceCandidate(c)
        except Exception as e:
            log.debug("[webrtc] ice add failed: %s", e)

    async def _reconnect(self) -> None:
        if not self._want:
            return
        self._retries += 1
        if self._retries > 6:
            log.info("[webrtc] gave up reconnecting after %d tries",
                     self._retries)
            self._want = False
            return
        await asyncio.sleep(min(2 * self._retries, 8))
        if not self._want:
            return
        log.info("[webrtc] auto-reconnect attempt %d", self._retries)
        await self._stop()
        await self._start()

    async def _stop(self) -> None:
        for tr in (self._track, self._audio):
            try:
                if tr is not None:
                    tr.stop()
            except Exception:
                pass
        self._track = None
        self._audio = None
        try:
            if self._pc is not None:
                await self._pc.close()
        except Exception:
            pass
        self._pc = None

    # ── remote mouse (datachannel) ───────────────────────────────────
    def _apply_control(self, msg) -> None:
        try:
            d = json.loads(msg) if isinstance(msg, str) else json.loads(
                msg.decode("utf-8"))
        except Exception:
            return
        try:
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0
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
        except Exception:
            pass


class WebRTCReceiver:
    """Phone → laptop screen over WebRTC (Phase 5b). The PHONE is the offerer
    (it has a getDisplayMedia screen track); the laptop answers and consumes
    the decoded frames, handing each to ``on_frame(jpeg_bytes)`` so the GUI's
    existing phone-live window can show them — buttery, not the old JPEG poll."""

    def __init__(self, send_signal: Callable[[str, dict], object],
                 on_frame: Callable[[bytes], object], quality: int = 60,
                 on_frame_np: Optional[Callable[[object], object]] = None):
        self._send_signal = send_signal
        self._on_frame = on_frame
        # Phase 2: if the GUI registers a numpy sink, hand it decoded BGR frames
        # directly (no JPEG encode→decode round-trip). Falls back to the JPEG
        # callback (used by the relay/LAN fallback path) when it's not set.
        self._on_frame_np = on_frame_np
        self._quality = quality
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._pc = None
        self._running = False
        self._want = False
        self._stats: dict = {}    # Phase 0: latest {bitrate_kbps, rtt_ms, loss}

    def get_stats(self) -> dict:
        return dict(self._stats)

    async def _stats_loop(self) -> None:
        prev: dict = {}
        while self._want and self._pc is not None:
            await asyncio.sleep(2)
            try:
                report = await self._pc.getStats()
                s, prev = _summarize_stats(report, prev)
                self._stats = s
                log.info("[webrtc-rx-stats] rx br=%dkbps rtt=%dms loss=%.1f%%",
                         s["bitrate_kbps"], s["rtt_ms"], s["loss"])
            except Exception:
                pass

    def start(self) -> None:
        if self._running:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="WebRTCRxLoop", daemon=True)
        self._thread.start()
        self._running = True
        self._want = True

    def stop(self) -> None:
        self._want = False
        if self._loop is not None and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._stop(), self._loop)\
                    .result(timeout=5)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._running = False
        self._pc = None

    def on_offer(self, sdp: str) -> None:
        if not self._running:
            self.start()
        asyncio.run_coroutine_threadsafe(self._on_offer(sdp), self._loop)

    def on_ice(self, cand: dict) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._on_ice(cand), self._loop)

    async def _on_offer(self, sdp: str) -> None:
        from aiortc import (RTCPeerConnection, RTCConfiguration, RTCIceServer,
                            RTCSessionDescription)
        cfg = RTCConfiguration(iceServers=[
            RTCIceServer(urls=s["urls"], username=s.get("username"),
                         credential=s.get("credential"))
            for s in load_ice_servers()])
        pc = RTCPeerConnection(cfg)
        self._pc = pc

        @pc.on("track")
        def _on_track(track):
            if track.kind == "video":
                asyncio.ensure_future(self._consume(track))

        @pc.on("connectionstatechange")
        async def _state():
            log.info("[webrtc-rx] state: %s", pc.connectionState)

        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        self._send_signal("phone_webrtc_answer",
                          {"sdp": pc.localDescription.sdp,
                           "type": pc.localDescription.type})
        log.info("[webrtc-rx] answer sent")
        asyncio.ensure_future(self._stats_loop())

    async def _on_ice(self, cand: dict) -> None:
        from aiortc.sdp import candidate_from_sdp
        if self._pc is None:
            return
        try:
            raw = cand.get("candidate", "")
            if raw.startswith("candidate:"):
                raw = raw.split(":", 1)[1]
            c = candidate_from_sdp(raw)
            c.sdpMid = cand.get("sdpMid")
            c.sdpMLineIndex = cand.get("sdpMLineIndex")
            await self._pc.addIceCandidate(c)
        except Exception:
            pass

    async def _consume(self, track) -> None:
        import cv2
        from aiortc.mediastreams import MediaStreamError
        while self._want:
            try:
                frame = await track.recv()
            except MediaStreamError:
                break
            except Exception:
                break
            try:
                img = frame.to_ndarray(format="bgr24")
                if self._on_frame_np is not None:
                    # Phase 2: hand the raw BGR frame straight to the GUI — no
                    # JPEG encode here, no JPEG decode there.
                    self._on_frame_np(img)
                else:
                    ok, enc = cv2.imencode(
                        ".jpg", img,
                        [int(cv2.IMWRITE_JPEG_QUALITY), self._quality])
                    if ok:
                        self._on_frame(enc.tobytes())
            except Exception:
                pass

    async def _stop(self) -> None:
        try:
            if self._pc is not None:
                await self._pc.close()
        except Exception:
            pass
