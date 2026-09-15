# AERIS Companion — Feature Guide

Your phone (AERIS Remote) and laptop (AERIS assistant) talk to each other
end-to-end encrypted, from anywhere. Below is everything you can do and how.

---

## 1. Pairing (one time)

1. On the laptop, say/type **"phone pair karo"** → a QR pops up.
2. In the AERIS Remote app, scan the QR.
3. Done — the QR **auto-dismisses** when the phone connects. The green dot
   in the app turns online.

Re-pairing rotates the key (old phone locked out). Kill switch: **"phone
unpair karo"**.

---

## 2. Screen mirroring — laptop → phone (WebRTC, remote-desktop grade)

Say/type **"laptop screen dikhao"** (or tap the *Laptop screen* chip in the
app). The laptop screen appears on the phone.

- **Transport:** WebRTC (UDP + adaptive bitrate + STUN NAT-traversal) — the
  same tech as AnyDesk/Parsec. Smooth, no freeze, and it **auto-reconnects**
  if the link drops.
- **Header shows the mode:** `🌐 WebRTC` (best), `⚡LAN` / `60fps` (fallback),
  or `(relay)` (laggy, only if nothing better works).
- If WebRTC can't connect in ~13s (rare, strict NAT + no TURN), it
  **auto-falls back** to a relay picture so you still see something.
- **Stop:** tap **Exit** on the overlay, or say **"screen share band karo"**.
- **Audio:** the laptop's sound streams to the phone too (video + audio).

### Quality (tunable)
Edit `data/settings.json` and restart the AERIS GUI:
- `"mirror_max_width": 1920` — sharper (strong LAN)
- `"mirror_fps": 60` — smoother
- lower them (e.g. `960` / `24`) on weak WiFi.

---

## 3. Remote control (phone drives the laptop)

While the laptop screen is showing on the phone:

- **Trackpad:** tap **👆 View mode → ✋ Trackpad ON**. Then:
  - slide finger = move cursor
  - **1 tap = click**, **2 quick taps = double-click** (opens files/apps)
  - long-press = right-click
- **Buttons:** Left / Right click, Scroll ↑ / ↓.
- **Keyboard:** tap the ⌨️ icon (top bar) → type; it lands on the laptop
  live. Special keys: ⌫ Enter Tab Esc arrows **Ctrl+C / Ctrl+V / Win**.

Mouse + keyboard ride the WebRTC data channel (low latency, works anywhere).

---

## 4. Screen mirroring — phone → laptop

Say/type **"phone screen dikhao"** → the phone captures its screen and shows
it in a live window on the laptop. First time, allow the screen-record
permission on the phone. **"phone pe kya notification hai"** OCRs + answers.

---

## 5. File transfer (both directions)

- **Laptop → phone:** say/type **"phone pe file bhejo"** → a file picker
  opens on the laptop → the file streams to the phone and saves there (a chat
  note shows the path).
- **Phone → laptop:** in the app menu (⋮) → **Send a file to laptop** → pick
  a file → it lands in the laptop's **Downloads** (chat note confirms).

Any size (chunked), works from anywhere over the encrypted relay.

---

## 6. Voice — talk to your laptop from the phone

Hold the mic in the app and speak (Hinglish). Your command runs on the
laptop **and the reply is spoken back** on the phone. Typed commands get a
text reply only.

---

## 7. Phone actions (from the laptop)

- **"phone ring karao"** — find-my-phone (rings/vibrates even if screen off).
- **"phone ki battery batao"** — phone battery %.
- **"screenshot phone pe bhejo"** — send the laptop screenshot to the phone.
- **"clipboard phone pe bhejo"** / app menu → clipboard sync both ways.

---

## 8. Works truly anywhere (optional TURN)

Same-WiFi and most home internet already work with free STUN. For the ~10%
of cases behind strict NAT (e.g. mobile data ↔ office WiFi), add a TURN
server: copy `data/secrets/turn.json.example` → `turn.json`, fill in a TURN
host + credentials, restart the GUI. The laptop uses it AND sends it to the
phone automatically — one place, no code changes.

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| Phone shows `(relay)` / laggy | Put both devices on the **same WiFi** (ideally 5 GHz). |
| Nothing connects | Ensure the phone has **internet + WiFi** (the offer is delivered via the relay). Keep the app in the **foreground**. |
| "Only text, no screen" | The overlay opens on first frame; if the phone dropped WiFi, reconnect — it auto-recovers. |
| Mirror won't stop | Exit on the phone, or **"screen share band karo"** — stop now goes over the reliable direct channel. |
| Red `E/GoogleApiManager` in logs | Harmless Realme/GMS noise — not the app. |
| Laptop GUI crash on a command | Fixed (duplicate OpenMP DLL); if it recurs, restart the GUI. |

---

## Screen mirroring v2 (low-latency)

Both directions run over WebRTC (UDP, adaptive, works across networks). The
live-view top bar shows a mono transport badge — `WEBRTC · 58fps · 6.1Mb · 21ms`
(transport · framerate · bitrate · round-trip) so you can see the real link.

- **Laptop → phone** encodes with a low-latency H.264 path (~8 ms/frame) at 1280
  wide / 60 fps, stepping resolution down automatically on a weak link.
- **Phone → laptop** captures at up to 60 fps and renders directly on the laptop
  (no JPEG round-trip).
- Cursor moves ride a separate lossy channel so the pointer stays fluid even when
  video degrades; clicks/keys stay reliable.
- Works anywhere; on strict mobile-data NAT add a TURN server (see
  `data/secrets/turn.json.example`). Full design: `docs/MIRRORING_V2_ARCHITECTURE.md`.

*Built with an all-local Hinglish assistant — no cloud AI, E2E encrypted,
zero-config pairing.*
