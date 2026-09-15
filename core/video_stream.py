"""H.264 live video pipeline — laptop screen → phone at 60 fps (Phase 4d).

Why not JPEG frames?  Each JPEG is a full picture (~50-150 KB), capping the
stream at ~10-20 fps and looking jittery.  Real video (H.264) only encodes
what CHANGED between frames and offloads the work to the GPU encoder — the
same trick YouTube / video calls use — giving a smooth 60 Hz at ~8 Mbit/s.

Pipeline (all laptop-side):

  dxcam (video_mode, 60 fps) ──BGR frames──▶ ffmpeg subprocess
      (h264_qsv on Intel Iris Xe → h264_nvenc / h264_amf / libx264 fallback)
  ffmpeg stdout (raw Annex-B H.264, AUD inserted per access unit)
      ──▶ AU splitter ──▶ bounded queue ──▶ sender → lan_link ('V' frames)

The phone decodes with Android MediaCodec straight onto a Flutter Texture.

Latency control: encoder runs zero-lookahead/no-B-frames; the sender queue
drops to the next IDR (keyframe, 1/s) instead of building a backlog when
WiFi hiccups.  Encoding lives in a SEPARATE PROCESS (ffmpeg), so none of
this touches the fragile in-process torch/OpenMP heap.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Callable, List, Optional

log = logging.getLogger(__name__)

_AUD3 = b"\x00\x00\x01\x09"          # AUD NAL with 3-byte start code

# Encoder preference: hardware first (this laptop: Intel Iris Xe → qsv).
_ENCODERS = [
    ("h264_qsv",   ["-preset", "veryfast", "-async_depth", "1"]),
    ("h264_nvenc", ["-preset", "p1", "-tune", "ll", "-delay", "0"]),
    ("h264_amf",   ["-usage", "lowlatency", "-quality", "speed"]),
    ("libx264",    ["-preset", "ultrafast", "-tune", "zerolatency"]),
]

_ffmpeg_path: Optional[str] = None
_best_encoder: Optional[tuple] = None
_probe_lock = threading.Lock()


def ffmpeg_exe() -> Optional[str]:
    """Locate ffmpeg: PATH → imageio-ffmpeg bundle. Cached."""
    global _ffmpeg_path
    if _ffmpeg_path:
        return _ffmpeg_path
    p = shutil.which("ffmpeg")
    if not p:
        try:
            import imageio_ffmpeg
            p = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            p = None
    _ffmpeg_path = p
    return p


def pick_encoder() -> Optional[tuple]:
    """Probe H.264 encoders once and cache the fastest available."""
    global _best_encoder
    with _probe_lock:
        if _best_encoder is not None:
            return _best_encoder or None
        ff = ffmpeg_exe()
        if not ff:
            log.warning("[video] ffmpeg not found — H.264 stream unavailable")
            _best_encoder = ()
            return None
        for name, args in _ENCODERS:
            try:
                r = subprocess.run(
                    [ff, "-hide_banner", "-loglevel", "error",
                     "-f", "lavfi", "-i", "color=black:s=320x240:r=30:d=0.2",
                     "-c:v", name, "-f", "null", "-"],
                    capture_output=True, timeout=20,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if r.returncode == 0:
                    log.info("[video] H.264 encoder: %s", name)
                    _best_encoder = (name, args)
                    return _best_encoder
            except Exception:
                pass
        log.warning("[video] no usable H.264 encoder")
        _best_encoder = ()
        return None


def _split_aus(buf: bytearray) -> List[bytes]:
    """Split an Annex-B buffer at Access Unit Delimiters (in-place consume).

    Every AU starts with an AUD NAL (we force `h264_metadata=aud=insert`),
    and emulation prevention guarantees 00 00 01 never appears inside a NAL
    payload — so scanning for the AUD start code is exact.
    """
    positions: List[int] = []
    i = 0
    while True:
        j = buf.find(_AUD3, i)
        if j < 0:
            break
        s = j - 1 if j > 0 and buf[j - 1] == 0 else j   # 4-byte start code
        positions.append(s)
        i = j + 4
    if len(positions) < 2:
        return []
    out = [bytes(buf[positions[k]:positions[k + 1]])
           for k in range(len(positions) - 1)]
    del buf[:positions[-1]]
    return out


def _has_keyframe(au: bytes) -> bool:
    """True if the AU contains an IDR (5) or SPS (7) NAL."""
    i = 0
    while True:
        j = au.find(b"\x00\x00\x01", i)
        if j < 0 or j + 3 >= len(au):
            return False
        if (au[j + 3] & 0x1F) in (5, 7):
            return True
        i = j + 3


class VideoStreamer:
    """Capture the screen and push H.264 access units to ``send_au``."""

    def __init__(self, send_au: Callable[[bytes], object],
                 send_info: Callable[[dict], object],
                 fps: int = 60, bitrate: str = "4M",
                 out_width: int = 1280):
        self._send_au = send_au
        self._send_info = send_info
        self.fps = fps
        self.bitrate = bitrate
        # Encode at 720p-class width: on a phone screen it looks identical
        # to 1080p but halves the bits → WiFi sustains 60 fps without the
        # backlog-drop stutter seen at 1080p/8M.
        self.out_width = out_width
        self.info: dict = {}
        self._proc: Optional[subprocess.Popen] = None
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self._q: deque = deque()
        self._q_cv = threading.Condition()
        self._need_idr = False
        self._running = False

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self) -> bool:
        enc = pick_encoder()
        if enc is None:
            return False
        from core import dx_capture
        cam = dx_capture.get()
        if cam is None:
            log.warning("[video] dxcam unavailable — H.264 stream off")
            return False
        try:
            cam.start(target_fps=self.fps, video_mode=True)
            frame = cam.get_latest_frame()
        except Exception as e:
            log.warning("[video] dxcam start failed: %s", e)
            try:
                cam.stop()
            except Exception:
                pass
            return False
        h, w = frame.shape[:2]
        # Downscale to out_width (keep aspect, even dims) — the phone shows
        # this full-screen-fitted anyway, and fewer pixels = fewer bits =
        # no WiFi backlog at 60 fps.
        ow = min(self.out_width, w)
        oh = max(2, round(h * ow / w))
        ow -= ow % 2
        oh -= oh % 2
        self.info = {"w": ow, "h": oh, "fps": self.fps, "codec": "h264"}

        name, args = enc
        ff = ffmpeg_exe()
        cmd = [ff, "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{frame.shape[1]}x{frame.shape[0]}",
               "-r", str(self.fps), "-i", "-",
               "-an", "-c:v", name, *args,
               "-pix_fmt", "yuv420p", "-bf", "0", "-g", str(self.fps),
               "-b:v", self.bitrate, "-maxrate", self.bitrate,
               "-bufsize", "800k",
               "-vf", f"scale={ow}:{oh}",
               "-bsf:v", "h264_metadata=aud=insert", "-f", "h264", "-"]
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            log.warning("[video] ffmpeg spawn failed: %s", e)
            try:
                cam.stop()
            except Exception:
                pass
            return False

        self._stop.clear()
        self._running = True
        self._send_info(self.info)
        for target, nm in ((self._feed_loop, "VideoFeed"),
                           (self._read_loop, "VideoRead"),
                           (self._send_loop, "VideoSend")):
            t = threading.Thread(target=target, name=nm, daemon=True)
            t.start()
            self._threads.append(t)
        log.info("[video] H.264 stream started %sx%s@%s via %s",
                 w, h, self.fps, name)
        return True

    def stop(self) -> None:
        if not self._running and self._proc is None:
            return
        self._stop.set()
        with self._q_cv:
            self._q_cv.notify_all()
        p = self._proc
        if p is not None:
            for closer in (lambda: p.stdin.close(),
                           lambda: p.kill()):
                try:
                    closer()
                except Exception:
                    pass
        for t in self._threads:
            if t is not threading.current_thread():
                t.join(timeout=2.0)
        self._threads = []
        self._proc = None
        try:
            from core import dx_capture
            cam = dx_capture.get()
            if cam is not None:
                cam.stop()
        except Exception:
            pass
        self._running = False
        log.info("[video] H.264 stream stopped")

    def is_running(self) -> bool:
        return self._running and self._proc is not None \
            and self._proc.poll() is None

    def resend_info(self) -> None:
        """Re-announce stream params (a phone just [re]connected)."""
        if self.info:
            try:
                self._send_info(self.info)
            except Exception:
                pass

    # ── worker threads ───────────────────────────────────────────────
    def _feed_loop(self) -> None:
        """dxcam frames → ffmpeg stdin (paces itself at target fps)."""
        from core import dx_capture
        cam = dx_capture.get()
        try:
            while not self._stop.is_set():
                frame = cam.get_latest_frame()
                if frame is None:
                    continue
                self._proc.stdin.write(frame.tobytes())
        except Exception:
            pass  # broken pipe on stop — normal
        finally:
            try:
                self._proc.stdin.close()
            except Exception:
                pass

    def _read_loop(self) -> None:
        """ffmpeg stdout → split at AUDs → bounded queue (drop-to-IDR)."""
        buf = bytearray()
        try:
            while not self._stop.is_set():
                # read1: return whatever is available now (low latency) instead
                # of blocking for a full 64 KB (which added ~100 ms of lag).
                chunk = self._proc.stdout.read1(65536)
                if not chunk:
                    break
                buf += chunk
                for au in _split_aus(buf):
                    with self._q_cv:
                        self._q.append(au)
                        if len(self._q) > 90:      # ~1.5 s backlog → reset
                            self._q.clear()
                            self._need_idr = True
                            log.info("[video] backlog dropped — waiting IDR")
                        self._q_cv.notify()
        except Exception:
            pass

    def _send_loop(self) -> None:
        """Queue → LAN socket. After a drop, resume only at a keyframe."""
        while True:
            with self._q_cv:
                while not self._q and not self._stop.is_set():
                    self._q_cv.wait(0.5)
                if self._stop.is_set() and not self._q:
                    return
                au = self._q.popleft() if self._q else None
            if au is None:
                continue
            if self._need_idr:
                if not _has_keyframe(au):
                    continue
                self._need_idr = False
            try:
                self._send_au(au)
            except Exception:
                pass
