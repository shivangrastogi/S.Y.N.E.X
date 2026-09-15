# AERIS Mobile — Audit + Master Plan

Two parts:
- **Part A — the audit:** every real mistake in the mobile app right now, ranked by
  severity, with root cause, location, and status (fixed today vs recommended).
- **Part B — the master plan:** how everything built so far (mobile Phases 1–9 + the
  laptop agent + the Autonomous-Year plan) becomes one coherent, "consciousness-grade"
  personal agent — and the reliability-first order to get there.

Audited by reading the code (not guessing), 2026-07-12.

---

## Part A — Audit: what's actually wrong

### 🔴 Critical — the false-wake bug (FIXED today)

The complaint "**bahut baar wake word nahi bolta phir bhi on ho jata hai**" had four
compounding root causes. All four are fixed in this pass.

| # | Root cause | Where | Fix (applied 2026-07-12) |
|---|---|---|---|
| A1 | **Ungated software AGC amplified ambient noise up to 8×.** In a quiet room `_agcPeak` decays toward ~0, so *any* faint hiss/fan/TV got boosted to speech level and matched. This was the dominant cause. | `wake_service.dart` `_onAudio` | Added a **VAD energy gate** (`rms ≥ 0.012`) — silence now passes through **unamplified**; gain cap lowered 8×→4×. |
| A2 | **Operating point far too hot:** `keywordsThreshold 0.12` + `keywordsScore 3.0` (an over-correction from the earlier "won't detect" phase). | `wake_service.dart` KWS config | Rebalanced to **0.22 / 2.2**. |
| A3 | **Loose phonetic spellings** `ERRORS`, `ARRIES` mapped to AERIS — extremely common sounds in speech/TV. | `assets/kws/keywords.txt` | Dropped the noisy spellings; kept `AERIS / AIRES / ERIS / HEY AERIS / JARVIS`. |
| A4 | **No debounce / refractory** — a single decode frame fired instantly, so one noise burst could wake repeatedly. | `wake_service.dart` `_onAudio` | Added a **3 s refractory** guard between wakes. |

> **Why this also helps the _missed_ wakes:** the earlier "fix" for missed detections was to
> crank sensitivity, which made noise fire. The correct fix is the VAD-gated AGC — genuine
> (even quiet) speech still gets a modest boost and is caught at a sane threshold, while noise
> is no longer manufactured into a wake. Net: fewer false wakes **and** steadier real ones.

### 🔴 Critical — self-hearing wake (FIXED 2026-07-12, salvaged from an earlier audit)

| # | Root cause | Where | Fix |
|---|---|---|---|
| A15 | **`_endConversation()` re-armed the hotword (`resumeMic`) without stopping TTS.** If it ran while AERIS was still speaking (stop button mid-speech, or a dismissal), Porcupine resumed and could wake on AERIS's *own voice* — especially with the "ERRORS" spelling active. | `chat_screen.dart` | `_endConversation` now `_tts.stop()`s first, then resumes the mic after a 500 ms audio-drain guard. |

### 🔴 Critical — mic yanked mid-conversation (FIXED today)

| # | Root cause | Where | Fix |
|---|---|---|---|
| A5 | The wake service armed a blind **30 s failsafe** to retake the mic if the app never came up (crash case). But the app holds the mic for the *whole* conversation and only releases it at the end — so any conversation **longer than 30 s** tripped the failsafe, which **restarted Porcupine while STT was still listening**, corrupting the turn. Multiple wakes also stacked multiple timers. | `wake_service.dart` `_onWakeWord`, `chat_screen.dart` | Failsafe is now a single cancellable timer, **cancelled the moment the app acks by holding the mic** (`_startConversation` → `pauseMic`) or finishing (`resumeMic`). It now only fires on a genuine crash. |

### 🟠 High — recommended next

| # | Issue | Symptom | Fix |
|---|---|---|---|
| A6 | **No personal wake model.** The 3.3 M generic zipformer + hand-written phonetic spellings is inherently noisy — it's the accuracy ceiling for both false wakes and misses. | Wake never becomes rock-solid | Train a wake word on **your own voice** (record 20–30 "Aeris" samples), or add a **2-stage verify** (a cheap on-device speaker/keyword re-check on the 1 s around the trigger before launching). This is the real cure. |
| A7 ✅ | **Contacts reloaded on every call/SMS/WhatsApp.** `_resolveNumber` called `getContacts(withProperties: true)` each time. | Lag / possible ANR on big contact lists | FIXED 2026-07-12: contacts cached (5-min TTL) in `phone_skills.dart`; lookups hit the flat cache instead of reloading the address book. |
| A8 | **Continuous session ends on one 12 s silence.** | Feels abrupt; drops mid-thought | Make it configurable; optionally a soft "haan, bolo?" re-prompt before closing. |

### 🟡 Medium

