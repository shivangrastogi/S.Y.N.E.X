# AERIS Assistant: build guide for the new mobile app

| | |
|---|---|
| **Status** | v0.1 draft, written 2026-11-16, before any code exists |
| **Folder** | `New version- 3.0/aeris_assistant/`, a new app separate from `aeris_remote/` and `aeris_mobile/` |
| **Platform** | Android first (Flutter UI + Kotlin native core). iOS is out of scope (see §3.3) |
| **Design** | [`STITCH_PROMPTS.md`](STITCH_PROMPTS.md): 40+ screen prompts for Google Stitch → Figma |
| **Owner** | Shivang |

> Working name: **AERIS**. Rename in one place (`lib/app/brand.dart`) if you pick something else.

---

## Table of contents

1. What we are building
2. Why a new app (and what we keep from the old ones)
3. Product principles and hard constraints
4. Core scenarios
5. Scope by release
6. System architecture
7. The wake pipeline (deep dive)
8. Voice in and out
9. The brain
10. Phone actions and the agent
11. Memory and data
12. UI system
13. Design workflow: Stitch → Figma → Flutter
14. Project structure, packages, native modules
15. Permissions, onboarding, keeping alive
16. Privacy and security
17. Testing and the numbers we track
18. Milestones and acceptance criteria
19. Wake-word training guide
20. Risks
21. Open decisions
22. Glossary

---

## 1. What we are building

**One line:** a voice-first personal assistant for Android that wakes on "Hey AERIS", understands Hinglish and English, runs on-device first, and actually does things on the phone. It always asks before anything irreversible.

**What "works amazingly" means here.** Each item below can be measured, and §17 tracks them:

| Quality | Target |
|---|---|
| Wakes when you call it | ≥ 95% of your "Hey AERIS" attempts, in a normal room |
| Doesn't wake by itself | ≤ 1 false wake per 8 hours with TV/talk in the background |
| Feels instant | Wake → listening chime < 300 ms. Simple command → done < 1.5 s after you stop talking |
| Understands you | ≥ 95% correct action on your own real-utterance test set (Hinglish + English) |
| Doesn't die | Wake service alive ≥ 99% of a 24 h day on the RMX3741 |
| Cheap to keep on | ≤ 3% battery per day for always-on wake |
| Trustworthy | 0 messages sent, calls placed, or purchases made without explicit approval |

**Not goals for v1:** beating Google at world knowledge, iOS, running a cloud server, payments automation, multi-user households.

---

## 2. Why a new app (and what we keep)

There are already two Flutter companions in this repo, and both stay as they are:

| App | What it became | Why it isn't this app |
|---|---|---|
| `aeris_remote/` | Laptop remote + bridge + screen mirror that grew a phone assistant | Its core identity is the laptop link. The assistant features were bolted onto an 1800-line chat screen. |
| `aeris_mobile/` | Tiered-assistant experiment (skills → laptop → cloud) | A clean architecture, but it has no wake word, no phone control and no real UI. |

This app is designed **assistant-first**: the voice loop and the UI are the product, and the laptop is an optional plug-in.

### Carry over (proven, don't relearn)

These lessons from `aeris_remote` were paid for on the real phone. Each is cited so it can be checked against the memory notes and roadmap docs:

1. **Wake-word gain must be adaptive.** Never gate the audio gain on a fixed RMS constant, because OEM noise suppression differs hugely between phones. A fixed floor made the old app deaf on the RMX3741. Use an adaptive noise floor (an EMA of quiet frames).
2. **A two-stage wake beats one hot threshold.** In the old app, a sensitive stage 1 plus a speech-plausibility stage 2 killed hiss false-wakes.
3. **Refractory period.** Ignore new wake hits for 3 s after one fires.
4. **Mic ownership contract.** The spotter owns the mic while idle and must hand it to STT explicitly (pause → STT → resume). A failsafe timer must never restart the spotter mid-conversation.
5. **PCM buffers from `record` are odd-offset views.** Use `ByteData.sublistView`, never `Int16List.view`.
6. **Utterance stitching.** Google's recognizer ignores the complete-silence extra, so commands get cut mid-sentence. Stitch consecutive finals together; don't swap the STT engine.
7. **Performance traps.** A `setState` on mic amplitude about 15 times a second rebuilt the whole screen, and that froze the app (an ANR). Use a `ValueNotifier` + `RepaintBoundary`, and never put a `BackdropFilter` inside something that repaints every frame. Debug builds exaggerate this, so test with release builds.
8. **ColorOS kills services.** Onboarding for Auto-launch and battery exemption is mandatory, not optional.
9. **Prefix KV cache is mandatory** for the on-device LLM: about 35 s cold vs 3 s cached on the RMX3741 with Qwen3 1.7B.
10. **Safety guards in code, not just in the prompt:** never tap pay/buy/delete; messaging Send needs approval.

### Reuse as code (copy or port, don't rewrite)

- `aeris_brain/schema/tools.json` + the 5-output contract (tool_call / ask / reply / plan / escalate). The Dart ports in `aeris_remote/lib/brain/` are pinned to Python by golden fixtures.
- `aeris_remote` Kotlin: `AerisAccessibilityService.kt` (dumpUi / clickId / typeId / global actions), `launchByLabel`, the ACTION_ASSIST intent filter.
- `aeris_remote/lib/assistant/phone_skills.dart` intent coverage, and its collision test corpus.
- Laptop crypto envelope (AES-256-GCM, `{"n","ct"}`). **It must stay byte-compatible** with `core/cloud_bridge.py` (see repo CLAUDE.md).

---

## 3. Product principles and hard constraints

### 3.1 Principles

1. **Voice first, screen second.** Every feature must work by voice. The screen confirms, shows and lets you fix things.
2. **On-device first.** Answer at the cheapest tier that can answer. Show the user which tier did.
3. **Ask before acting.** Anything that leaves the phone as you (messages, calls, posts) or can't be undone needs approval. Undo is offered wherever possible.
4. **Sci-fi, but legible.** A full JARVIS-style holographic HUD (reactor core, HUD panels, live telemetry, voice-reactive animation) in one cyan family. Amber, red and mint only for meaning, and every sentence a human reads is in plain Sora. See §12.
5. **Honest transparency.** Every action has an Activity entry: what you said, how it was understood, who answered, and what happened.
6. **Never silently fail.** Every error gets a log entry and a spoken or visible message. No empty `catch`.

### 3.2 The voice stack is fixed

**STT = Google en-IN, TTS = edge-tts `en-IN-NeerjaNeural`.** These are the user's hand-tested Hinglish picks, so don't propose swapping them. Wake-word engines are a separate layer and are free to choose. An English-only mode is **added alongside** Hinglish, never replacing it.

### 3.3 Platform constraints (facts, not choices)

| Constraint | Consequence |
|---|---|
| Third-party apps can't use the phone's low-power DSP hotword path (SoundTrigger needs privileged permissions) | Our wake model runs on the main CPU inside a foreground service. Battery matters, so the model must be tiny (§7). |
| Android 14+ requires FGS type `microphone`, started while the app is visible | The wake service starts from the app or a notification tap. It can't silently start itself from the background. |
| Android 15 forbids starting a `microphone` FGS from `BOOT_COMPLETED` | After a reboot, the user must open AERIS once (or tap a "Tap to resume listening" notification). Design for this; don't fight it. |
| iOS allows no always-on third-party mic | iOS is out of scope. A future iOS app would be Siri Shortcut / Action Button only. |
| Accessibility services are reviewed strictly on Play Store | This is a personal sideloaded build, but keep the a11y use honest and user-initiated. |

