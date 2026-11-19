# AERIS Mirroring v2 — "Better than Remote Desktop" Architecture

**Status**: Phases 0–7 IMPLEMENTED (2026-07-07) — code + compile/analyze verified.
On-device testing (RMX3741) still pending. See "Implementation results" below.

> ### Implementation results (what actually shipped)
> Phase 1's premise (hardware QSV/NVENC = the big win) was **benchmarked and
> found false on this laptop** and the implementation was corrected to match
> reality. Measured, 1080p, realistic screen content:
>
> | path | ms/frame |
> |---|---|
> | aiortc STOCK libx264 *medium* (the old default) | ~38 |
> | **libx264 ultrafast + zerolatency + no-B, yuv420p fed direct** | **~8** ✅ shipped |
> | h264_qsv (needs bgr→nv12 swscale ~49 ms) | ~37 (net loss) |
> | h264_nvenc | FAILS to open (no usable NVIDIA GPU) |
>
> Root causes found: (1) the CPU **colour-convert dominates** and scales with
> pixels (1080p≈70 ms, 720p≈24 ms), so the doc's "raise to 1920" was *harmful*
> — the shipped default is **1280 wide**; (2) doing the BGR→I420 convert once in
> OpenCV and handing aiortc a ready **yuv420p** frame removes aiortc's redundant
> reformat; (3) `hw_encoder` still prefers real hardware (NVENC/AMF) where
> present but lands on tuned libx264 here. Net: stock ~38 ms → **~8 ms/frame**.
>
> Everything else shipped as planned. Per-phase file changes are in section 5;
> the code is the source of truth where it diverges from the sketches below.

**Status (original)**: Blueprint — approved for implementation.
**Scope**: Bidirectional screen mirroring (laptop→phone AND phone→laptop), lowest
possible glass-to-glass latency, 60 fps, no same-WiFi requirement.
**Implementer notes**: Written for a fresh Claude session. Every phase lists exact
files, steps, and acceptance tests. Do phases IN ORDER — each is independently
shippable and testable. Never break the fallback chain.

---

## 0. Non-negotiable project constraints (read first)

- Python is **anaconda** at `C:\Users\Shivang\anaconda3\python.exe`. NEVER py-3.10 (ABI-broken).
- NEVER `Get-Process python | Stop-Process` (blanket kill). Kill only the exact GUI pid.
- NEVER auto-run training scripts (`core.train_intent`) — the user runs them.
- Voice stack (Google en-IN STT + edge-tts Neerja) is hand-picked — do not touch.
- `torch/lib/libiomp5md.dll` is renamed to `.disabled` on purpose (OpenMP duplicate
  → 0xC0000374 heap corruption). NEVER restore it.
- GUI launch: PowerShell `Start-Process` (Bash background jobs get reaped).
- Phone app: `aeris_remote/` (Flutter). Device: RMX3741, Android 14+ (targetSdk 36).
- Android 14+ requires a running mediaProjection FGS **before** `getDisplayMedia`
  — already implemented (`ScreenCaptureService` + `startScreenService` channel
  method + call in `phone_screen_sender.dart`). Do not regress this.

## 1. Current state (baseline, July 2026)

### Laptop → phone ("laptop screen dikhao")
```
dxcam (Desktop Duplication, BGR) 
  → cursor painted (core/webrtc_stream.py:_draw_cursor)
  → aiortc VideoStreamTrack (ScreenTrack)
  → aiortc H264Encoder  ← **libx264 SOFTWARE encode (THE bottleneck)**
  → WebRTC (UDP, STUN, ICE) 
  → flutter_webrtc → MediaCodec HW decode → RTCVideoView (SurfaceTexture)   ✅ optimal
Mouse/keyboard: one reliable ordered datachannel.
Audio: soundcard WASAPI loopback → aiortc → opus.                          ✅ works
Fallbacks: LAN H.264 (ffmpeg qsv→TCP→MediaCodec), LAN JPEG, relay JPEG.
```

