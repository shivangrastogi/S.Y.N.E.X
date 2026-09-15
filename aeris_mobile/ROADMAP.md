# A.E.R.I.S Mobile — plan to beat Google Assistant

Everything here is free and permissively licensed. No paid SDKs, no paid voices,
no paid models, no cloud subscription. Licences are named so nothing sneaks in.

---

## 1. The honest framing

You will not beat Google Assistant at open-domain world knowledge, at ASR
robustness across accents and noise, or at cloud-scale reasoning. Google has a
web index and a datacentre. Accept that and stop competing there.

You beat it on six axes where a local assistant is **structurally** better, and
where Google is structurally prevented from competing:

| Axis | Why you win |
| --- | --- |
| **Privacy** | Nothing leaves the device. Not a policy — an architecture. |
| **Offline** | Works on a train, on a plane, in a basement. Assistant largely doesn't. |
| **Deep phone control** | An AccessibilityService can operate *any* app. Assistant only works with apps that integrated App Actions. |
| **Your laptop** | Assistant cannot open a file, run a script, or read your IDE. A.E.R.I.S can. |
| **Hinglish** | Tuned to how *you* code-mix, not to a generic locale. |
| **Latency** | On-device answers land in milliseconds. No round trip, ever. |

The strategy is not "a worse Google Assistant". It's **"the assistant that does
the things Google's cannot"** — and is merely adequate at the rest.

---

## 2. Architecture: the tier ladder

Already built and working. Every question walks down until something answers,
and the UI shows which tier did.

```
  utterance
      │
      ▼
 ┌─────────────────┐  microseconds, offline, private
 │ T0  skills      │  math, units, dates, finance, numbers, text, chance
 └────────┬────────┘
          ▼
 ┌─────────────────┐  ~1s, offline, private          [Phase 5]
 │ T1  on-device   │  Qwen2.5-1.5B via llama.cpp
 │     LLM         │  tool-calls back into T0
 └────────┬────────┘
          ▼
 ┌─────────────────┐  ~300ms on LAN, private         [Phase 4]
 │ T2  laptop      │  full brain, PC control, files
 └────────┬────────┘
          ▼
 ┌─────────────────┐  last resort, leaves the device [Phase 9, optional]
 │ T3  cloud       │  only with explicit consent
 └─────────────────┘
```

**T3 stays optional and off by default.** The moment it is on by default, the
privacy claim is gone and you're just a worse Google Assistant.

---

## 3. The stack — all free, all permissive

| Need | Choice | Licence | Size on device |
| --- | --- | --- | --- |
| Wake word | **sherpa-onnx KWS** (zipformer) | Apache-2.0 | ~4 MB |
| Offline ASR | **sherpa-onnx streaming Zipformer** | Apache-2.0 | ~70 MB int8 |
| Native ASR (better when available) | Android `SpeechRecognizer` | platform | 0 |
| Offline TTS | **Piper** (onnxruntime) | MIT, voices CC-BY/CC0 | ~25 MB/voice |
| Native TTS | Android `TextToSpeech` | platform | 0 |
| On-device LLM | **Qwen2.5-1.5B-Instruct** Q4_K_M via **llama.cpp** | **Apache-2.0** | ~1.0 GB |
| Embeddings / intent | **paraphrase-multilingual-MiniLM-L12-v2** ONNX int8 | Apache-2.0 | ~120 MB |
| Vector memory | **SQLite + sqlite-vec** | Apache-2.0 | ~1 MB |
| Phone control | AccessibilityService, NotificationListener, MediaSession | platform | 0 |
| Laptop transport | WebSocket + AES-256-GCM (already ported) | — | 0 |

**Licence traps to avoid.** Llama and Gemma ship under custom licences with use
restrictions — not free in the sense you asked for. **Qwen2.5 is Apache-2.0** and
is the right default. Picovoice Porcupine's free tier died in June 2026; sherpa-onnx
replaces it with no strings. Whisper is MIT but not streaming — use it for batch
transcription (voice notes), not live dictation.

Total footprint at full build: **~1.3 GB**. Ship the LLM as an in-app download,
not in the APK, or Play Store limits will bite.

---

## 4. Phases

Each phase has an acceptance test. A phase is not done until its test passes on
a real phone.

### Phase 0 — Foundation ✅ done
Tiered router, 9 on-device skills, push-to-talk voice, transcript persistence,
diagnostics, settings, follow-up context. 213 tests passing.

### Phase 1 — Get it on the phone 🔴 blocking everything
Nothing below is real until the APK runs. Currently blocked on Windows
Developer Mode (`start ms-settings:developers`), which Flutter needs for plugin
symlinks.

- Enable Developer Mode, `flutter build apk --debug`, install
- Verify on-device: mic permission, STT round trip, TTS speaks, transcript survives a restart

**Accept when:** you ask it `15% of 2400` out loud on the phone and hear `360`.