| # | Issue | Where | Fix |
|---|---|---|---|
| A9 ✅ | **~29 empty `catch (_) {}`** swallow errors silently — the reason "bahut errors" are invisible. | across `lib/*.dart` | FIXED 2026-07-12: added `lib/aeris_log.dart` (in-memory ring buffer) + an **Error log** viewer (Assistant settings → Error log); wired the highest-value sites (skill failures, Gemini errors). More `catch` sites can route here incrementally. |
| A10 ✅ | `_registerPush()` (FCM token, listeners) runs even in **standalone** mode where there's no bridge to receive it. | `chat_screen.dart` | FIXED 2026-07-12: guarded on `_bridge != null`. |
| A11 ✅ | **No in-app sensitivity/tuning UI** — adjusting wake sensitivity needed a rebuild. | — | FIXED 2026-07-12: Low/Balanced/High selector in Assistant settings; the service reads it at spotter construction (low 0.30/2.0 · balanced 0.22/2.2 · high 0.15/2.6) and auto-restarts on change. A live confidence meter remains a nice-to-have. |
| A12 | Gemini **API key in the URL** query string. | `cloud_brain.dart` | Fine for Google, but prefer a header if the endpoint accepts it; never log the URL. |

### Found in self-review of the fixes (2026-07-12, second pass)

| # | Issue | Fix |
|---|---|---|
| A13 ✅ | **Stale ChatScreen State on pair/unpair** — no `key` on `ChatScreen`, so pairing from the menu never built the bridge (until app restart) and unpairing left the old bridge running. | `ValueKey(pairing?.pid ?? 'standalone')` in `main.dart` — State recreates on pairing change. |
| A14 ✅ | **No STT `onError`** — engine errors were invisible and a single transient `error_no_match`/`error_busy` silently killed the conversation. | `onError` wired to the AerisLog + **one transient-error retry per turn** (re-armed on each real result). |

### Found in the blueprint-verification pass (2026-07-12, third pass)