### Phone → laptop ("phone screen dikhao")
```
flutter_webrtc getDisplayMedia → MediaCodec HW encode                       ✅ optimal
  → WebRTC → aiortc WebRTCReceiver (core/webrtc_stream.py)
  → frame.to_ndarray(bgr24) → cv2.imencode JPEG → callback                 ← **wasteful**
  → GUI _PhoneLiveWindow: QPixmap.loadFromData(jpeg) per frame             ← **wasteful**
Fallback: JPEG polling over relay/LAN.
```

### Verified facts (do not re-verify, already tested on this machine)
- `aiortc 1.14.0`, `PyAV 16.1.0`.
- PyAV can open ALL of: `h264_qsv`, `h264_nvenc`, `h264_amf`, `libx264`,
  `hevc_qsv`, `av1_qsv`, `libvpx-vp9` (checked via `av.codec.Codec(name,'w')`).
- aiortc hardcodes `av.CodecContext.create("libx264","w")` inside
  `aiortc/codecs/h264.py: H264Encoder._encode_frame`, options
  `{level:31, tune:zerolatency}`, profile Baseline, `MAX_FRAME_RATE = 30`.
- aiortc's bandwidth estimator drives `encoder.target_bitrate` (REMB) — a patched
  encoder MUST keep honoring `self.target_bitrate`.

## 2. Why remote desktop feels instant (design principles we copy)

1. **UDP, never TCP** for media (no head-of-line blocking) → WebRTC ✅ already.
2. **Hardware encode/decode** (NVENC/QSV/AMF/MediaCodec) → the ONE big gap on laptop.
3. **Inter-frame (delta) coding** — only changed pixels ride the wire → H.264 P-frames ✅.
4. **P2P via ICE/STUN, TURN only as last resort** ✅ already; TURN self-host = Phase 5.
5. **Adaptive bitrate** — degrade quality, never freeze → aiortc REMB ✅ basic; tune in Phase 6.
6. **Low-latency encoder tuning** — zero B-frames, no lookahead, slice/intra-refresh.
7. **Input on a separate lossy low-latency channel** — mouse moves may drop, never queue.
8. **LAN autodetect for free**: ICE host candidates connect directly on the same LAN
   at LAN speed — same code path, zero special-casing. (This eventually obsoletes
   the custom LAN TCP paths — keep them as fallback until Phase 7.)

**Latency budget target** (glass-to-glass):
| Segment | Target |
|---|---|
| Capture (dxcam 60Hz) | ~8 ms |
| Convert+encode (QSV) | ≤ 8 ms |
| Network (LAN / same-city P2P) | 2–20 ms |
| Jitter buffer + decode (MediaCodec) | ~10–20 ms |
| Render (SurfaceTexture vsync) | ~8 ms |
| **Total** | **~40–70 ms LAN, ~80–130 ms internet** |

---

## 3. Phase plan (each independently shippable)

### Phase 0 — Metrics baseline + stats overlay  (do this FIRST)
You can't tune what you can't see.

**Laptop** (`core/webrtc_stream.py`):
- In both `WebRTCStreamer` and `WebRTCReceiver`, add a stats task:
  every 2 s call `pc.getStats()`; extract: `outbound-rtp` bitrate/framesEncoded,
  `remote-inbound-rtp` roundTripTime + packetsLost (sender side); `inbound-rtp`
  framesDecoded/bitrate (receiver side). Log one line:
  `[webrtc-stats] fps=57 br=6.2Mbps rtt=18ms loss=0.2%`.
- Expose latest stats dict via `get_stats()` for the GUI/skills.

**Phone** (`aeris_remote/lib/laptop/webrtc_client.dart` + `chat_screen.dart`):
- `Timer.periodic(2s)` → `_pc.getStats()`; keep `framesPerSecond`,
  `bytesReceived` delta, `currentRoundTripTime` (from candidate-pair).
- Render into the existing live-overlay transport badge:
  `WEBRTC · 58fps · 6.1Mb · 21ms`.

**Accept**: badge shows live numbers during a mirror session; laptop log prints
stats lines. Record the baseline numbers in `docs/MIRRORING_BASELINE.md`.

---

### Phase 1 — Hardware encode on laptop (THE big win)