---

## 4. Core scenarios

These are the acceptance tests for the whole product. Each must work by voice, end to end:

| # | You say | AERIS does | Tier |
|---|---|---|---|
| 1 | "Hey AERIS … kal subah 6:30 ka alarm laga do" | Sets alarm, says "Ho gaya, 6:30 ka alarm laga diya", card with Undo | Skills |
| 2 | "Ravi ko WhatsApp karo ki main 10 minute late hoon" | Drafts, reads back, **waits for "haan"**, sends | Skills + approval |
| 3 | "Mummy ko call karo" | Resolves contact (asks if ambiguous), calls | Skills |
| 4 | "Torch on" / "volume kam karo" / "brightness full" | Instant | Skills |
| 5 | "Screen pe kya error hai?" | Reads screen via a11y, explains | Brain (device or cloud) |
| 6 | "Gemini se birthday poster banwao aur Ravi ko bhejo" | Multi-step agent, approval before send | Agent |
| 7 | "Work mode chalu karo" | Runs routine (DND, volume, apps) | Routines |
| 8 | "Yaad rakhna meri car ki parking B2 mein hai" … later "car kahan park ki thi?" | Remembers, recalls | Memory |
| 9 | "Aaj ka weather aur umbrella chahiye?" | Weather card + answer | Skills (web) |
| 10 | "Laptop pe VS Code kholo" | Sends to paired laptop | Laptop |
| 11 | "Who won the match yesterday?" | Web-grounded answer with sources | Cloud (opt-in) |
| 12 | "Bas" / "bye" | Ends conversation, back to wake listening | — |

---

## 5. Scope by release

### v0.1 "Hears you" (foundation)
- Flutter shell, design tokens, Home idle, Settings skeleton
- Kotlin wake service: openWakeWord stage 1 with a **pretrained test model** (e.g. "hey jarvis", for development only, see §19 licence note)
- Voice loop: wake → STT → echo → TTS, compact overlay
- Activity log, error log, diagnostics screen

### v0.3 "Does things"
- Custom **"Hey AERIS"** model (you train it in Colab, §19)
- Stage 2 personal verification + enrolment flow (S04/S05)
- Skills: alarms/timers/reminders, calls, SMS/WhatsApp (prefilled + approval), torch/volume/brightness/settings panels, open any app, battery/time/date/math
- Approval sheet, undo, full-screen voice HUD (listening/thinking/speaking)

### v0.6 "Thinks"
- On-device brain (Qwen3 1.7B Q4 via llama.cpp with prefix cache; shadow mode first)
- Optional Gemini cloud tier (user key)
- Screen reading + explain (a11y)
- Memory (facts/notes/people/places) + recall
- Conversation follow-ups (pronouns, "uska", "aur ek")

### v1.0 "Partner"
- Agent: multi-step app driving with approvals
- Routines/Modes + suggested routines
- Laptop link (optional plug-in)
- Widgets, quick-settings tile, lock-screen answers
- Polish: motion, haptics, reduced motion, accessibility, release build hardening

---

## 6. System architecture

```
┌──────────────────────────── Android process ────────────────────────────┐
│                                                                          │
│  ┌──────────── Kotlin native core (always alive, FGS) ───────────────┐  │
│  │                                                                    │  │
│  │  AudioRecord 16 kHz mono ──► RingBuffer (2 s)                      │  │
│  │        │                                                           │  │
│  │        ▼                                                           │  │
│  │  [S0] Adaptive noise floor + energy VAD  (cheap, every 10 ms)      │  │
│  │        │ voiced?                                                   │  │
│  │        ▼                                                           │  │
│  │  [S1] openWakeWord: melspec.onnx → embedding.onnx → hey_aeris.onnx │  │
│  │        │ score ≥ τ1 (80 ms frames)                                 │  │
│  │        ▼                                                           │  │
│  │  [S2] Personal verify: DTW over embeddings vs enrolled samples     │  │
│  │       + speech-plausibility check ──► accept / reject              │  │
│  │        │ accept                                                    │  │
│  │        ▼                                                           │  │
│  │  WakeEvent ──► MethodChannel/EventChannel ──► Flutter              │  │
│  │                                                                    │  │
│  │  AccessibilityService (dumpUi / tap / type / global actions)       │  │
│  │  Assist entry (ACTION_ASSIST / power-button hold)                  │  │
│  │  LlamaRuntime (llama.cpp JNI, prefix KV cache)   [v0.6]            │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                    ▲ ▼ platform channels                 │
│  ┌──────────────────────────── Flutter (Dart) ────────────────────────┐  │
│  │  VoiceSession state machine (§7.6)                                 │  │
│  │     STT (Google en-IN via speech_to_text) ─► Utterance stitcher    │  │
│  │     TTS (edge Neerja; offline fallback Android TTS)                │  │
│  │  Router: T0 Skills → T1 On-device LLM → T2 Laptop → T3 Cloud       │  │
│  │  Executor (tools.json contract) ─► Approval gate ─► Actions        │  │
│  │  Agent loop (a11y-driven, step caps, guards)                       │  │
│  │  Memory (SQLite + FTS5; vectors v1.0)                              │  │
│  │  UI: Home · Voice HUD · Conversation · Activity · Memory ·         │  │
│  │      Routines · Abilities · Devices · Settings                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
          │ optional                                   │ optional
          ▼                                            ▼
   Laptop AERIS (LAN WS / Firebase relay, E2E)   Gemini API (user key)
```

**Why the wake stack is Kotlin, not a Dart isolate.** The old app ran its spotter in a `flutter_foreground_task` Dart isolate. It worked, but it keeps a Flutter engine alive in the background, which costs memory and makes cold restarts after process death fragile. A plain Kotlin FGS with ONNX Runtime is lighter and survives independently of the UI engine. Flutter subscribes to wake events when it's running. When it isn't, the service launches the activity on wake.

---

## 7. The wake pipeline (deep dive)

### 7.1 Engine choice: evidence from the Jaco benchmark

Source: <https://gitlab.com/Jaco-Assistant/Benchmark-KeywordSpotting>. It tests 25 h of speech + noise with inserted keywords and reports the miss rate at a fixed false-alarm rate.

**"alexa", LibriSpeech background, miss rate at false alarms/hour:**

| Engine | 0/h | 0.1/h | 0.25/h | 0.5/h | 1/h | Median latency | Compute (RTF) |
|---|---|---|---|---|---|---|---|
| local-wake | 10.7% | **4.6%** | **3.4%** | **3.4%** | **2.8%** | 0.18 s | n/a |
| openWakeWord | 8.2% | 6.4% | 6.1% | 4.0% | 3.3% | **0.04 s** | **0.001** |
| Porcupine (old free) | 10.9% | 8.5% | 6.1% | 5.8% | 3.3% | 0.13 s | n/a |
| slungt large decoding | **7.3%** | 5.8% | 5.2% | 5.2% | 5.2% | 1.48 s | 0.05 |
| microWakeWord | 61.7% | 46.5% | 42.2% | 38.9% | 34.3% | n/a | n/a |

