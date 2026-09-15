# A.E.R.I.S — Eternal Live Presence & Personal-Assistant Roadmap

**Companion to [`ROADMAP.md`](ROADMAP.md).** That document hardened AERIS into a
well-supervised Windows process. This one takes the next step: turning it from a
*command box you talk to* into a **continuous, ambient presence** — something that
is quietly *there*, aware of context, and proactively useful in the real,
day-to-day sense. A personal assistant in the actual manner.

The bar for everything here is one word: **usable.** Every feature must be
real (no demo-ware), respectful (cooldowns, quiet hours, privacy switch), and
something you'd actually leave switched on for weeks.

---

## North-star for presence

1. **Always there, never in the way.** Proactive moments are governed by
   per-kind cooldowns, quiet hours (23:00–07:00), and the global privacy
   switch. If it ever feels naggy, it has failed.
2. **Context over commands.** It should fuse what it already senses — camera
   presence, idle/power, foreground-app profile, time of day — and act on the
   *fused* picture, not single triggers.
3. **Graceful degradation.** No webcam? Idle + workspace + clock still drive
   the whole thing. Every signal source is optional.
4. **Earned trust before automation.** Suggest first, act later. High-impact
   or destructive actions always confirm; voice-biometric gate for the
   privileged ones.
5. **Real gestures, real functions.** Every gesture and skill maps to a thing a
   person genuinely does at a desk — not a party trick.

---

## ✅ Phase 0 — Foundation (shipped 2026-06-22)

- **`core/eternal_presence.py`** — the always-on heartbeat. Fuses camera
  presence + idle/power + workspace profile + time-of-day into one
  `PresenceContext` and a 4-state machine (**AWAY → IDLE → ACTIVE → FOCUS**).
- **Proactive moments** with cooldowns: time-of-day greeting, welcome-back on
  return, quiet farewell on leaving, focus/hydration nudge after a long deep-work
  stretch, gentle low-battery heads-up. Hinglish-flavoured, swappable templates.
- **Listener model** — consumers register `add_listener(fn)`; nothing here
  touches Qt/TTS. `install(speak=, on_moment=)` wires speech + orb + shutdown hook.
- **Tests** — `tests/test_eternal_presence.py`, 9 deterministic tests (fake clock,
  no camera/torch). All green.

---

## Phase 1 — Wire the presence into the living app

> Make it felt, not just instantiated.

- ✅ **1a. GUI orb reacts to presence state.** ArcReactor gained a presence-dim
  axis (`set_presence_state`) orthogonal to the activity state: away → 0.30,
  idle → 0.62, active/focus → 1.0, eased + applied as a global `QPainter`
  opacity (faint ember floor). Forwarded through `stage.set_presence_state`,
  driven by the app's 5 s presence poll. *(shipped 2026-06-22)* **Phase 1 done.**
- ✅ **1b. Speak the important moments.** Priority ≥ 1 moments routed to the
  existing TTS worker via `request_speak`; priority 0 (farewell) silent/log-only.
  Greetings/welcome-backs also drop a proactive chat line. *(shipped 2026-06-22)*
- ✅ **1c. Presence pill in the titlebar** — live coloured `PRESENCE` chip
  ("FOCUS · 42m", "AWAY"), polled every 5 s from the fused context, colour per
  state (away grey / idle amber / active green / focus cyan). *(shipped 2026-06-22)*
- ✅ **1d. Settings block** — `"presence"` object in `data/settings.json`
  (`enabled`, `heartbeat_s`, `quiet_start_h`, `quiet_end_h`, `speak_moments`).
  Engine honours all of them (master switch gates `start()`; quiet hours are
  per-instance). *Pending:* surfacing it in the in-app settings page.
  *(shipped 2026-06-22)*
- ✅ **1e. Daily presence digest** — `_show_daily_digest()` posts yesterday's
  one-line summary as a chat line once on boot, from `presence_journal`.
  *(shipped 2026-06-22)*

## Phase 2 — Proactive intelligence (suggest, don't surprise)