**New file `core/hw_encoder.py`** — a drop-in replacement for aiortc's H264
encoder that tries QSV → NVENC → AMF → libx264 and keeps aiortc's packetizer:

```python
"""Hardware H.264 for aiortc — replaces the hardcoded libx264 encoder.

aiortc's H264Encoder._encode_frame creates libx264 with zerolatency. We subclass
and override ONLY codec creation + per-frame encode, keeping aiortc's NAL
splitting/packetization + target_bitrate plumbing intact.
"""
import fractions, logging
import av
from aiortc.codecs import h264 as _h264

log = logging.getLogger(__name__)
FPS = 60   # also patch aiortc MAX_FRAME_RATE (see below)

_CANDIDATES = [
    # (codec_name, options)
    ("h264_qsv",  {"preset": "veryfast", "async_depth": "1",
                    "look_ahead": "0", "bf": "0", "g": "600",
                    "forced_idr": "1"}),
    ("h264_nvenc", {"preset": "p1", "tune": "ull", "delay": "0",
                    "bf": "0", "g": "600", "forced-idr": "1",
                    "rc": "cbr", "zerolatency": "1"}),
    ("h264_amf",  {"usage": "ultralowlatency", "bf": "0", "g": "600"}),
    ("libx264",   {"preset": "ultrafast", "tune": "zerolatency",
                    "bf": "0", "g": "600"}),
]

def _create_codec(width, height, bitrate):
    for name, opts in _CANDIDATES:
        try:
            c = av.CodecContext.create(name, "w")
            c.width, c.height = width, height
            c.bit_rate = bitrate
            c.pix_fmt = "nv12" if name.endswith(("qsv", "nvenc", "amf")) else "yuv420p"
            c.framerate = fractions.Fraction(FPS, 1)
            c.time_base = fractions.Fraction(1, FPS)
            c.options = opts
            c.open()                      # fail fast here, not on frame 1
            log.info("[hw-enc] using %s", name)
            return c, name
        except Exception as e:
            log.warning("[hw-enc] %s unavailable: %s", name, e)
    raise RuntimeError("no H.264 encoder available")

class HardwareH264Encoder(_h264.H264Encoder):
    def _encode_frame(self, frame, force_keyframe):
        # recreate codec on size change or bitrate drift >20% (REMB adaptation)
        if self.codec and (
            frame.width != self.codec.width
            or frame.height != self.codec.height
            or abs(self.target_bitrate - self.codec.bit_rate)
               / self.codec.bit_rate > 0.20
        ):
            self.codec = None
        if force_keyframe:
            frame.pict_type = av.video.frame.PictureType.I
        else:
            frame.pict_type = av.video.frame.PictureType.NONE
        if self.codec is None:
            self.codec, self._codec_name = _create_codec(
                frame.width, frame.height, self.target_bitrate)
        frame = frame.reformat(format=self.codec.pix_fmt)
        data = b"".join(bytes(p) for p in self.codec.encode(frame))
        if data:
            yield from self._split_bitstream(data)

def install():
    """Monkeypatch aiortc to use hardware encode + 60fps. Call once at import
    time in core/webrtc_stream.py, BEFORE any RTCPeerConnection is created."""
    _h264.H264Encoder._encode_frame = HardwareH264Encoder._encode_frame
    _h264.MAX_FRAME_RATE = FPS
```

**Wire it** in `core/webrtc_stream.py`, top of module (after aiortc import):
```python
try:
    from core import hw_encoder
    hw_encoder.install()
except Exception as _e:
    log.warning("[webrtc] hw encoder unavailable, using default: %s", _e)
```

**Also raise the capture rate**: in `_make_screen_track`, default
`fps=60`, `max_px=1920` when `settings mirror_fps/mirror_max_width` absent.
dxcam `video_mode=True` with `target_fps=60`.

**Gotchas the implementer must handle**:
- QSV wants **nv12**, even dimensions. Crop/pad width,height to even numbers
  when downscaling in ScreenTrack.