**Noisy dinner-party background (DiPCo), 0.25/h:** local-wake 6.1%, Porcupine 5.8%, slungt 7.0%, **openWakeWord 13.1%** (it degrades in babble noise).

**Decision:**

- **Stage 1 = openWakeWord.** It's free, by far the cheapest compute (RTF 0.001, which matters most for all-day battery), the fastest, and has competitive accuracy. It's trainable for a custom phrase. Its weakness in babble noise is handled by training augmentation (§19) and by stage 2.
- **Stage 2 = personal verification in the style of local-wake.** It compares the candidate against *your* recorded samples. local-wake has the best accuracy at strict false-alarm rates, and the benchmark notes it does even better on the same speaker, which is exactly our case. We **implement the idea ourselves** on the openWakeWord embeddings stage 1 already computed, so stage 2 adds almost no compute and no new dependency.
- **Rejected:** slungt (1.5 s latency, 50× compute, not suited to always-on), microWakeWord (accuracy), Porcupine (paid since mid-2026).
- **Fallback:** sherpa-onnx keyword spotting was live-verified on this phone in `aeris_remote`. Keep it as a plan B behind the same `WakeEngine` interface if openWakeWord underperforms on-device.

> The benchmark used desktop audio with English keywords. **Our own on-phone numbers (§17) decide the final thresholds**, not this table.

### 7.2 openWakeWord on Android

openWakeWord is three small models chained per 80 ms frame (1280 samples @ 16 kHz):