| # | Issue | Fix |
|---|---|---|
| A16 ✅ | **Dashboard poll consumed the initiative budget** — `_collect_mind` called side-effectful `tick()` every 3 s, marking things "surfaced" + eating the anti-nag budget (a GET must be read-only; would have starved real proactive speech later). | `InitiativeEngine.preview()` (pure) added; dashboard uses it. Test guards it. |
| A17 ✅ | **Adaptive noise floor never rose in an always-loud room** — the update only ran on quiet frames, so a fan/AC room kept getting amplified (stage-2 still blocked wakes, but the "fan becomes the floor" claim was false). | Slow-rise branch added for loud frames (fan reaches the floor cap in ~a minute; 1 s speech shifts it ~3% — negligible). |
| A18 ✅ | **Manual hold-to-talk deadlock (the old audit's P0-2, still alive)** — a manual listen ending with NO final result (silence/error) never called `resumeMic` → hotword dead until the next manual action. | `onStatus(notListening/done)` now resumes the hotword when not in a conversation (resume is idempotent service-side). |

### 🔵 Low

- **KGP plugin warnings** (future Flutter will fail) — track plugin updates (`record_android`, `speech_to_text`, `torch_light`, `flutter_foreground_task`, …).
- **Only debug builds tested** — a release build (R8/proguard) may strip or shrink something (sherpa/onnx native libs, reflection). Test a release APK before relying on it daily.
- **Live-web "grounding" is paid** on Gemini 2.5 (already handled with a no-grounding fallback) — real-time answers need a 3.x model or a paid key; document it in-app.

**Verification of today's fixes:** `flutter analyze` clean on the changed files; debug APK builds. On-device confirmation still needed — install and (a) leave it in a quiet/noisy room for a while to confirm no phantom wakes, (b) hold a >30 s conversation to confirm the mic isn't yanked.

---

## Part B — Master plan: toward a "consciousness-grade" AERIS

### What "consciousness" means here (honestly)

Not literal sentience — that's not an engineering target and claiming it would be dishonest.
What *is* buildable, and what makes an assistant feel like a mind rather than a command
box, is a concrete set of properties:

1. **Continuity of memory** — it remembers across time, not just this turn.
2. **A self- and world-model** — it knows what's going on, what it can do, and what it can't.
3. **Persistent goals + initiative** — it holds intentions and acts on them unprompted.
4. **Reflection** — it critiques its own actions and adjusts.
5. **Identity + voice** — a consistent personality that is recognizably *yours*.
6. **Learning** — it becomes more *you* over time.

AERIS already has real pieces of all six (memory stores, an agent loop, routine learning,
perception, a distinct Hinglish voice). The plan below is about making them **reliable,
unified, and continuous** — that's the difference between "impressive demo" and "a presence
you trust."

### One mind, two bodies

The single most important architectural idea: **the phone and the laptop are not two apps —
they are two bodies of one agent.**

```
                         ┌──────────── THE AERIS MIND ────────────┐
                         │  Memory Fabric  ·  Goal System  ·       │
                         │  Agent Runtime  ·  Autonomy Ladder      │
                         │  (laptop core — the "big brain")        │
                         └───────────────▲───────────┬────────────┘
                        E2E encrypted bridge (sync)   │
              ┌──────────────────────────┘            ▼
   ┌──────────┴───────────┐              ┌────────────────────────┐
   │  PHONE (senses+hands) │              │  LAPTOP (compute+web)  │
   │  always-with-you      │              │  always-on reasoning   │
   │  hotword, mic, TTS,   │              │  local LLM, Playwright,│
   │  location, calls,     │              │  screen agent, files   │
   │  apps, screen a11y    │              │  heavy planning        │
   └──────────────────────┘              └────────────────────────┘
```

Today the phone runs its own 3-tier brain (on-device skills → laptop → Gemini). The target
is that the phone becomes a **perception + actuation node of the same agent**: it shares the
**Memory Fabric** and **Goal System** (already built — Q1 M1/M2) over the bridge, so a goal
captured by voice on the phone is the *same* goal the laptop works on, and what AERIS learns
on one body it knows on the other. That's continuity — property #1 and #6.

### The reliability-first order (why this sequence)

A mind you can't trust to hear its own name isn't a mind — it's a toy. So the order is
**reliability → continuity → depth**, not features-first.

**Track 0 — Make the phone rock-solid (NOW, partly done today).**
- ✅ False-wake + mic-lifecycle fixes (Part A A1–A5).
- ▶ Personal wake model or 2-stage verify (A6) — the durable cure.
- ▶ Contact cache (A7), error surfacing / in-app logs (A9), sensitivity UI (A11).
- ▶ Test a **release** build (A-Low) before daily reliance.
- *Definition of done:* a week of daily use with zero phantom wakes and zero mic stalls.

**Track 1 — Unify the mind across bodies (bridge the phone into the AAR).**
- Sync a relevant **Memory Fabric** slice to the phone so standalone answers are personal.
- Share the **Goal System**: capture on phone → the laptop's resumable orchestrator
  (already built) pursues it → results surface on whichever body you're near.
- Route by **body capability**: phone for sense/act, laptop for heavy reasoning/web.
- *This is where the Autonomous-Year Q1–Q3 work and the mobile app converge.*

**Track 2 — Initiative on the phone (the "presence").**
- Once the laptop-side **Initiative Engine** (Q2 M5, salience-scored) exists, let it speak
  through the phone — the always-with-you body — governed by the **Autonomy Ladder** and
  quiet-hours. This is what makes AERIS feel *alive*: it notices and speaks, but only when
  it earns the interruption. (Getting salience right is the make-or-break, per the year plan.)

**Track 3 — Depth + polish.**
- Barge-in refinements, TTS ducking, richer on-device skills, cross-device continuity
  ("start on phone, finish on laptop"), and the personalization/learning loop (Q4).

### Where each already-built piece fits

| Built | Role in the mind |
|---|---|
| Mobile Phases 1–9 (hotword, 3-tier brain, skills, a11y, assist-role, HUD) | the **body**: senses, voice, hands |
| Laptop agent (`agent_orchestrator`, `kg_memory`, `routine_learner`, perception, 100+ skills) | the **cortex**: reasoning, habits, world-sense |
| Q1·M1 **Memory Fabric** (built) | **continuity** — one ranked recall over all memory |
| Q1·M2 **Goal System** (built) | **intention** — standing goals that resume |
| Q1·M3 Autonomy Ladder + Ledger (next) | **conscience** — trust, explainability, undo |
| Q2 World Model + Initiative (planned) | **awareness + will** — notices, decides, acts |
| Q3 Tiered brain + Reflexion + sub-agents (planned) | **thought** — deeper, self-correcting reasoning |
| Q4 Learning + continuity (planned) | **selfhood** — becomes recognizably *yours* |

### Immediate next steps (recommended)

1. **On-device test today's wake fixes** (quiet + noisy room, long conversation). Report back;
   if any phantom wakes remain, the next lever is raising `keywordsThreshold` toward 0.28 and
   then the personal wake model (A6).
2. **A6 — personal wake reliability**: record your "Aeris" samples; I'll derive tighter
   spellings (as done before) or wire a 2-stage verify. This is the single biggest win.
3. **A7 + A9 — robustness**: contact cache + an in-app error log so "bahut errors" become
   visible and fixable.
4. Then **Track 1**: bridge the phone into the Memory Fabric + Goal System (the mind-unifying
   step) — this is where the mobile app stops being a remote and becomes a body of the agent.

The honest headline: the foundation is genuinely strong. The gap between "advanced assistant"
and "a mind you rely on" is **reliability first, then continuity** — and today's fixes are the
first, most-needed step on that path.