- `frame.reformat(format="nv12")` runs in libswscale (SIMD, ~1-2 ms at 1080p) — fine.
- Keep `profile` unset for qsv/nvenc (their option parsing differs); H.264
  `constrained-baseline`/`main` are both fine for MediaCodec decode. If the phone
  shows black video, force `"profile": "main"` on the qsv options and retest.
- If bitrate recreate causes visible hiccups every REMB update, widen the drift
  threshold to 30% or implement `codec.bit_rate` live update (qsv supports it via
  `AVCodecContext.bit_rate` reconfig — PyAV allows assignment between frames).
- aiortc calls `encode()` from its media thread — no asyncio work inside.

**Accept**:
- Log shows `[hw-enc] using h264_qsv` (or nvenc).
- Laptop CPU during 1080p mirror drops vs baseline (task manager: python process).
- Phase-0 badge shows ≥50 fps at 1080p on LAN.
- Regression: WebRTC session still connects, mouse/keyboard still work,
  fallback path still works when `hw_encoder.install()` is made to raise (test once).

---

### Phase 2 — Laptop viewer direct render (phone→laptop path)

Kill the double JPEG hop. Currently: decoded frame → ndarray → **JPEG encode** →
Qt signal → **JPEG decode** → QPixmap. At 1080p60 that wastes ~2 CPU cores and
adds ~15 ms.

**`core/webrtc_stream.py` `WebRTCReceiver._consume`**: stop JPEG-encoding.
Emit raw frames instead:
```python
img = frame.to_ndarray(format="bgr24")      # HxWx3, contiguous
self._on_frame_np(img)                       # new callback, ndarray not bytes
```
Keep the old bytes-callback as an optional shim (`quality` arg) so the JPEG
fallback path (relay/LAN) still uses the existing signal.

**`core/cloud_bridge.py` `start_phone_webrtc`**: pass a numpy callback
`_on_phone_screen_np` through to the GUI (new optional callback registration
`on_phone_screen_np(fn)`), falling back to JPEG callback when GUI hasn't
registered the new one.

**`ui/jarvis_v31/main_window.py` `_PhoneLiveWindow`**:
- New signal `frame_np = pyqtSignal(object)`.
- Slot: wrap ndarray in QImage **without copy-per-pixel**:
```python
h, w, _ = img.shape
qimg = QImage(img.data, w, h, 3*w, QImage.Format_BGR888)
self._label.setPixmap(QPixmap.fromImage(qimg.copy()))  # one memcpy, no codec
```
- Coalesce: if a frame arrives while one is still being painted, drop the old
  one (keep only latest — `self._pending = img` + singleShot(0) repaint).

**Accept**: phone mirror window CPU use visibly lower; motion (scrolling on
phone) looks smooth ≥30 fps; JPEG fallback path still renders when WebRTC is
killed mid-session.

---

### Phase 3 — Phone capture quality (phone→laptop 60fps)

**`aeris_remote/lib/laptop/phone_screen_sender.dart`**:
```dart
_stream = await navigator.mediaDevices.getDisplayMedia({
  'video': {
    'frameRate': {'ideal': 60, 'max': 60},
    'width':  {'ideal': 1280},   // phone is 1080x2412; 1280-wide portrait ≈ 534x1280
    'height': {'ideal': 1280},
  },
  'audio': false,
});
// Hint the encoder this is screen content (crisper text, smarter rate control):
for (final t in _stream!.getVideoTracks()) {
  try { t.contentHint = 'detail'; } catch (_) {}
}
```
- After `addTrack`, raise the encoder ceiling via sender parameters:
```dart
final sender = (await pc.getSenders())
    .firstWhere((s) => s.track?.kind == 'video');
final p = sender.parameters;
if (p.encodings != null && p.encodings!.isNotEmpty) {
  p.encodings![0].maxBitrate = 8 * 1000 * 1000;   // 8 Mbps ceiling
  p.encodings![0].maxFramerate = 60;
  await sender.setParameters(p);
}
```
(Guard everything in try/catch — flutter_webrtc parameter support varies by version.)

