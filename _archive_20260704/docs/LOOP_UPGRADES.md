# AERIS — Autonomous Upgrade Loop

A running log of self-paced upgrade iterations. Each iteration ships a
**small, additive, fully-tested** improvement drawn from the sanctioned
"Improvements & Next Steps" list in `README.md §13` and `ROADMAP.md`, then
records what changed here so the next pass builds coherently instead of
sprawling.

## Operating principles for the loop

1. **Additive first.** Prefer new modules + new skills over rewrites of the
   338-skill / 78-core-module base. One clean insertion point beats ten edits.
2. **Always testable headlessly.** No iteration depends on a mic, camera,
   speaker, or GPU to verify. Pure-logic helpers + fixtures.
3. **Every iteration ends green.** New tests pass and `test_skill_registry`
   still discovers everything.
4. **Document the seam.** Note the data/contract each iteration exposes so the
   next can consume it (e.g. structured events → digest → UI chip → diff skill).

## Roadmap this loop is working through (from README §13 / ROADMAP)

- [x] **I1 — Dispatch telemetry + Activity Digest.** Structured
  `skill_dispatch` events + "what did you do today?" skill. *(done)*
- [x] **I2 — "Which skill fired" chip data + recent-activity API.** Surface
  the per-reply skill/latency/confidence (README §13.4). *(done)*
- [x] **I3 — TTS phrase cache.** Wire `data/audio_cache/` so common short
  phrases ("Done.", "Yes sir.") replay from disk (README §13.5). *(done)*
- [x] **I4 — Undo last action.** Ring buffer + undo for reversible skills
  (README §13.4). *(done)*
- [x] **I5 — "What did you change?" diff skill.** Natural-language summary of
  recent dispatch + routine-fire events over 24h (README §13.6). *(done)*
- [x] **I6 — Ollama reachability check** in first-run + a `/health` field.
  *(done — structured probe, /health field, status skill)*
- [x] **I7 — TTS fallback-chain tests + main_engine smoke test** (README §13.3).
  *(done)*

### Phase 2 — restructure + new functionality (original §13 list exhausted)

- [x] **I8 — `core/metrics.py` consolidation + `/metrics` enrichment + health
  disconnect-bug fix.** Unify `activity_digest` + `change_log` + `telemetry`
  behind one façade; `/metrics` now carries an `activity` section; health
  handler swallows client-disconnect errors (observed live during a run).
  *(done)*
- [x] **I9 — Reversible memory-forget.** "forget my X" now removes the fact and
  registers an undo; "undo" restores it. (Volume/brightness deferred — they need
  hardware mocks to test; memory-forget is pure data.) *(done)*
- [x] **I10 — Scheduled-routines introspection skill** ("what fires at 9am?",
  README §13.6) reading `data/routines.json`. *(done)*
- [x] **I11 — Robust voice handling (USER-REQUESTED).** Noise-gate + PROCESSING
  watchdog so a half-heard capture never flips to PROCESSING and a slow/hung
  brain call can never strand the UI — it snaps back to LISTENING. *(done; deeper
  VAD-streaming upgrade still open — see I12.)*
- [~] **I12 — True VAD streaming voice.** Endpointing core + energy VAD shipped
  & tested; `stt.listen_streaming` refactored onto it. Remaining: wire a
  `_stream_loop` + `partial` signal into `voice_engine` and a live-partial GUI
  caption (needs mic to verify) → I12b.
- [x] **I13 — Unified "how are you doing?" status skill.** One spoken line over
  the metrics façade + LLM health + memory pressure. *(done)*
- [x] **I14 — Consolidation pass.** Full-suite verification after I1–I13: 1138
  tests collect cleanly, 147 new+touched pass, 13 pipeline pass. No regressions.
  *(done)*
- [x] **I15 — Test-infra: `slow` marker + fast lane.** `conftest` auto-tags the
  25 brain/model modules `slow`; `pytest.ini` registers the marker.
  `pytest -m "not slow"` → 271 passed in ~24 s (vs the full run getting killed).
  *(done)*
- [x] **I16 — Reversible + testable volume control.** Mockable `get_volume`/
  `set_volume` seam; `volume_set`/`up`/`down` capture the prior level and
  register an undo (the deferred I9 hardware-undo, now headlessly testable).
  *(done)*
- [x] **I17 — Reversible brightness control.** Same seam+undo pattern on
  `brightness_control.py` (seam already existed); `brightness_set`/`up`/`down`
  now restore the prior level on "undo". *(done)*