> The assistant notices patterns and offers — you decide.

- 🟡 **2a. Routine learner** — `core/routine_learner.py` (engine done): reads
  `presence_journal` history, detects stable weekday arrival times per workspace
  profile + evening wind-down, returns `Suggestion`s (title + confidence +
  ready `routine_spec`, always `enabled:False`). Needs ≥4 distinct days inside a
  ±45 min window; ignores >21-day-old + weekend + IDLE-profile data. Pure +
  unit-tested (6 tests). *Pending:* a GUI offer-card that turns a `Suggestion`
  into a one-tap accept → `core.automation` create. *(engine shipped 2026-06-22)*
- **2b. Re-engagement memory** — on return from a > 30 min absence, recall the
  last thing in progress (last file/app/chat topic via `semantic_memory`) and
  offer "wahin se continue karein?" with a real resume action.
- **2c. Meeting guard** — on `workspace_enter MEETING`: auto-suggest mic-level
  check, mute notifications, dim proactive moments to silent for the duration.
- **2d. Context-aware quick actions** — extend `SmartSuggestionsPanel` to read
  the fused `PresenceContext` directly (it currently re-derives a subset).
- **2e. End-of-day wind-down** — in the evening, if idle starts trending up,
  offer a wind-down: summarise the day, list tomorrow's `- [ ]` todos, dim screen.

## Phase 3 — Actual gestures (desk-real, accessibility-grade)

> Builds on the existing 21-gesture engine. Each new one earns its slot.