**Laptop answer side** (`WebRTCReceiver._on_offer`): nothing needed — decode is
already whatever the phone sends. But bump aiortc's receive bandwidth: after
`setLocalDescription`, no action needed (REMB is receiver-driven; aiortc
advertises based on estimator — verify in Phase-0 stats that phone-side bitrate
actually climbs above ~2.5 Mbps; if stuck, the fix is `RTCRtpTransceiver`
direction + `b=AS` munging: append `b=AS:8000` under the video m-line of the
answer SDP string before `setLocalDescription`).

**Accept**: Phase-0 badge on laptop shows phone stream ≥40 fps and >4 Mbps while
scrolling; text on the mirrored phone screen is readable.

---

### Phase 4 — Input channel split (mouse feels "wired")

Currently one reliable ordered datachannel carries everything → a lost packet
stalls every queued mouse-move behind it (TCP-like lag on flaky links).

**Laptop `core/webrtc_stream.py` (WebRTCStreamer)**:
- Create a SECOND datachannel at offer time:
  `pc.createDataChannel("mouse", ordered=False, maxRetransmits=0)`
- Route in `_apply_control`: unchanged (both channels call the same handler).
- Keep "control" (existing) reliable channel for: click, down/up, scroll,
  key, type, hotkey, clipboard. ONLY `{'t':'move'}` rides "mouse".

**Phone `aeris_remote/lib/laptop/webrtc_client.dart`**:
- In `onDataChannel`, keep references by `channel.label` (`control` / `mouse`).
- `sendMouse(ev)`: if `ev['t'] == 'move'` and mouse channel open → mouse channel;
  else control channel. If mouse channel not open yet → drop moves (never queue).
- **Coalescing**: accumulate pan deltas and flush on a 8 ms timer
  (`Timer.periodic(Duration(milliseconds: 8))`, sum dx/dy between flushes,
  skip empty). Cheap and caps the message rate at 125/s.

**Accept**: on a throttled connection (enable Windows firewall rule or hotspot
with weak signal), cursor keeps moving fluidly while video may degrade; taps
never get lost (reliable channel).

---

### Phase 5 — TURN self-host + ICE tuning (worst-network insurance)

P2P fails on symmetric NAT / CGNAT (common on Indian mobile data). Without TURN,
those sessions fall back to Firestore JPEG (ugly). With TURN, they stay WebRTC.

**Server** (one-time, user does the account part):
1. Free VM: Oracle Cloud Always-Free (Mumbai region) or a ₹250/mo VPS.
2. `sudo apt install coturn`; `/etc/turnserver.conf`:
   ```
   listening-port=3478
   fingerprint
   lt-cred-mech
   user=aeris:<long-random-password>
   realm=aeris
   total-quota=100
   min-port=49152
   max-port=49999
   ```
   Open UDP 3478 + 49152-49999 in the VM firewall AND the cloud security list.
3. `systemctl enable --now coturn`.