1. **melspectrogram** (ONNX): raw audio → mel features
2. **embedding model** (ONNX, Google's speech-embedding backbone): mel window → a 96-dimension embedding every 80 ms
3. **wake classifier** (ONNX, ours: `hey_aeris.onnx`): last ~16 embeddings (~1.28 s) → score 0..1

Run all three with **ONNX Runtime for Android** (`com.microsoft.onnxruntime:onnxruntime-android`) in Kotlin with 1 intra-op thread. Port the streaming feature buffers from the Python reference (`openwakeword/utils.py` AudioFeatures) **and pin them with a golden test**: run the same WAV through Python and Kotlin and require the scores to match within 1e-3.

### 7.3 Stage 0: adaptive noise floor (cheap gate)

```
every 10 ms frame:
  rms = sqrt(mean(x²))
  if not voiced: floor = 0.98·floor + 0.02·rms        # EMA of quiet frames
  voiced = rms ≥ max(0.006, floor × 2.5)
  gain   = clamp(target / max(rms, ε), 1, 4)          # cap 4×, only applied when voiced
```

- Stage 1 always runs: openWakeWord is cheap enough, and gating it fully risks missing soft speech. **Stage 0 only controls the gain**, so silence and hiss are never amplified. This was the old app's main false-wake cause.
- Save `floor` into diagnostics so "deaf" vs "too hot" is visible.

### 7.4 Stage 2: personal verification

**Enrolment (onboarding S04):** record 3–5 × "Hey AERIS" from the user. Trim with VAD, then store each as its sequence of 96-dimension embeddings (from the same embedding model) in app-private storage.

**On a stage-1 hit:**

1. Take the last ~1.5 s of embeddings from the ring buffer.
2. For each enrolled sample, compute the **DTW distance** with cosine cost, normalised by path length. Keep the best (minimum) distance `d`.
3. Run the **speech plausibility** check carried over from the old app: voiced-ratio ≥ 0.2 AND peak ≥ median × 2 over the window.
4. Accept if `score1 ≥ τ1` AND plausible AND (`d ≤ τ2` OR voice-match is off).
5. **Refractory:** ignore hits for 3 s after an accept.

Sensitivity presets (starting points, to be tuned by §17 measurements):

| Preset | τ1 (stage-1) | τ2 (DTW) |
|---|---|---|
| Low (fewer false wakes) | 0.65 | 0.30 |
| Balanced | 0.50 | 0.38 |
| High (fewer misses) | 0.35 | 0.45 |

Log every hit as `(time, score1, d, plausible, accepted)` to the diagnostics ring buffer. Without this you're tuning blind.

> **Voice Match is a convenience, not security.** It makes AERIS ignore the TV and other people. It doesn't stop a determined impostor, so personal actions on the lock screen still require unlock (§16).

### 7.5 Mic ownership

Exactly one owner of the microphone at any time:

```
          ┌────────────┐ wake accept  ┌────────────┐ STT ready  ┌───────────┐
  ──────► │  SPOTTER   │ ───────────► │  HANDOFF   │ ─────────► │   STT     │
          │ (Kotlin)   │              │ release mic│            │ (Google)  │
          └────────────┘ ◄─────────── └────────────┘ ◄───────── └───────────┘
                         resume ok      session end / error / timeout
```

- The handoff waits for `AudioRecord.stop()` + `release()` before STT starts. Some phones fail STT with ERROR_AUDIO if two recorders overlap.
- While TTS speaks, the mic is **off** (no self-wake). Barge-in is tap-to-interrupt in v0.3. Voice barge-in with echo cancellation is a v1.x stretch.
- **One watchdog**, cancelled on every state change. It only fires if a state is stuck for longer than its own timeout (STT 15 s, thinking 60 s, speaking 120 s), then forces `IDLE` and resumes the spotter.

### 7.6 Voice session state machine

```
IDLE ──wake/tap/assist──► LISTENING ──final text──► THINKING ──reply──► SPEAKING
  ▲                          │  ▲                       │                  │
  │                    no speech│ re-listen (≤1)        │ needs approval   │ done
  │                          ▼  │                       ▼                  ▼
  │                       NO_MATCH                   APPROVAL ──haan──► ACTING
  │                                                     │ nahi              │
  │                                                     ▼                   ▼
  └──────── "bas"/"bye"/stop/3-min idle ◄──────── FOLLOW_UP_LISTEN ◄────────┘
```

- **Follow-up mode** (on by default) keeps the session open after a reply until "bas"/"bye"/stop or 3 minutes of silence, as in the old app.
- Each state maps 1:1 to an orb state in the UI (§12.4).
- Pure Dart class `VoiceSession` with injected STT/TTS/router fakes, so it's 100% unit-testable without a device.

### 7.7 Battery budget

| Component | Expected | Notes |
|---|---|---|
| AudioRecord 16 kHz | low | unavoidable |
| openWakeWord 3 models @ 12.5 Hz | very low (RTF ~0.001 on desktop) | measure on RMX3741 |
| Stage 2 | ~0 (only on hits) | |
| FGS overhead | low | no wakelock beyond the mic |

The target is ≤ 3%/day, measured with `dumpsys batterystats` over 24 h (§17). **Saver rule:** an optional pause when the screen is off and battery is below 15%. It's surfaced in Settings and never silent.

---

## 8. Voice in and out

### 8.1 STT: Google en-IN (fixed)

- `speech_to_text` plugin → Android `SpeechRecognizer`, locale `en-IN` (Hinglish) or `en-US` (English-US mode).
- `partialResults: true` gives the live transcript in the HUD.
- **Utterance stitcher** (port `aeris_remote/lib/utterance.dart`): if the recognizer finalises after a short pause and the user keeps talking within 1.2 s (configurable "wait for pauses"), concatenate the finals.
- Errors (`error_no_match`, `busy`, `speech_timeout`, `audio`) get **one** retry per turn, then NO_MATCH. Log every error.
- **Privacy note:** audio goes to Google only *after* a wake. Say this plainly in onboarding and in Privacy.

### 8.2 TTS: Neerja (fixed)

- Primary: `en-IN-NeerjaNeural` via the Edge read-aloud websocket (the same service edge-tts uses), implemented in Dart (`lib/voice/tts_edge.dart`) and streaming MP3 chunks to `just_audio`.
  - **Risk:** it's an unofficial endpoint and can change or rate-limit. Mitigations: an LRU cache of short common phrases ("Ho gaya", "Haan, bolo"), and automatic fallback below.
- Fallback when offline or on error: Android `TextToSpeech` with an `en-IN` voice (flutter_tts). The fallback is announced once in diagnostics, not spoken.
- Expose the playback audio (Android `Visualizer` on the player session) plus TTS word-boundary events, so the Reactor Core and transcript animate with the real voice (§12.6).
- Speaking style: short first sentence (the answer), detail only if asked. Hinglish by default. The language mode decides via `Lang.t(hinglish, english)`.

### 8.3 Earcons and haptics

| Event | Sound | Haptic |
|---|---|---|
| Wake accepted | soft two-note rise (≤ 150 ms) | light tick |
| Listening ended | single low note | — |
| Action done | none (spoken) | light tick |
| Needs approval | single amber chime | medium |
| Error | low double note | heavy |

These can be switched off in Settings → Wake word → "Chime on wake".

---

## 9. The brain

### 9.1 The tier ladder

| Tier | What | Latency | Leaves phone? | When |
|---|---|---|---|---|
| **T0 Skills** | Deterministic Dart router (regex + slot parsers + contact resolver) | 5–60 ms | No | Always first |
| **T1 On-device LLM** | Qwen3 1.7B Q4_K_M via llama.cpp, prefix-cached system prompt, grammar-constrained JSON | ~3 s | No | T0 unsure, or chat |
| **T2 Laptop** | Paired AERIS desktop | ~300 ms LAN | To your laptop only, E2E | "laptop/PC …" or laptop-only tools |
| **T3 Cloud** | Gemini (user's own key), optional web grounding | ~1–2 s | Yes | Opt-in. World knowledge, fallback |

Every reply records its tier, and the UI shows it as a tag (ON-DEVICE / LAPTOP / CLOUD).

### 9.2 The contract (reuse `aeris_brain`)

The brain returns one of five shapes, the same as `aeris_brain/brain/contract.py`:

```jsonc
{"type":"tool_call","tool":"set_alarm","args":{"time":"06:30","day":"tomorrow"}}
{"type":"ask","question":"Kaunse Ravi — Ravi Sharma ya Ravi Kumar?"}
{"type":"reply","text":"Nau baj ke chaar minute."}
{"type":"plan","steps":[...]}            // → agent
{"type":"escalate","reason":"needs_web"} // → next tier
```

- **Tools come from `aeris_brain/schema/tools.json`** (37 tools). Sync with `py -3.10 -m scripts.sync_app` from `aeris_brain/`, adapted to copy into `aeris_assistant/assets/brain/`.
- **Grounding check before executing:** every string arg must be a span of the user's utterance or a resolved entity. This stops invented values.
- **Prefix stability:** the system prompt + tool list stay byte-identical across turns so the KV cache hits. Dynamic context (time, memory) goes *after* the tools block.
- **Modes:** Off / Shadow (T1 runs and logs, but T0/T3 act) / On. Ship in Shadow until T1 beats T0 + T3 on your real-utterance set.

### 9.3 Router logic

```
route(utterance):
  if pending approval/slot-fill → resolve it
  if mentions laptop/PC/computer and laptop linked → T2
  r0 = skills.match(utterance)            # returns (tool, args, confidence)
  if r0.confidence ≥ 0.9 → execute
  if T1 enabled: r1 = llm.decide(utterance, history)
       if r1 is tool_call and grounded → execute
       if r1 is reply → speak
       if r1 is escalate and T3 enabled → T3
  elif T3 enabled → T3
  else → "Ye abhi mujhe nahi aata" + log as an unknown (training data)
```

**Unknown and failed utterances are saved locally** (opt-in) to a `misses.jsonl` file. That's the most valuable training data for the next brain version.

---

## 10. Phone actions and the agent

### 10.1 Action catalogue (v0.3)

| Domain | Actions | API |
|---|---|---|
| Alarms/timers | set, cancel, list | `AlarmClock` intents |
| Reminders | create, list, done | own DB + `AlarmManager` exact alarms + notification |
| Calls | call contact/number | `ACTION_CALL` (CALL_PHONE) |
| Messages | SMS prefilled, WhatsApp prefilled → approval → send | intents + a11y send |
| Device | torch, volume, brightness, DND, wifi/bt panels, screenshot | CameraManager, AudioManager, Settings panels, a11y global |
| Apps | open any app (fuzzy label) | PackageManager |
| Media | play/pause/next/prev | `dispatchMediaKeyEvent` |
| Info | time/date/battery/math/units | Dart |
| Screen | read, summarise, tap "X", scroll, back/home | a11y |

### 10.2 The approval gate (code, not prompt)

`ApprovalPolicy.requires(action)` is true for: any message send, any call to a non-favourite, posting anything, deleting anything, changing system security settings, anything in the agent touching a messaging app's Send. Some actions are **never automated** whatever the approval: payment/UPI PIN, purchases, "upgrade", account deletion, passwords/OTP entry. The agent must hand control back to the user for these.

Approval works by voice ("haan bhejo" / "nahi") or tap (S22). There's also an "Always allow for this contact" option, stored per contact and revocable in Settings.

### 10.3 The agent (v1.0)

Port `aeris_remote/lib/phone_agent.dart` and keep its limits:

- `plan()` → steps. `run()` loop: dump a11y tree → numbered elements → brain picks ONE action per step (`open_app/tap/long_press/type/enter/scroll/wait/find_contact/skill/say/done/fail`).
- Caps: 30 steps, 5 minutes. Stop button always visible (S21).
- Every step is logged with a thumbnail of the a11y tree so failures can be debugged.
- **User preference (recorded):** drive the free Gemini/ChatGPT *apps* like a human for image generation and similar. Don't integrate paid image APIs.

---

## 11. Memory and data

### 11.1 Storage

- **SQLite** via `drift` (typed, migrations, testable), with **FTS5** for search.
- Everything is in app-private storage. Nothing syncs unless a laptop is linked and the user enables sync.

### 11.2 Schema (v0.6)

```sql
-- what the user taught or AERIS learned
memories(id, kind TEXT CHECK(kind IN('fact','note','person','place','preference')),
         text, source TEXT, confidence REAL, confirmed INTEGER, created_at, updated_at)
memories_fts USING fts5(text, content='memories')

-- every turn, for Activity + transparency
activity(id, at, said TEXT, understood_json TEXT, tier TEXT, result TEXT,
         status TEXT CHECK(status IN('ok','failed','pending','cancelled')), latency_ms INTEGER)

reminders(id, text, due_at, place_id NULL, done_at NULL)
routines(id, name, trigger_json, actions_json, say_after TEXT, enabled INTEGER)
approvals(contact_key, action, allowed INTEGER)      -- "always allow" grants
wake_events(at, score1 REAL, dtw REAL, plausible INTEGER, accepted INTEGER)  -- rolling 7 days
```

- **Retention:** activity 30 days by default (configurable), wake_events 7 days, misses.jsonl opt-in.
- **No raw audio is stored, ever.** Enrolment stores embeddings, not WAVs. Keep WAVs only if the user explicitly opts into "help improve my wake word". Their only use is your own Colab retraining.

### 11.3 Recall

- v0.6: FTS5 keyword recall plus the LLM picking from the top 5.
- v1.0: add vectors (EmbeddingGemma or similar small embedder) + sqlite-vec hybrid. This follows `docs/AERIS_MOBILE_BRAIN_PLAN.md` §RAG.

---

## 12. UI system: "HOLO HUD"

**Direction (user, 2026-11-16):** a full sci-fi, JARVIS-style app. Techy, animated, with speaking animations, impressive at first glance. To keep it premium rather than garish, the whole UI uses **one cyan colour family**, with amber, red and mint reserved for meaning, and decoration is capped at 3–4 HUD details per screen. Visual spec: [`STITCH_PROMPTS.md`](STITCH_PROMPTS.md).

### 12.1 Tokens (`lib/ui/tokens.dart`)

| Token | Value | Use |
|---|---|---|
| `bg` | `#04070B` | app background |
| `haze` | `#0B2A36` → transparent | radial glow behind the core |
| `grid` | `#38D9FF` @ 4% | hex micro-grid, scan lines |
| `holo` | `#38D9FF` | primary lines, active, glow |
| `holoDim` | `#167A94` | secondary lines, inactive rings |
| `holoHot` | `#CFF6FF` | nucleus, brightest highlights |
| `panelFill` | `#38D9FF` @ 4% | HUD panel fill (+ blur on static backgrounds) |
| `panelBorder` | `#38D9FF` @ 25% | 1 px panel border |
| `glow` | `#38D9FF` @ 35%, blur 6–12 | outer glow |
| `text1 / text2 / text3` | `#DDF4FF / #7FA6B8 / #44616F` | primary / secondary / tertiary |
| `ok` | `#5EE6B5` | success, online |
| `attn` | `#FFB454` | approval, attention |
| `stop` | `#FF4D5E` | stop, error, destructive |
| shape | chamfer 10 px (cut corners), bracket arm 12 px, pill → chamfered | no rounded cards |
| spacing | 4, 8, 12, 16, 20, 24, 32, 48 | 8 pt grid, 20 side margin |
| fonts | **Oxanium** (HUD titles, uppercase), **Sora** (body/conversation), **JetBrains Mono** (telemetry) | all OFL, bundled in `assets/fonts/` |

Rule: **conversation and any sentence a human must read are Sora in sentence case.** Oxanium uppercase is only for short labels and titles. This is what keeps a sci-fi UI usable.

### 12.2 Components (`lib/ui/kit/`)

| Component | Notes |
|---|---|
| `ReactorCore` | The signature. 9 states (§12.4) |
| `HudBackground` | Shader: hex grid + haze + scan line + grain (§12.5) |
| `HudPanel` | `ClipPath` chamfer + `CornerBrackets` + optional label tab + optional alert variant (amber/red) |
| `CornerBrackets` | Animated: draws in on mount, extends on focus |
| `HudButton` | Primary (filled glow) / outline / danger / hexagon icon button |
| `TranscriptLine` | `▸ YOU` / `◂ AERIS` tags, word-by-word reveal synced to TTS |
| `Callout` | Leader line + dot + mono label, animates out from the core |
| `DecodeText` | Scramble→resolve text effect for headers |
| `CountUp` | Mono number count-up |
| `TerminalLog` | Typing lines + block cursor |
| `SegmentedBar`, `ArcGauge`, `SpectrumRing`, `Oscilloscope`, `MirroredWaveform` | Telemetry visuals |
| `ApprovalPanel` | Amber "AUTHORISATION REQUIRED" panel with TRANSMIT/ABORT, voice "haan/nahi" |
| `StatusStrip`, `CommandDock`, `HudNavBar`, `SettingRow`, `SegmentedSwitch`, `UnsavedChangesBar`, `EmptyState`, `Banner` | Standard pieces in HUD styling |

**Settings behaviour (user preference):** toggles and segmented choices apply instantly and show a "Saved" snackbar. Text forms get an explicit Save button, enabled only when something changed, plus an unsaved-changes bar and a "Discard changes?" prompt on leaving. Destructive actions get a confirm dialog, and deletes offer Undo. The sci-fi skin doesn't change these behaviours.

### 12.3 Screen map and routes

| ID | Route | Screen |
|---|---|---|
| S00 | `/boot` | Boot sequence (cinematic, first launch; 600 ms short version afterwards) |
| S01–S06 | `/onboarding/{welcome,language,permissions,enrol,test,ready}` | Onboarding |
| S10/S11/S71/S72 | `/` | Command Center (idle / wake offline / offline / mic blocked) |
| X04 | overlay | Compact HUD over any app |
| X01–X03, S16 | `/voice` | Full-screen voice: listening / processing / speaking / no signal |
| X05, S56 | `/status` | System status + diagnostics |
| S20 | `/conversation/:id` | Conversation thread |
| S21–S23 | `/agent/:taskId` | Agent run / complete |
| S22 | sheet | Approval |
| S30/S31 | `/log`, `/log/:id` | Activity log + detail |
| S32/S33 | `/memory`, `/memory/:id` | Memory + edit |
| S34/S35 | `/protocols`, `/protocols/:id` | Routines ("protocols") + editor |
| S40/S41 | `/abilities`, `/abilities/:id` | Abilities |
| S42 | `/reminders` | Reminders |
| S43 | `/devices` | Linked devices |
| S50–S55 | `/settings/...` | Settings hub, wake, voice, brain, permissions, privacy |
| S60–S62 | system | Notification/QS tile, widgets, lock screen |

Navigation: `go_router`, with a bottom nav of CORE / LOG / MEMORY / PROTOCOLS. Settings opens from the top-right hexagon. The voice HUD is a root-level overlay so it can sit over any route. Shared-element transition: the Reactor Core flies into the dock mic button when you leave Home, and back.

### 12.4 The Reactor Core (`lib/ui/reactor/`)

A port and upgrade of `aeris_remote/lib/reactor_painter.dart`, which was already live-tested, as a set of layered painters driven by **one** `Ticker`:

| Layer (back → front) | Painter | Drives it |
|---|---|---|
| Haze + grid | fragment shader (`hud_bg.frag`) | time, core brightness |
| Radar sweep | `SweepGradient` wedge | time |
| Tick ring + degree labels | `CustomPainter` (labels cached as `Paragraph`s) | rotation |
| Arc A / Arc B | `drawArc`, counter-rotating | time × state speed |
| Segmented ring / spectrum ring | 36 segments ↔ 72 bars (morph) | state + **audio spectrum** |
| Lattice | `Path` (hex/triangle), cached | ignition |
| Nucleus + bloom | radial gradient + shader bloom (`bloom.frag`) | audio RMS |
| Particles | ≤ 120 points, `drawRawPoints` | processing state |
| Shockwaves | expanding stroked circles | TTS peaks, wake event |
| Callouts | widgets (`Callout`) positioned by polar coords | state |
| Glitch | shader RGB split (`glitch.frag`) | error event |

**Inputs:**

```dart
ReactorCore(
  state: CoreState.listening,          // boot, idle, wake, listening, processing,
                                        // speaking, approval, success, error, offline
  ignition: bootProgress,               // 0..1
  audio: audioBus.levels,               // ValueListenable<AudioFrame{rms, bands[72]}>
  callouts: [...],
)
```

Motion timings are in STITCH_PROMPTS.md §5.1, which is the contract.

### 12.5 Animation stack (which library does what)

All free and permissively licensed:

| Job | Use | Why |
|---|---|---|
| Reactor Core, spectrum, waveforms, gauges | **Flutter `CustomPainter` + `Ticker`** (built-in) | Procedural, so it reacts to live audio, stays crisp at any size, adds 0 MB of assets, and gives full control. Proven in aeris_remote |
| Glow/bloom, hex grid, haze, scan lines, film grain, glitch, holographic shimmer | **Fragment shaders** (`FragmentProgram`, GLSL `.frag` listed under `flutter: shaders:`) + **`flutter_shaders`** (MIT) helpers | GPU does the expensive per-pixel effects. Runs on Impeller (Android). Far cheaper than stacking `BackdropFilter`/`MaskFilter.blur` |
| Screen/panel entrance choreography, staggered reveals, shimmer, slides, blur-ins | **`flutter_animate`** (BSD-3) | Declarative chains: `.animate().fadeIn().slideY().then().shimmer()`. Perfect for "panels materialise" |
| Decode/scramble headers, typing terminal, count-up numbers | Own small widgets (`DecodeText`, `TerminalLog`, `CountUp`) on `AnimationController` | Tiny and exact. Avoids a dependency for 30 lines each |
| Designer-made pieces (logo sting, special icons) | **`rive`** (MIT runtime; free Rive editor) | Optional. State machines with inputs (e.g. `isSpeaking`, `level`), when you want to hand-design something in a visual editor |
| Small one-shot icon animations (check, warning) | **`lottie`** (MIT) | Optional. Free LottieFiles assets, recoloured to cyan |
| Haptics | `HapticFeedback` (built-in) | Wake tick, approval, error |
| Shared-element core → dock | `Hero` + custom `flightShuttleBuilder` | Built-in |

**Don't use video (Veo/MP4) or GIFs for live UI.** They can't react to the voice, they're blurry when scaled, and they're heavy. Video is fine only for a marketing/splash sting. This is the same conclusion reached in aeris_remote.

### 12.6 Speaking and listening animations: where the audio data comes from

The orb must react to **real** sound, not a fake loop:

| State | Source | How |
|---|---|---|
| **Listening** (Google STT owns the mic) | `speech_to_text` `onSoundLevelChange` → RMS (~10–20 Hz) | Android's recognizer doesn't expose raw PCM, so the 72-bar spectrum is **synthesised from the real RMS**: each bar = RMS × a per-bar noise curve that drifts smoothly over time. It looks like a spectrum and follows your voice exactly in loudness and timing |
| **Wake moment** | Wake service PCM (we own the mic then) | A real FFT of the last 300 ms is sent with the wake event, so the ignition burst is shaped by the actual "Hey AERIS" |
| **Speaking** (Neerja via `just_audio`) | Android **`Visualizer`** API attached to the player's `androidAudioSessionId` → real waveform + FFT at ~20 Hz, over channel `aeris/audio/viz` | Drives `MirroredWaveform`, shockwave peaks and nucleus brightness. Needs `RECORD_AUDIO`, which we already hold. If `Visualizer` fails on a device, fall back to the decoded MP3 envelope |
| **Word sync** | Edge TTS **WordBoundary** events (offset + text) from the same websocket | `TranscriptLine` highlights each word as it's spoken. The segment ring steps once per word |

Everything goes through one `AudioBus` (`lib/ui/reactor/audio_bus.dart`) of `ValueNotifier<AudioFrame>`, smoothed with an EMA (0.35) so it never jitters.

### 12.7 Performance budget (non-negotiable: the old app hit an ANR here)

| Rule | Why |
|---|---|
| One `Ticker` per Reactor Core; all layers read from it | N controllers = N rebuilds |
| `RepaintBoundary` around the core, background and each live graph | Isolates repaints |
| Audio → `ValueNotifier` → painter `repaint:` listenable. **Never `setState`** on a screen for audio | The aeris_remote ANR root cause |
| **No `BackdropFilter` over or inside anything that animates.** Blur only static layers, or use a pre-blurred snapshot | Blur every frame = dropped frames |
| Cache static paths, labels and the lattice; draw only what changes | |
| Particles ≤ 120, spectrum bars ≤ 72, shockwaves ≤ 3 alive | |
| Idle → 30 fps cap; app backgrounded or screen off → tickers stopped | Battery |
| Measure in **profile/release builds**, never debug | Debug exaggerates jank massively (aeris_remote lesson) |
| Target: 60 fps with no frame > 16 ms on RMX3741 in DevTools, during speaking state (the heaviest) | Acceptance gate for M3 |

**Reduced motion** (`MediaQuery.disableAnimations` or Settings → "Reduce effects"): static state frames, 150 ms cross-fades, no particles, no glitch, no scan lines. There's also a **"Battery saver visuals"** toggle that disables shaders except the haze.

---

## 13. Design workflow: Stitch → Figma → Flutter

1. **Stitch:** Prompt A (Master) until the Command Center and Reactor Core are right. Then the showpieces X01–X05, then S00…S72, each with the Design System Block (see STITCH_PROMPTS.md).
2. **Figma:** paste or export each screen. Name frames by screen ID. Turn repeated pieces into components (§12.2) and colours/type into styles (§12.1). Fix drift, since Stitch will vary paddings and colours slightly.
3. **Flutter:** build **components first** in a hidden `/kit` gallery route (every component in every state, light/dark). Then build screens from components only. A screen that needs a new visual means a new or extended component, never a one-off style.
4. **Check:** golden tests (`matchesGoldenFile`) for the kit gallery and key screens at 360 and 412 wide.
5. **Never paste Stitch HTML/Tailwind into the app.** It's a reference only.

---

## 14. Project structure, packages, native modules

### 14.1 Folders

```
aeris_assistant/
├─ docs/                     BUILD_GUIDE.md, STITCH_PROMPTS.md, decisions/
├─ assets/
│  ├─ fonts/                 Oxanium, Sora, JetBrains Mono (all OFL)
│  ├─ wake/                  melspectrogram.onnx, embedding_model.onnx, hey_aeris.onnx
│  ├─ brain/                 tools.json, system prompt, grammar (synced from aeris_brain)
│  ├─ sounds/                earcons
│  └─ (shaders/ at root)     hud_bg.frag, bloom.frag, glitch.frag, hologram.frag
├─ android/app/src/main/kotlin/com/aeris/assistant/
│  ├─ wake/                  WakeService.kt, AudioPipeline.kt, NoiseFloor.kt,
│  │                         OwwEngine.kt (ONNX), PersonalVerifier.kt (DTW),
│  │                         WakeEngine.kt (interface), SherpaEngine.kt (fallback)
│  ├─ a11y/                  AerisAccessibilityService.kt
│  ├─ apps/                  AppLauncher.kt
│  ├─ audio/                 PlaybackVisualizer.kt (Visualizer → waveform/FFT)
│  ├─ assist/                AssistEntry (ACTION_ASSIST in MainActivity)
│  ├─ llm/                   LlamaBridge.kt (v0.6)
│  └─ channels/              Channels.kt (method/event channel wiring)
├─ lib/
│  ├─ app/                   main.dart, router.dart, brand.dart, bootstrap.dart
│  ├─ ui/                    tokens.dart, theme.dart, kit/, reactor/ (core painters, audio_bus.dart)
│  ├─ features/
│  │  ├─ home/  voice/  conversation/  agent/  activity/  memory/
│  │  ├─ routines/  abilities/  reminders/  devices/  settings/  onboarding/
│  ├─ voice/                 voice_session.dart (state machine), stt.dart,
│  │                         utterance_stitcher.dart, tts_edge.dart, tts_device.dart
│  ├─ wake/                  wake_channel.dart, wake_settings.dart, enrolment.dart
│  ├─ brain/                 router.dart, contract.dart, tools.dart, grounding.dart,
│  │                         llm_tier.dart, cloud_tier.dart, laptop_tier.dart
│  ├─ skills/                one file per domain + registry.dart
│  ├─ actions/               executor.dart, approval_policy.dart, undo.dart
│  ├─ data/                  db.dart (drift), repositories/
│  └─ core/                  log.dart (ring buffer), result.dart, lang.dart, clock.dart
├─ test/                     unit, widget, golden, fixtures/ (wake golden wavs, brain golden)
└─ tools/                    wake_eval.py (FA/h + miss rate on recordings), sync scripts
```

### 14.2 Packages (all free)

| Need | Package | Licence |
|---|---|---|
| State | `flutter_riverpod` | MIT |
| Routing | `go_router` | BSD-3 |
| DB | `drift` + `sqlite3_flutter_libs` | MIT |
| STT | `speech_to_text` | BSD-3 |
| TTS fallback | `flutter_tts` | MIT |
| Audio playback (Neerja) | `just_audio` | MIT/Apache |
| WebSocket | `web_socket_channel` | BSD-3 |
| Secure store | `flutter_secure_storage` | BSD-3 |
| Contacts | `flutter_contacts` | MIT |
| Intents | `android_intent_plus`, `url_launcher` | BSD-3 |
| Battery | `battery_plus` | BSD-3 |
| Animation chains | `flutter_animate` | BSD-3 |
| Shader helpers | `flutter_shaders` | MIT |
| Designer animations (optional) | `rive` | MIT |
| Icon animations (optional) | `lottie` | MIT |
| Fonts | Oxanium, Sora, JetBrains Mono (bundled files, not runtime fetch) | OFL |
| Crypto (laptop) | `cryptography` | Apache-2.0 |
| HTTP (cloud) | `http` | BSD-3 |
| ONNX (Kotlin) | `com.microsoft.onnxruntime:onnxruntime-android` | MIT |
| LLM (v0.6) | llama.cpp (JNI) or `llamadart 0.10.0` (pinned, as proven in aeris_remote) | MIT |

Wake models: **openWakeWord code is Apache-2.0**. Its **pretrained** models are published under a non-commercial licence (CC BY-NC-SA, verify on the repo before relying on this), which is fine for development and personal use. **Your own trained `hey_aeris.onnx` is yours.** The embedding backbone comes from Google's speech-embedding model; check its licence on the openWakeWord repo too.

### 14.3 Platform channels

| Channel | Direction | Methods / events |
|---|---|---|
| `aeris/wake` | Dart → Kotlin | `start`, `stop`, `pause`, `resume`, `setSensitivity`, `enrolStart/Stop`, `status` |
| `aeris/wake/events` | Kotlin → Dart | `wake{score1,dtw,at}`, `level{rms}`, `state{running,owner}`, `error{code}` |
| `aeris/a11y` | Dart → Kotlin | `dumpUi`, `clickId`, `longClickId`, `typeId`, `pressEnter`, `global{back,home,recents,notifications,screenshot}`, `readScreen` |
| `aeris/apps` | Dart → Kotlin | `list`, `launchByLabel` |
| `aeris/assist` | Kotlin → Dart | `assist{cold}` |
| `aeris/audio/viz` | Kotlin → Dart | `frame{rms, bands[72], waveform[128]}` at ~20 Hz while TTS plays (§12.6) |
| `aeris/llm` | Dart ↔ Kotlin | `load`, `generate(stream)`, `unload`, `stats` (v0.6) |

---

## 15. Permissions, onboarding, keeping alive

| Permission | Why | When asked |
|---|---|---|
| `RECORD_AUDIO` | wake + commands | onboarding S03 |
| `POST_NOTIFICATIONS` | FGS notification | S03 |
| `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MICROPHONE` | wake service | manifest |
| `READ_CONTACTS` | call/message by name | S03 (skippable) |
| `CALL_PHONE` | direct calls | first call (just-in-time) |
| Accessibility service | screen read/tap/agent | S03 "Set up" → system page |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | survive Doze | S03 |
| `SCHEDULE_EXACT_ALARM` / `USE_EXACT_ALARM` | reminders | first reminder |
| Default assistant role | power-button hold | Settings (optional) |

### ColorOS / Realme keep-alive checklist (shown in onboarding and Settings S54)

1. Battery → AERIS → "Allow background activity" / unrestricted.
2. App info → "Auto-launch" ON.
3. Recents → lock the AERIS card.
4. Notification for the FGS must stay enabled. If the user blocks it, warn them.

**Health check:** on every app open, verify that the service is running, the mic is owned by the spotter, there's no battery restriction, and auto-launch is confirmed. Surface a score (S54: "4/5").

**After reboot (Android 15):** post a normal notification, "Tap to resume listening for 'Hey AERIS'", from `BOOT_COMPLETED`. That's allowed. The tap starts the FGS from a user interaction.

---

## 16. Privacy and security

- **Wake detection is fully on-device.** No audio leaves the phone before a wake.
- **After a wake:** audio goes to Google for STT, and reply text goes to Microsoft for Neerja TTS. Disclosed plainly in onboarding and S55. Offline fallback TTS keeps text local.
- **Cloud brain** is off by default. When on, the request text (and screen text, for "explain my screen") goes to Google Gemini. Each use is tagged CLOUD in Activity.
- **Secrets:** the Gemini key and laptop pairing secret live in `flutter_secure_storage` (Android Keystore).
- **Lock screen:** answers info-only (time, weather, timers). Personal actions (messages, calls to non-favourites, memory, screen) require unlock.
- **No analytics, no crash upload, no account.** Crash logs stay local and are shared only through Diagnostics → Share.
- **Logs must never contain message bodies or contact numbers.** Redact in `log.dart`.
- **Repo is public** (`shivangrastogi/S.Y.N.E.X`): never commit enrolment embeddings, recordings, `misses.jsonl`, keys or `.env`. Add them to `.gitignore` on day one.

---

## 17. Testing and the numbers we track

### 17.1 Automated

| Layer | What | How |
|---|---|---|
| Wake parity | Kotlin openWakeWord scores = Python scores (±1e-3) on 10 golden WAVs | JVM unit test with ONNX Runtime |
| Verifier | DTW accepts own samples, rejects others/hiss | unit, synthetic + recorded fixtures |
| Voice session | every state transition, timeouts, "bas"/"bye", approval paths | Dart unit with fake STT/TTS/router |
| Skills | phrase → (tool,args) collision corpus (port aeris_remote's, grow it) | Dart unit; corpus file is the contract |
| Brain contract | Dart ↔ Python golden fixtures | Dart unit |
| Approval policy | every send/delete/pay path needs approval or is refused | Dart unit |
| UI | kit gallery + key screens | golden tests at 360/412 |

### 17.2 On-device metrics

Run `tools/wake_eval.py`, which mirrors the Jaco benchmark method:

- **Miss rate:** 100 "Hey AERIS" by you (varied distance/volume/noise) + 50 by others with voice-match off → % detected.
- **False accepts/hour:** play 8 h of mixed TV/podcast/Hindi-English talk next to the phone → wakes per hour. **Target ≤ 0.125/h** (1 per 8 h).
- **Latency:** end of "AERIS" → chime, from screen recording + audio. **Target < 300 ms.**
- **Battery:** 24 h `dumpsys batterystats` with only the wake service on. **Target ≤ 3%.**
- **Survival:** % of a 24 h day the service is alive (from wake_events heartbeat). **Target ≥ 99%.**
- **Understanding:** your real-utterance set (≥ 200 lines, Hinglish + English) → correct action. **Target ≥ 95%.**

Record each run in `docs/metrics.md` with date, build, model version and thresholds. Tune thresholds from these, never by feel.

---

## 18. Milestones and acceptance criteria

| # | Milestone | Done when |
|---|---|---|
| M0 | Scaffold | `flutter create`, tokens/theme, kit gallery route, go_router, CI-style `flutter analyze` + `flutter test` clean, `.gitignore` privacy block |
| M1 | Design | Stitch Prompt A + showpieces X01–X05 + S00–S72 approved, Figma components (ReactorCore variants, HudPanel …) + styles done |
| M2 | Wake engine (pretrained test model) | Kotlin FGS + openWakeWord parity test green. Detects "hey jarvis" on device. Diagnostics shows live score + floor |
| M3 | Voice loop + living core | wake → STT → stitched text → echo via Neerja → back to wake, 20 cycles without a stuck mic. Reactor Core animates all states from real audio (mic RMS, Visualizer, word boundaries). **60 fps, no frame > 16 ms in profile build on RMX3741** |
| M4 | "Hey AERIS" + Voice Match | Custom model trained (§19), enrolment S04/S05 works. §17 miss ≤ 10% and FA ≤ 0.5/h (first pass) |
| M5 | Skills + approvals | Scenarios 1–4, 7, 9, 12 pass by voice. Approval tests green. Activity shows every turn |
| M6 | Brain | Shadow mode logs T1 decisions. Cloud tier with key. Scenario 5, 8, 11 pass |
| M7 | Agent + routines | Scenario 6 passes with approval. Routines CRUD + voice trigger |
| M8 | Hardening | §17 targets met on RMX3741 (release build), 3 days of daily use without a service death, privacy review done |
| M9 | v1.0 | Widgets/QS tile/lock screen, light theme, accessibility pass, laptop link (scenario 10) |

**Order of work:** M0 → M2 → M3 are the spine (the hard, risky native work), so do them first. M1 (design) runs in parallel since it's your Stitch time.

---

## 19. Wake-word training guide ("Hey AERIS")

You run training yourself, in Colab. Claude never runs it.

1. **Get the official notebook.** The openWakeWord repo has an automatic model training notebook. Open it in Colab (a T4 is enough).
2. **Phrase:** `hey aeris`. Also try alternate spellings the TTS pronounces correctly ("hey airis", "hey eh-ris"). Generate a few test clips first and listen. Pick the spelling that *sounds* like how you say it.
3. **Positive data:** the notebook generates thousands of synthetic clips with many voices. **Add your own:** record 30–50 real "Hey AERIS" on the RMX3741 (quiet, noisy, far, near) and include them. Real-voice samples matter most.
4. **Negative data:** the notebook's general negative sets, **plus Hindi/Hinglish speech and TV audio**, since the benchmark shows openWakeWord degrading in babble noise. Add confusables: "hey Alexa", "Harris", "errors", "aries", "hey Siri", "theory".
5. **Augmentation:** room impulse responses, background noise at 0–15 dB SNR, gain variation. These are the notebook defaults; keep them on.
6. **Export** `hey_aeris.onnx`. Drop it into `assets/wake/` and bump `WAKE_MODEL_VERSION`.
7. **Evaluate** with `tools/wake_eval.py` (§17.2) before using it daily. Keep the previous model to compare against.
8. **Iterate:** every false wake logged in `wake_events` can be exported (opt-in) as a hard negative clip for the next training round.

Training data generation uses TTS voices only as *data*. That doesn't change the assistant's voice stack (§3.2).

---

## 20. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| openWakeWord misses Indian-accented "AERIS" | Medium | High | Own recordings in training, stage 2 on your voice, sherpa-onnx fallback behind the same interface |
| False wakes from TV/Hindi speech | Medium | High | Hindi/TV negatives, stage 2 DTW + plausibility, refractory, Low preset |
| ColorOS kills the FGS | High | High | Keep-alive onboarding, health check, reboot notification, heartbeat metric |
| Edge TTS endpoint changes/blocks | Medium | Medium | Phrase cache + automatic Android TTS fallback. Desktop users of edge-tts would notice too, so watch the edge-tts project |
| Kotlin openWakeWord feature drift vs Python | Medium | High | Golden parity test is mandatory (M2) |
| On-device LLM too slow/hot | Medium | Medium | Shadow mode, prefix cache, unload when idle, T0 handles the common 80% |
| Agent mis-taps | Medium | High | Approval gate in code, never-automate list, step caps, Stop button |
| Scope creep (too many screens) | High | Medium | Milestones are gates. v1.0 screens beyond M5 wait |
| Sci-fi visuals cause jank/ANR or eat battery | Medium | High | §12.7 budget, shaders over blur, one Ticker, profile-build gate in M3, reduce-effects + battery-saver visuals toggles |
| HUD looks cluttered or "gamer" instead of premium | Medium | Medium | One cyan family, ≤ 4 HUD details/screen, Sora for all readable text, the "dial it down" follow-ups in STITCH_PROMPTS §4 |

---

## 21. Open decisions

1. **App name.** Keep "AERIS" or rename? It affects the wake phrase, so decide before M4.
2. **Wake phrase.** "Hey AERIS" vs just "AERIS". Two syllables are short and false-wake-prone, so "Hey AERIS" is recommended.
3. **State management.** Riverpod (recommended, used in Momentum/ClearWay) vs plain ChangeNotifier (used in aeris_remote).
4. **LLM runtime.** Raw llama.cpp JNI (more control) vs `llamadart 0.10.0` (already proven in aeris_remote).
5. **Laptop link in v1.0 or later?** It's optional per the principles.
6. **Cloud tier default.** Off (privacy, recommended) vs on-with-key.

---

## 22. Glossary

| Term | Meaning |
|---|---|
| **KWS** | Keyword spotting, a tiny model that detects one phrase |
| **FA/h** | False accepts (wrong wakes) per hour |
| **Miss rate** | % of real wake attempts not detected |
| **RTF** | Real-time factor: compute time ÷ audio time. 0.001 = 1 ms per second of audio |
| **FGS** | Android foreground service (persistent notification, allowed to use the mic) |
| **DTW** | Dynamic time warping, which compares two sequences that differ in speed |
| **a11y** | Accessibility service, used to read and act on other apps' screens |
| **Tier** | Which brain answered: Skills / On-device / Laptop / Cloud |
| **Shadow mode** | The new brain runs and logs but doesn't act, for comparison |
| **Prefix KV cache** | Reusing the LLM's computed system prompt so each turn starts fast |