### Phase 2 — Always listening
- `sherpa-onnx` KWS in a `foreground_service`, "Aeris" / "Hey Aeris"
- Self-hearing guard: pause the spotter while TTS speaks, resume 500 ms after
  (`aeris_remote` already solved this — copy the logic)
- Battery budget: **< 3% / day idle**. Measure with Battery Historian; if it
  exceeds, drop the spotter to 8 kHz mono and re-measure.

**Accept when:** screen off, pocket, say "Aeris, what time is it", hear the answer.

### Phase 3 — Offline ears and voice
- Bundle sherpa-onnx streaming ASR + Piper TTS
- `VoiceIn`/`VoiceOut` already abstract this — add `SherpaVoiceIn`, `PiperVoiceOut`
  next to the existing `Device*` implementations, pick per-availability
- Hinglish: run native ASR *and* offline ASR, prefer whichever returns higher
  confidence; log both to build a real comparison set

**Accept when:** aeroplane mode, full voice conversation, no network at all.

### Phase 4 — The laptop tier 🔑 the biggest single unlock
This is the open decision that has blocked ten iterations. **Recommendation:**

- New `core/phone_server.py` on the laptop: WebSocket, **bound to LAN only**,
  handshake `AERIS <token>` matching `lan_link.py`'s convention, payloads in the
  existing AES-256-GCM envelope (`crypto.dart` is already byte-compatible)
- Discovery by mDNS so the phone finds the laptop without typing an IP
- Phone side: `LaptopTier implements TierHandler` — the interface already exists,
  it just needs a body

**Security, non-negotiable:** an `/ask` endpoint runs skills, and skills open
apps and drive the PC. That is remote code execution. It must be token-gated,
LAN-bound, and rate-limited. Do not expose it on 0.0.0.0. Do not skip the token
"just for testing".

**Accept when:** phone says "open spotify", laptop opens Spotify, round trip
under 400 ms on LAN, and an unpaired device is refused.

### Phase 5 — The on-device brain
- llama.cpp JNI + Qwen2.5-1.5B-Instruct Q4_K_M, downloaded on first run
- **Tool-calling into the existing skill registry** — the LLM does not do
  arithmetic, it calls the maths skill. This is why T0 exists below it.
- MiniLM ONNX embeddings replace regex scoring for intent selection; keep the
  regexes as a fast path, since they answer in microseconds

**Accept when:** offline, laptop off, "why is the sky blue" gets a sensible
answer in under 4 seconds.

### Phase 6 — Phone control ⭐ the differentiator
This is where you actually pass Google Assistant. Assistant can only drive apps
that adopted App Actions. An AccessibilityService drives **anything**.

- `AccessibilityService`: read the screen tree, tap, scroll, type
- `NotificationListenerService`: read, summarise, act on, dismiss
- `MediaSession`: control any player
- Contacts / Telephony / Alarm / Settings panels

Target tasks that Assistant genuinely cannot do:
- "reply to mummy's last whatsapp saying I'll call in an hour"
- "mute every notification except calls until 6"
- "screenshot this and send it to my laptop"
- "what did I miss in the office group"

**Accept when:** ten real cross-app tasks work end to end, each with a
confirmation step before anything irreversible.

### Phase 7 — Memory and proactivity
- SQLite + sqlite-vec, embeddings from Phase 5
- Remembers facts you tell it; recalls them weeks later
- Morning briefing built from calendar + notifications + laptop state
- Routines: "every weekday at 9, do X"

**Accept when:** you tell it something on Monday and it uses it unprompted on Friday.

### Phase 8 — Make it feel finished
Onboarding that explains each permission in plain words, a permissions dashboard,
battery and latency benchmarks in the diagnostics screen, crash beacon.

### Phase 9 — Cloud, optional, off by default
Only if you want it. Gemini free tier or an OpenRouter free model. **Must be
opt-in, must be visibly labelled in the tier rail** — the UI already shows
provenance, so the user always knows when something left the device.

---

## 5. Where this will lose, and what to do about it

| Weakness | Mitigation |
| --- | --- |
| Open-domain knowledge | Phase 9 cloud tier, opt-in. Accept the gap otherwise. |
| ASR in noise | Dual-path (native + offline), pick by confidence. |
| First-run size (~1.3 GB) | Download models on demand; app works fully without the LLM. |
| Battery from wake word | Hard budget, measured, with a "listen only while charging" option. |
| Accessibility permission is scary | Earn it: work well *before* asking, then explain exactly what it does. |
| Android kills background services | Foreground service + a plain-language "disable battery optimisation" prompt. |

---

## 6. Do these three next

1. **Enable Developer Mode and build the APK.** Ten iterations of work have
   never run on a phone. Everything else is speculation until this happens.
2. **Decide the laptop protocol** (Phase 4 recommends WebSocket + token + AES-GCM).
   This has blocked the single most valuable feature since day one.
3. **Wake word** (Phase 2). It's the difference between an app you open and an
   assistant you talk to — and `aeris_remote` already has working code to copy.

Phases 5 and 6 are where you pass Google Assistant. Phases 1–4 are what make
that possible.
