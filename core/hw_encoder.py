"""Low-latency H.264 for aiortc — replaces the stock libx264 *medium* encoder.

## Why this exists (measured, not assumed)

aiortc (`aiortc/codecs/h264.py: H264Encoder`) creates libx264 with only
`{tune: zerolatency}` and NO preset → libx264 defaults to the **medium** preset,
which is ~38 ms/frame at 1080p on this laptop. That, plus a too-high resolution,
is the real laptop→phone latency.

The original v2 plan assumed a hardware encoder (QSV/NVENC) would be the big win.
Benchmarked on THIS machine (Intel iGPU, no working NVENC — see numbers below),
that turned out false, so this module reflects what actually measured fastest:

    encoder / path (1080p, realistic screen content)     ms/frame
    ------------------------------------------------      --------
    libx264 medium  (aiortc stock)                          ~38
    libx264 ultrafast + zerolatency + no-Bframes            ~30   ← default
    h264_qsv veryfast (needs bgr→nv12 swscale ~49ms)        ~37   (net loss)
    h264_nvenc                                             FAILS  (no usable GPU)

Two findings drive the design:
  1. **Resolution is the master lever** — the bgr→yuv colour convert is CPU-bound
     and scales with pixels: 1080p ≈ 70 ms, 720p ≈ 24 ms, 540p ≈ 16 ms. So the
     capture side (ScreenTrack) caps at 1280 wide and the colour convert is done
     once with OpenCV (SIMD, ~1.3× faster than PyAV swscale), handing aiortc a
     ready yuv420p frame so it never reformats.
  2. **Hardware only helps when it's real hardware.** NVENC/AMF, when present, ARE
     faster and are tried first; QSV is intentionally NOT in the default chain
     because feeding it needs an nv12 swscale that costs more than it saves in
     aiortc's one-frame-at-a-time synchronous encode pattern. Set
     `AERIS_FORCE_ENCODER=h264_qsv` (etc.) to override for experiments.

We override ONLY codec creation + the per-frame encode; aiortc's NAL
packetisation and its REMB-driven `self.target_bitrate` adaptation stay intact.
See docs/MIRRORING_V2_ARCHITECTURE.md.
"""
from __future__ import annotations

import fractions
import logging
import os

import av
from aiortc.codecs import h264 as _h264

log = logging.getLogger(__name__)

# 60 fps target — aiortc's MAX_FRAME_RATE (30) is patched to match in install().
FPS = 60

_HW_SUFFIXES = ("qsv", "nvenc", "amf")

# Tried in order; first that OPENS wins. Genuine hardware (NVENC/AMF) first —
# they're a real win where present. libx264-ultrafast is the reliable floor and
# is what this Intel laptop actually lands on. QSV is deliberately absent (see
# module docstring); force it with AERIS_FORCE_ENCODER if you want to test.
_CANDIDATES = [
    ("h264_nvenc", {
        "preset": "p1", "tune": "ull", "delay": "0", "bf": "0",
        "g": "600", "forced-idr": "1", "rc": "cbr", "zerolatency": "1",
    }),
    ("h264_amf", {
        "usage": "ultralowlatency", "bf": "0", "g": "600",
    }),
    ("libx264", {
        "preset": "ultrafast", "tune": "zerolatency", "bf": "0", "g": "600",
    }),
]

_QSV_OPTS = {
    "preset": "veryfast", "async_depth": "1", "look_ahead": "0",
    "bf": "0", "g": "600", "forced_idr": "1",
}

_preferred: str | None = None


def _candidate_list():
    forced = os.environ.get("AERIS_FORCE_ENCODER", "").strip()
    if forced:
        opts = _QSV_OPTS if forced.endswith("qsv") else dict(
            next((o for n, o in _CANDIDATES if n == forced), {}))
        return [(forced, opts)] + [c for c in _CANDIDATES if c[0] != forced]
    if _preferred is not None:
        return ([c for c in _CANDIDATES if c[0] == _preferred]
                + [c for c in _CANDIDATES if c[0] != _preferred])
    return _CANDIDATES


def _create_codec(width: int, height: int, bitrate: int):
    """Return (opened CodecContext, name). Probes the chain once, then sticks to
    the winner for later recreations (resolution / bitrate changes)."""
    global _preferred
    last_err: Exception | None = None
    for name, opts in _candidate_list():
        try:
            c = av.CodecContext.create(name, "w")
            c.width = width
            c.height = height
            c.bit_rate = int(bitrate)
            c.pix_fmt = "nv12" if name.endswith(_HW_SUFFIXES) else "yuv420p"
            c.framerate = fractions.Fraction(FPS, 1)
            c.time_base = fractions.Fraction(1, FPS)
            c.options = opts
            c.open()  # fail fast HERE, not on the first frame
            if _preferred != name:
                _preferred = name
                log.info("[hw-enc] using %s (%dx%d @ %d bps)",
                         name, width, height, bitrate)
            return c, name
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("[hw-enc] %s unavailable: %s", name, e)
    raise RuntimeError(f"no H.264 encoder available: {last_err}")


def _encode_frame(self, frame, force_keyframe):
    """Drop-in replacement for aiortc H264Encoder._encode_frame (a generator
    yielding NAL byte-chunks). `self` is an aiortc H264Encoder instance, so
    self.codec / self.target_bitrate / self._split_bitstream are all present.

    ScreenTrack already hands us yuv420p, so with libx264 no reformat happens
    at all; only a hardware encoder wanting nv12 pays a (cheap) yuv→nv12 pass."""
    if self.codec is not None:
        try:
            drift = abs(self.target_bitrate - self.codec.bit_rate) / max(
                1, self.codec.bit_rate)
        except Exception:
            drift = 0.0
        if (frame.width != self.codec.width
                or frame.height != self.codec.height
                or drift > 0.20):
            self.codec = None

    if self.codec is None:
        self.codec, self._hw_codec_name = _create_codec(
            frame.width, frame.height, self.target_bitrate)

    # Convert to the encoder's pixel format FIRST, then stamp the picture type on
    # the reformatted frame — reformat() does not carry pict_type across.
    if frame.format.name != self.codec.pix_fmt:
        frame = frame.reformat(format=self.codec.pix_fmt)
    frame.pict_type = (av.video.frame.PictureType.I if force_keyframe
                       else av.video.frame.PictureType.NONE)

    data = b"".join(bytes(p) for p in self.codec.encode(frame))
    if data:
        yield from self._split_bitstream(data)


def install() -> str:
    """Monkeypatch aiortc to low-latency-encode + run at 60 fps. Call ONCE at
    import time, before any RTCPeerConnection is created. Returns the encoder
    name chosen, or raises (caller then keeps aiortc's stock encoder)."""
    c, name = _create_codec(1280, 720, 4_000_000)
    try:
        c.close()
    except Exception:
        pass
    _h264.H264Encoder._encode_frame = _encode_frame
    _h264.MAX_FRAME_RATE = FPS
    log.info("[hw-enc] installed (encoder=%s, %d fps)", name, FPS)
    return name