- ✅ **3a. Presence-gated gestures** — `core/gesture_gate.py`: subscribes to the
  fused presence state via the new `eternal_presence.add_state_listener`; arms
  the gesture engine only in ACTIVE/FOCUS, disarms on IDLE/AWAY. Only ever
  resumes a session *it* paused (won't override a user-disabled engine) and
  privacy-mode forces disarm. Engine + privacy injectable → 6 tests with fakes
  (no camera/MediaPipe). Wired into `app._install_presence`. *(shipped 2026-06-22)*
- **3b. Glance-to-wake** — sustained face toward camera (not just present) for
  1.5 s while AERIS is minimised → bring window forward + arm mic. Hands-free.
- **3c. Palm-hold "hold my thought"** — open palm held 2 s → start a voice memo;
  release → save to `data/notes/` with timestamp. For mid-task ideas.
- **3d. Two-finger scrub = scrub media/timeline** — horizontal index+middle
  drag maps to ←/→ in the foreground media app (finer than the existing
  next-track gesture).
- **3e. Air-sign shortcuts (user-defined)** — let the user *record* an air-stroke
  (reuse the stroke recognizer) and bind it to any skill. Persist to
  `data/custom_gestures.json` (file already exists in the tree).
- **3f. Gesture confidence HUD** — a brief on-screen confirmation of the
  recognised gesture before it fires the action, with a 400 ms cancel window
  (wave to abort). Stops accidental destructive gestures.

## Phase 4 — Voice presence (ambient, low-friction)

- **4a. Always-listening wake word** (opt-in, local) — porcupine/openWakeWord
  for "JARVIS" so you don't touch the hotkey. Hard off-switch + mic LED state.
- **4b. Barge-in** — speaking over TTS interrupts it cleanly.
- **4c. Streaming STT partials** — show words as you speak (Whisper streaming /
  `core/stt_whisper.py`), so it feels responsive.
- **4d. Voice biometric gate** — `core/voice_id.py` verifies the speaker before
  honouring privileged commands (vault, shutdown, "delete"). Ties to ROADMAP 5d.
- **4e. Ambient acknowledgement** — a soft, short verbal "hmm?" on wake so you
  know it's listening without staring at the screen.

## Phase 5 — Real personal-assistant functions

> The "does actual useful things" layer. Each is a concrete skill or pipeline.

- **5a. Morning briefing** — on first arrival: time, weather (`info_skills`),
  battery, today's calendar + todos, one-line "what's on" — spoken in ~10 s.
- **5b. Calendar + reminders** — local ICS / Outlook-COM read; natural-language
  reminders ("mujhe 4 baje yaad dilana") → native toast at the time.
- **5c. Smart Do-Not-Disturb** — auto-engage Focus Assist in FOCUS state and
  during MEETING; auto-release on AWAY. Already have the registry hook in
  `focus_mode.py`; drive it from presence.
- **5d. Inbox / message glance** (opt-in, read-only) — surface unread counts via
  existing notify-listener; never auto-replies.
- **5e. Clipboard & file butler** — "AERIS, isko save kar do" grabs the
  clipboard/selection into a dated note; "kal wala file" recalls recent files.
- **5f. Health nudges that respect focus** — water/posture/eye-break reminders
  scheduled *around* focus blocks, not interrupting them (queued for the next
  natural break the presence engine detects).
- **5g. Conversational memory recall** — "humne X ke baare mein kya discuss kiya
  tha?" → `semantic_memory.recall` surfaces it. Already have the engine; add the
  natural phrasing intents.

## Phase 6 — Continuity & the "eternal" promise

> Presence that survives restarts, days, and devices.

- ✅ **6a. Persisted presence journal** — `core/presence_journal.py`: append-only
  rolling `data/presence_journal.jsonl` (state transitions + moments), atomic
  trim past 5k records, `day_summary()` / `digest_line()` / `transitions()`
  read helpers. Wired into the engine (records every transition + moment).
  9-assertion test file, all green. *(shipped 2026-06-22)*
- **6b. Session resurrection** — on crash/restart, restore the last presence
  state and in-progress context so it feels continuous, not rebooted.
- **6c. Cross-device handoff** — via the existing `core/sync.py` + mobile bridge,
  carry "what you were doing" to the phone companion (ROADMAP 5g).
- **6d. Long-term rhythm model** — weekly/seasonal patterns (you code mornings,
  meet afternoons) feed gentler, better-timed proactivity.
- **6e. The "eternal" mode** — opt-in: AERIS stays resident in the tray across
  reboots (run-at-login), keeping the journal and presence state warm so the
  assistant genuinely persists. Always with a single, obvious kill switch.

---

## Sequencing

```
Phase 0 (foundation ✅) ─▶ Phase 1 (wire into GUI/voice)
                        ├▶ Phase 3 (gestures, parallel — engine already exists)
                        └▶ Phase 5 (assistant functions, parallel — skills exist)
Phase 2 (proactive)  ─▶ needs Phase 1 + a few days of journal (6a)
Phase 4 (voice)      ─▶ independent; gated on opt-in + mic UX
Phase 6 (continuity) ─▶ after journal (6a) lands
```

Load-bearing first: **1a/1b** (make presence visible+audible) and **6a** (the
journal). Almost everything proactive depends on having real history to learn from.

## Acceptance metric per phase

| Phase | "It's working when…"                                                       |
|-------|----------------------------------------------------------------------------|
| 0     | Engine runs for an hour, fires correct moments, zero false nags. ✅          |
| 1     | Orb visibly tracks AWAY/FOCUS; greeting is spoken once per morning.         |
| 2     | It offers (not forces) one accurate routine after ~2 weeks of use.         |
| 3     | Two new gestures usable one-handed, with a cancel window; no misfires away. |
| 4     | Wake word + biometric gate work; privileged command refused for a stranger. |
| 5     | Morning briefing + a real reminder fire end-to-end without docs.           |
| 6     | Restart preserves presence state; daily digest reflects the real journal.  |

## Guardrails (apply to every phase)

- **Privacy first** — camera/mic/journal all honour `core/privacy_mode.is_on()`;
  one switch silences everything proactive.
- **Quiet hours** — no spoken proactivity 23:00–07:00 (configurable).
- **Confirm the irreversible** — destructive skills stay behind the
  orchestrator's confirm + voice gate.
- **Everything off-switchable** — presence, voice, gestures, eternal-mode each
  have an independent, discoverable toggle.
