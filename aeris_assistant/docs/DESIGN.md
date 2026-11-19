# AERIS: the remade design (v1, 2026-11-16)

The Stitch export (`Downloads/stitch_aeris_holographic_hud_assistant`) was the starting reference. Shivang's verdict was "soo cluttered" and "totally AI looking". This file says what was wrong with it and the rules the Flutter app follows instead. When a screen and this file disagree, this file wins.

## What made Stitch look AI-made

| Symptom in the export | Example | Rule that replaces it |
|---|---|---|
| Invented telemetry | `SEC-ID 0x489F`, `LAT 28.6139° N`, `SYNC 5G.MIL`, `PACKET #4810-SYN`, `BUFFER: 256K`, `CH-04` | **R1: no fake numbers.** Every number on screen is real (time, battery, latency, counts) or it isn't shown |
| Jargon labels | `AERIS_CORE // AUDIO_ANALYSIS_MATRIX`, `STREAM_01: LIVE_TRANSCRIPTION`, `PAYLOAD TEXT`, `TRANSMIT` | **R2: human words.** "Listening", "Send", "Message". No `//`, no snake_case, no hex IDs |
| Everything framed | brackets on every panel, ticks, tabs, crosshairs | **R3: brackets mark focus only.** Just the reactor and whatever needs your decision (approval) get brackets |
| Everything uppercase and wide-tracked | headers, buttons, body | **R4: sentence case.** Sora for anything you read. Uppercase mono only for tiny section labels and real numbers |
| Five things competing per screen | core + callouts + strip + log + chips + panels | **R5: one hero per screen.** Home = the core + one line + the dock. The rest lives on its own tab |
| Static decoration standing in for "sci-fi" | degree labels, radar wedges, leader-line callouts | **R6: sci-fi comes from light and motion.** A reactor that really reacts to your voice, text that resolves, panels that materialise |

## The visual system

- **Colour:** background `#04070B`. Holo cyan `#38D9FF` is the only accent. Dim cyan `#167A94` is for structure. Amber `#FFB454` means only "needs your OK", red `#FF4D5E` only "stop/error", mint `#5EE6B5` only "done/ready".
- **Type:**
  - **Sora** for everything readable.
  - **Oxanium** for the wordmark and the one-word voice state only.
  - **JetBrains Mono** for real numbers and tiny section labels.
- **Surfaces:** flat `#0A1117` with a 1 px cyan hairline at 12% and a small 6 px chamfer on two corners. That's the only "HUD" shape cue, and it's quiet.
- **Background:** radial haze plus a 3%-opacity dot grid, painted once (static).
- **Motion:**
  - The reactor runs on one ticker and is driven by real mic level and TTS word timing.
  - Entry: content fades and lifts 8 px, staggered 40 ms.
  - The state word decodes (scrambles into place) when it changes.
  - No blur on anything that animates.
- **Density:** 20 px side margins, 8 pt grid, at most one row of suggestions on Home.