- [x] **I18 — "What can I undo?" history skill.** `ActionHistory.labels()` +
  `undo_history` skill lists pending reversible actions, newest first. *(done)*

---

## I1 — Dispatch telemetry + Activity Digest  ✅

**Date:** 2026-06-26

**What shipped**

- `core/main_engine.py` — emits one structured `skill_dispatch` JSON event per
  executed/slot-filled intent at the single dispatch seam (`_process_segment`),
  capturing `intent`, `confidence`, `action`, `latency_ms`, `sentiment`.
  Best-effort; a logging hiccup never breaks the response path.
- `core/activity_digest.py` — pure helpers (`read_events`, `digest`,
  `summarize`) that read those events back from the rotating log + ring buffer,
  window them by time, de-dup, and roll up counts / top skills / latency p50/p95.
- `skills/activity_digest_skill.py` — voice skill `activity_digest`
  ("what did you do today", "aaj kya kiya", "summarise the last hour") with
  natural-language window parsing (minutes/hours/days/week, English + Hinglish).
- `tests/test_activity_digest.py` — 9 tests: parsing, windowing, dedup, rollup
  math, NL window parsing, skill registration. All green.

**Seam exposed for next iterations:** the `skill_dispatch` event stream is now
the canonical source of "what AERIS has been doing" — I2 (UI chip), I5 (diff
skill), and any `/metrics` consumer all read from `core/activity_digest`.

---

## I2 — "Which skill fired" chip data + recent-activity API  ✅

**Date:** 2026-06-26

**What shipped**

- `core/main_engine.py` — `JarvisMainEngine.last_dispatch` (a dict) is now set
  synchronously at the dispatch seam, mirroring the `skill_dispatch` event, so
  a GUI reading it right after `process_text()` always sees this turn's
  metadata (`intent`, `confidence`, `action`, `latency_ms`, `sentiment`).