**Laptop**: `data/secrets/turn.json` (already supported by
`core/webrtc_stream.py:load_ice_servers`, and already forwarded to the phone in
both directions' offers/actions):
```json
[{"urls": "turn:<vm-ip>:3478?transport=udp",
  "username": "aeris", "credential": "<password>"}]
```

**Verify**: `python -c` script using aiortc to gather candidates with only the
TURN server configured → must yield `typ relay` candidates. Then a real mirror
session with STUN blocked (temporarily set ice list to TURN-only) must connect.

**Accept**: mirror works on phone mobile-data + laptop home-WiFi with TURN-only
config; stats badge shows the extra RTT but stable fps.

---

### Phase 6 — Adaptive policy polish

- **Resolution ladder (laptop→phone)**: in `ScreenTrack`, once per 2 s read the
  sender stats collected in Phase 0. If `rtt > 150ms` or `loss > 5%` for 3
  consecutive reads → step down the ladder [1920 → 1600 → 1280 → 960] (recreate
  scale only — encoder auto-recreates on size change from Phase 1). Step up one
  rung after 15 s clean. Log every transition.
- **Keyframe hygiene**: aiortc answers PLI with a forced keyframe already —
  verify in logs when toggling airplane mode briefly; if recovery > 2 s, lower
  `g` (GOP) from 600 to 300.
- **Jitter-buffer feel (phone)**: nothing to configure in flutter_webrtc;
  measured latency comes from the stats. Do NOT add app-level buffering.
- **Audio**: keep opus defaults; if audio ever leads video noticeably, set
  `ptime:10` by munging the answer SDP (`a=ptime:10` under audio m-line).

**Accept**: pulling the router cable for 2 s → picture freezes ≤2 s, recovers
without disconnect; walking away from the router degrades resolution before fps.

---

### Phase 7 — Simplify: legacy paths become fallback-only

Once Phases 1-6 are verified on-device:
- `skills/screen_share_skill.py` + `skills/phone_screen_skill.py`: WebRTC is the
  only primary. Remove the "start both, race" logic if any remains; keep exactly
  one fallback trigger: `WebRTCStreamer.is_connected()` false after 13 s (the
  existing `_webrtc_fallback_watch`) → LAN H.264 → relay JPEG.
- Delete dead code paths ONLY if they're unreachable; otherwise leave & mark
  `# fallback-only`.
- Update `aeris_remote/AERIS_COMPANION_GUIDE.md` with the new pipeline + stats badge.
- Run the repo's guard/regression tests + `flutter analyze` + full mirror test
  matrix below.

**Final test matrix** (all on real RMX3741):
| Scenario | Expectation |
|---|---|
| Laptop→phone, same WiFi | ≥50 fps, badge RTT <25 ms, cursor visible, kb+mouse OK |
| Laptop→phone, phone on 4G | connects (TURN if needed), ≥24 fps, no freeze |
| Phone→laptop, same WiFi | ≥40 fps, text readable, direct-render (no JPEG log) |
| Phone→laptop, phone on 4G | connects, degrades gracefully |
| Capture-consent denied on phone | JPEG fallback message, NO crash (FGS fix) |
| Kill WebRTC mid-session (airplane 2 s) | auto-reconnect ≤ backoff, or LAN fallback |
| "screen share band karo" | everything stops both sides, FGS notification gone |
| Double-tap in trackpad mode | OS double-click still works |

---

## 4. Explicit non-goals / rejected options

- **AV1**: `av1_qsv` exists on the laptop, but phone-side HW AV1 decode on
  RMX3741 (Dimensity) is unreliable and flutter_webrtc negotiation for AV1 is
  spotty → H.264 stays. Revisit in 2027.
- **HEVC**: WebRTC HEVC support is Safari-land; not portable. No.
- **Custom UDP protocol (à la Parsec)**: months of work to re-derive what
  WebRTC already gives (FEC/NACK/BWE/DTLS). No.
- **uvloop**: not on Windows. `winloop` exists but aiortc runs its own loop
  thread and the encoder is now HW — event-loop speed is not the bottleneck. Skip.
- **Frame-diff dirty rectangles at app level**: H.264 P-frames already do this
  better in silicon. No.

## 5. File inventory (what gets touched)

| File | Phases |
|---|---|
| `core/hw_encoder.py` (NEW) | 1 |
| `core/webrtc_stream.py` | 0,1,2,4,6 |
| `core/cloud_bridge.py` | 2 |
| `ui/jarvis_v31/main_window.py` | 2 |
| `aeris_remote/lib/laptop/webrtc_client.dart` | 0,4 |
| `aeris_remote/lib/laptop/phone_screen_sender.dart` | 3 |
| `aeris_remote/lib/home/chat_screen.dart` | 0 (badge) |
| `data/secrets/turn.json` | 5 (user creates) |
| `docs/MIRRORING_BASELINE.md` (NEW) | 0 |

## 6. How to verify without the phone connected

- `python -m py_compile` every touched Python file.
- `flutter analyze` after every Dart change.
- HW encoder unit check (no WebRTC needed):
  ```
  python -c "from core import hw_encoder; import av, numpy as np; \
    c,n = hw_encoder._create_codec(1280,720,4_000_000); \
    f = av.VideoFrame.from_ndarray(np.zeros((720,1280,3),np.uint8),format='bgr24').reformat(format=c.pix_fmt); \
    f.pts=0; print(n, len(c.encode(f)))"
  ```
- Everything else needs the device — batch it into one session per phase.