- `core/activity_digest.py` — `last_dispatch(within_h=…)` recovers the newest
  dispatch from the durable event stream (for consumers without a live engine
  ref); `format_chip(ev)` renders `weather · 0.91 · 12 ms` (empty string when
  there's nothing to show, so the GUI just hides the chip).
- `tests/test_activity_digest.py` — +5 tests (chip formatting variants,
  newest-wins `last_dispatch`, empty case).
- `tests/test_pipeline.py::test_last_dispatch_side_channel` — engine-level test
  asserting a routed turn populates `last_dispatch` + renders a chip. Green
  (52 s, brain load).

**GUI consumer hook (left for the UI pass):** the glass chat panel only needs
to call `format_chip(engine.last_dispatch)` after each reply and render the
string as a small dim caption under the assistant bubble. Data layer is done
and tested; rendering is a one-liner whenever the GUI is touched next.

---

## I3 — TTS phrase cache  ✅

**Date:** 2026-06-26

**What shipped**

- `core/tts_cache.py` — content-addressed cache keyed by `(text, voice, rate,
  pitch)`: `cache_key`, `is_cacheable` (≤ 80 chars), `lookup` (mtime-bump for
  LRU), `store` (temp-then-`os.replace`, best-effort), `prune` (LRU by mtime,
  cap 250, only ever touches `<32hex>.mp3` so the live `speech.mp3` is safe).
- `core/tts.py` — `_try_edge_tts` now resolves the live voice once, checks the
  cache before any network synth (replays the clip on a hit), and stores +
  prunes after synthesising a cacheable phrase. Extracted `_play_file()` so the
  cache-hit and fresh-synth paths share one playback routine. `_generate_audio`
  takes the resolved voice so the cache key and the audio always agree.
- `tests/test_tts_cache.py` — 8 headless tests (key stability/sensitivity,
  normalisation, cacheability gate, store↔lookup roundtrip, miss cases, LRU
  prune sparing non-cache files). All green; runs in the normal suite (no audio).

**Effect:** repeated short acks ("Done.", "Yes sir.", "Theek hai.") now skip the
edge-tts round-trip after first synthesis — lower latency + fewer network calls.
Long/unique replies are untouched (gate + reusable temp file as before).

---

## I4 — Undo last action  ✅

**Date:** 2026-06-26

**What shipped**

- `core/action_history.py` — `ActionHistory`, a thread-safe LIFO ring buffer
  (cap 20) of `UndoableAction(label, undo_fn, skill, ts)`. `record()`,
  `undo_last(within_s=…)` (honours a 180 s default window for voice; `None`
  = force), `peek_last()`, `clear()`, plus module-singleton convenience fns.
  Opt-in: only skills that register an undo participate; irreversible actions
  never pretend to be undoable. Failing undo callables are caught, not fatal.
- `skills/undo_skill.py` — voice skill `undo_last` ("undo", "wait no",
  "wapas karo", "force undo"). "force" ignores the time window.
- `skills/clipboard.py` — `clipboard_copy` now captures the previous clipboard
  and registers an undo that restores it (first real consumer).
- `tests/test_action_history.py` — 9 tests: LIFO order, empty history, window
  blocking + force, failing-undo handling, ring eviction, non-callable guard,
  skill registration, end-to-end clipboard restore with a fake pyperclip.

**Seam exposed:** any skill can now make itself reversible with
`core.action_history.record(label, undo_fn)`. Next reversible candidates:
volume/brightness (restore prior value), memory-forget (restore the fact),
theme change. The GUI can also surface a 5 s undo toast via
`peek_last()` + `undo_last(within_s=5)`.

---

## I5 — "What did you change?" diff skill  ✅

**Date:** 2026-06-26

**What shipped**

- `core/change_log.py` — narrates the *whole* event stream (not just skills):
  `changes(window_h)` buckets every event by kind (skill_dispatch /
  routine_fire / presence_moment / unknown kinds fall through), `summarize_changes`
  renders a Hinglish paragraph, `changes_since_boot()` windows from
  `data/last_boot.json`. Built on `activity_digest.read_events(event_name=None)`.
- `skills/change_log_skill.py` — voice skill `change_log` ("what did you
  change", "what's new", "kya naya hua", "since boot"), distinct trigger
  phrases from `activity_digest` so both summary skills coexist; shares the
  same NL window parser.
- `tests/test_change_log.py` — 6 tests: kind bucketing, each-category narrative,
  unknown-kind fall-through, empty window, since-boot path, skill registration
  + coexistence with `activity_digest`. All green (43 in the fast subset).

**Note:** new event emitters now surface in the diff for free (the unknown-kind
fall-through), so future iterations that add `event(...)` calls become
self-documenting in "what did you change".

---

## I6 — Ollama reachability check  ✅

**Date:** 2026-06-26

**What shipped**

- `core/llm_chat.py` — new `LLMChat.probe()` returns a structured dict that
  distinguishes **unreachable** (server down) from **no_model** (server up,
  model not pulled) from **ok**, each with a one-line fix hint (`ollama serve`
  / `ollama pull <model>`). `is_available()` is now a thin wrapper over it.
  Added `probe_cached(ttl=15s)` so repeated callers don't each fire a 2 s
  network round-trip.
- `core/health_server.py` — `/health` now carries an `llm_ollama` field
  (`status` / `reachable` / `model` / `model_present`), cached, best-effort.
- `skills/llm_status_skill.py` — voice skill `llm_status` ("is ollama running",
  "is chat working", "kya ollama chal raha hai") that reports status + the exact
  fix command, and emits an `llm_probe` event (visible in the I5 change-log).
- `tests/test_llm_health.py` — 7 tests: all three probe branches, `is_available`
  parity, cache behaviour, `/health` field, status skill. All green (63 in the
  fast subset).

**First-run wizard hook (left for the UI pass):** `ui/first_run_wizard.py` can
call `probe_cached()` and show a green/amber/red row + the fix hint, with a
"skip — I'll set it up later" branch, exactly as README §13.4 asks. Logic is
done and tested; the wizard just renders the dict.

---

## I7 — TTS fallback-chain tests + main_engine smoke test  ✅

**Date:** 2026-06-26

**What shipped**

- `tests/test_tts_fallback.py` — 7 tests driving `TTS.speak()` with each tier
  (`_try_edge_tts` → `_try_pyttsx3` → `_try_sapi5`) mocked to fail/succeed in
  sequence: short-circuit on first win, fall-through to each next tier,
  all-fail-no-exception, empty-text skips all, and the `_EDGE_OK`/`_PYTTSX3_OK`
  module gates skipping disabled tiers. No speaker/edge_tts/COM touched.
- `tests/test_pipeline.py` — +2 orchestration smoke tests: `process_text("hello")`
  returns a non-empty reply and `_speak` forwards it verbatim to a fake TTS
  (and ignores empty strings) — the minimal brain→response→TTS wiring check
  README §13.3 asked for.

**Milestone:** the original README §13 "Improvements & Next Steps" list (the
correctness, coverage, UX, and perf items I1–I7 targeted) is now worked through.
The loop pivots to **Phase 2 — restructure + new functionality** (I8+ above):
consolidate the three telemetry modules behind one façade, extend the undo
stack to more skills, and add routines introspection.

---

## I8 — Metrics façade + /metrics + health disconnect fix  ✅

**Date:** 2026-06-26

- `core/metrics.py` — one front door over `activity_digest` + `change_log` +
  legacy `telemetry`: `snapshot(window_h)` returns digest + changes +
  last_dispatch + summary + narrative + legacy totals, each section best-effort
  isolated. Thin re-exports (`digest`/`summarize`/`changes`/`last_dispatch`/
  `format_chip`) so callers import one module.
- `core/health_server.py` — `/metrics` now carries an `activity` section; **and
  the disconnect bug observed live during a run is fixed**: a client that closes
  mid-response (`ConnectionAbortedError`/`ConnectionResetError`/`BrokenPipeError`)
  is debug-logged once, not dumped as a double traceback, and no error response
  is forced into the dead socket.
- `tests/test_metrics_facade.py` — 5 tests (façade unify, section isolation,
  re-exports, handler swallows disconnect, real error still reported).

## I11 — Robust voice handling (noise-gate + PROCESSING watchdog)  ✅

**Date:** 2026-06-26 · **User-requested** ("mic na sun paye to processing me
chala jata tha; chahiye continuous listening jaise ChatGPT").

**Diagnosis.** The mic loop (`core/voice_engine._loop`) is *already* continuous
+ always-on. The strand was the UI state machine in
`ui/jarvis_v31/main_window.py`: (1) no watchdog — once in PROCESSING the only
exits were `responded`/`error`, so a slow/hung `process_text` (LLM fallback,
agentic loop, wedged skill) stuck the UI forever; (2) a garbled non-empty
capture still flipped to PROCESSING; (3) captures during PROCESSING were dropped.

**What shipped**

- `core/voice_gate.py` — pure policy: `is_meaningful_capture(text)` (rejects
  empty / sub-2-char / all-filler blips in English + Hinglish) and
  `processing_timeout_s(text, llm_possible=…)` (bounded 3–30 s watchdog budget).
- `ui/jarvis_v31/main_window.py` —
  * `_on_voice_captured` drops noise via the gate → stays LISTENING, mic keeps
    streaming (the core "stuck on a half-heard word" fix).
  * a single-shot `QTimer` watchdog armed on PROCESSING (`_on_user_send`),
    disarmed on `responded`/`error`; on timeout `_on_processing_timeout` snaps
    back to LISTENING, says "thoda time lag gaya, phir se boliye", and replays
    any phrase captured while wedged.
- `tests/test_voice_gate.py` — 22 tests (filter pass/reject matrix, min-chars,
  watchdog budget scaling + bounds).

**Still open → I12:** the *deeper* ChatGPT-parity upgrade is real streaming —
swap the per-utterance blocking `recognizer.listen(timeout, phrase_time_limit)`
+ separate Google round-trip for continuous **VAD** with **Vosk partial
transcripts** (`stt.listen_streaming` is already written). That gives live
partials, instant endpointing, and barge-in. I11 makes today's path robust;
I12 makes it feel like ChatGPT.

## I12 — VAD streaming endpointing core  ✅ (foundation)

**Date:** 2026-06-27

**What shipped**

- `core/vad_stream.py` — the pure, testable heart of ChatGPT-style "cut as soon
  as you stop talking": `is_speech(chunk)` (PCM16 RMS energy gate vs room tone)
  and `Endpointer`, a state machine fed the recogniser's latest partial each
  chunk. A *changed* partial resets the silence counter (still talking); an
  unchanged partial accrues trailing silence and endpoints after
  `max_silence_chunks`; a non-empty Vosk hard-final endpoints immediately; an
  empty hard-final is a no-op that preserves the running partial.
- `core/stt.py` — `listen_streaming` now drives an `Endpointer` instead of an
  inline silence counter, so the live partial path and the endpointing policy
  are unit-tested and shared.
- `tests/test_vad_stream.py` — 9 tests (energy gate silence/voice/threshold;
  growing partial resets silence; endpoint after trailing silence; hard-final
  immediate; empty-final no-op; no endpoint before speech; reset; configurable
  silence window).

**Remaining → I12b (needs mic to verify):** add a `_stream_loop` to
`core/voice_engine.py` that opens the Vosk stream, drives an `Endpointer`, emits
a new `partial(str)` signal per chunk and `captured(str)` on endpoint — then a
live "…listening, you said: <partial>" caption in the chat panel. The blocking
`recognizer.listen()` path stays as the fallback when Vosk isn't loaded. The
endpointing logic it needs is now done + tested; I12b is the mic/GUI plumbing.

## I9 — Reversible memory-forget  ✅

**Date:** 2026-06-27

**What shipped**

- `core/memory.py` — `UserMemory.forget(key)` (pops + returns the removed entry
  so it can be restored), `restore_fact(key, entry)` (the undo), and
  `detect_and_forget(text)` — NL "forget my X" / "mera X bhool jao" (reuses the
  `_KEY_ALIASES` Hindi→canonical map), which removes the fact AND registers an
  undo via the I4 `action_history` seam.
- `core/main_engine.py` — new Step 2c calls `detect_and_forget` right after the
  memory-SET step, so "forget my name" is handled before intent classification
  (same pattern as `detect_and_store`).
- `tests/test_memory_forget.py` — 9 tests: forget/restore roundtrip, persistence
  across reload, English + Hinglish-alias detection, no-match + unknown-fact
  paths, and the full undo integration ("forget my name" → "undo" → restored).

**Effect:** accidental "forget my X" is now one "undo" away — closes the loop
with I4. Volume/brightness/theme undo deferred: they touch hardware (pycaw / WMI
/ COM) and can't be verified headlessly without mock layers; memory-forget is
pure JSON and fully tested.

## I10 — Scheduled-routines introspection skill  ✅

**Date:** 2026-06-27

**What shipped**

- `core/routines_view.py` — read-only view over `data/routines.json`:
  `load_routines` (→ `Routine` objects), `cron_hour`, `routines_at(hour)`,
  `summarize_routines(enabled_only=…)`, `summarize_at(hour)`. Reuses the
  engine's own `Trigger.summary()` so the prose matches what the scheduler logs.
- `skills/routines_view_skill.py` — voice skill `routines_view` ("show my
  routines", "what fires at 9am", "9 baje kya hota hai", "which routines are
  enabled") with hour parsing for `9am`/`7 pm`/`21:00`/`9 baje`.
- `tests/test_routines_view.py` — 10 tests (load, missing-file, cron_hour parse,
  routines_at, summarize all/enabled/empty/at-hour, NL hour parsing, skill reg).

**Effect:** the README §13.6 ask — "no dialog to see what fires at 9am Monday" —
is answered by voice. Read-only, so it can never corrupt the engine's routine
state.

---

## Loop status after I10

Original README §13 list (I1–I7) ✅ complete. Phase-2 additive features I8–I11
shipped; I9 reversible-forget + I10 routines-view round out the undo/automation
introspection surface. **Open:** I12b (live voice partials — needs mic),
volume/brightness undo (needs hardware mocks). The event-stream telemetry seam
(I1) now feeds digest, chip, change-log, and `/metrics` — a coherent spine for
any future "AERIS, how are you doing?" feature.

## I13 — Unified "how are you doing?" status skill  ✅

**Date:** 2026-06-27

**What shipped**

- `core/status_report.py` — `system_status(window_h)` composes three guarded
  sections (LLM via `probe_cached`, memory via `resource_monitor` pressure+RSS,
  activity via the I8 `metrics.digest`); `summarize_status()` renders a spoken
  Hinglish one-liner. Each section degrades to a default on failure — one dead
  subsystem never blanks the report.
- `skills/status_report_skill.py` — voice skill `status_report` ("how are you
  doing", "system status", "tum kaise ho", "are you ok") — the quick health
  check vs the detailed `diagnostics` dump.
- `tests/test_status_report.py` — 8 tests (all-healthy / LLM offline / no-model /
  critical pressure / all-unknown fallback / shape / section isolation / skill).

**Seam reuse:** this is the first consumer that fans the I8 metrics façade + I6
LLM probe + resource monitor into a single user-facing answer — the telemetry
spine paying off.

## I14 — Consolidation pass (full-suite verification)  ✅

**Date:** 2026-06-27

**Result: no regressions from I1–I13.**

- `pytest --collect-only` → **1138 tests collect cleanly** — confirms every edit
  (memory, main_engine, tts, stt, health_server, llm_chat + 12 new modules)
  imports without breaking collection anywhere in the suite.
- All **12 new test files + touched existing** (memory, skill_registry,
  tool_router) → **147 passed** (~8 s, no brain load).
- `tests/test_pipeline.py` (brain-loading, exercises the `main_engine` Step 2c
  `detect_and_forget` insertion + orchestration + `last_dispatch`) → **13 passed**.

**Finding → I15 candidate:** a plain `pytest` of the whole suite is slow enough
(brain-loading tests load a ~120 MB encoder serially) that a wall-clock-bounded
runner kills it mid-run. Worth a `@pytest.mark.slow` marker on the brain/model
tests + a `-m "not slow"` fast lane, so the 1000+ fast tests give a green signal
in seconds and the slow ones run on demand. Pure test-infra, fully safe.

## I15 — Test-infra: `slow` marker + fast lane  ✅

**Date:** 2026-06-27

**What shipped**

- `pytest.ini` (new) — registers the `slow` marker (no more "unknown mark"
  warnings) + documents the three run modes; `testpaths = tests`.
- `tests/conftest.py` — `pytest_collection_modifyitems` auto-tags the 25
  brain/model/engine-loading modules `slow` by file stem (matched via `nodeid`,
  so no module import just to read a name). Zero edits to the 25 test files.

**Run modes now:**
- `pytest` → everything (1138).
- `pytest -m "not slow"` → **fast lane: 271 passed in ~24 s** — pure-logic tests,
  a quick green signal that won't get killed on wall-clock.
- `pytest -m slow` → the 867 heavy brain/model tests, on demand.

**Why it matters:** every future loop iteration can verify with the fast lane in
seconds; the full suite is still one command when you want the brain path too.

## I16 — Reversible + testable volume control  ✅

**Date:** 2026-06-27

**What shipped**

- `skills/volume_control.py` — extracted a mockable seam: `get_volume()` (master
  scalar 0–1 or None) and `set_volume(scalar)` (clamped, True on success). All
  three skills (`volume_set`/`volume_up`/`volume_down`) now route through it and,
  via `_record_volume_undo(prev)`, register an undo that restores the prior level
  through the I4 stack. The media-key fallback (no pycaw) registers no undo since
  the absolute prior level is unknowable there.
- `tests/test_volume_undo.py` — 6 headless tests using an in-memory fake volume:
  set→undo restores, bad input no-ops, up/down + undo, clamp at 1.0, and the
  no-endpoint fallback path (no undo registered).

**Why it matters:** I9 deferred volume undo as "needs hardware mocks". Extracting
the seam *is* the mock layer — the deferred work is now done and fully tested.
Pattern reusable for brightness/theme next. Fast lane after I16: **277 passed**.

## I17 — Reversible brightness control  ✅

**Date:** 2026-06-27

**What shipped**

- `skills/brightness_control.py` — the `_get_brightness`/`_set_brightness` seam
  already existed, so I added `_record_brightness_undo(prev)` and wired
  `brightness_set` to capture the prior % and register an undo via the I4 stack.
  `brightness_up`/`down` delegate to `brightness_set`, so they inherit undo for
  free.
- `tests/test_brightness_undo.py` — 7 headless tests (set→undo, up/down+undo,
  clamp at 100, set-failure / unreadable → no undo).

**Effect:** brightness now joins volume + memory-forget as reversible. Fast lane:
**284 passed**. The undo stack (I4) now meaningfully covers the most "wait, no"
hardware actions a user hits by voice.

## I18 — "What can I undo?" history skill  ✅

**Date:** 2026-06-27

**What shipped**

- `core/action_history.py` — `ActionHistory.labels()` (+ module-level `labels()`)
  returns pending undoable-action labels, newest first.
- `skills/undo_history_skill.py` — `undo_history` skill ("what can I undo",
  "undo history", "kya undo kar sakta hoon") lists the stack (caps at 5 + "+N
  aur"), read-only companion to `undo_last`.
- `tests/test_undo_history.py` — 8 tests (labels order/empty/after-pop; skill
  empty/single/multiple/cap-at-5/registration).

**Effect:** rounds out the undo feature (I4/I16/I17) — the user can now *see*
what "undo" will revert before saying it. Fast lane: **292 passed**.

The reversible-actions surface is now coherent: do it (volume/brightness/forget)
→ "what can I undo?" → "undo". A clean, discoverable safety net.
