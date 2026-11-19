# A.E.R.I.S — working notes for Claude

Hinglish-native desktop assistant for Windows. PyQt5 GUI, local inference
(sentence-transformers + spaCy + an optional Ollama fallback), no cloud brain.
Python packages: `core/` (engine), `skills/` (user-facing actions), `ui/`
(desktop surfaces), `utils/`, `tests/`.

## Interpreter

Use **`py -3.10`** (`C:\Users\Shivang\AppData\Local\Programs\Python\Python310`).
Anaconda is no longer installed on this machine, so `python` on PATH resolves
to the Windows Store stub and fails.

*Corrected 2026-09-01.* This section previously said the opposite — use
Anaconda, never `py -3.10`, whose wheels were ABI-broken against numpy 2.x
(`numpy.dtype size changed`). Both halves are now out of date: Anaconda is
gone, and the py3.10 stack imports cleanly. Measured today, in this
interpreter:

    numpy 0.18s · torch 3.57s · sentence_transformers 8.33s · sklearn · spacy 3.09s

`python check_split.py` re-checks this any time — its "brain ML stack" line
imports the whole stack in a subprocess, which is exactly the check that would
catch the ABI break coming back (§6.35).

## Entry points

| Command | What it starts |
| --- | --- |
| `python run_aeris_v6.py` | `ui/aeris_v6` — the newest GUI |
| `python run_gui.py` | `ui/jarvis_v31` — the older GUI, still fully supported |
| `AERIS.bat` / `AERIS.bat debug` | `run_gui.py` via `pythonw` (no console) / with console. The **fast profile**: lite boot + background warm-up, brain models kept 30 min between uses |
| `python main.py` | terminal: voice. `--text`, `--wake`, `--verbose`, `--vault` |
| `python run_split.py` | text driver with the brain in a supervised child process; this process imports no ML |
| `python run_bridge.py` | phone bridge alone — no torch, no encoder |
| `python run_gesture_tester.py` | gesture/camera harness (in-process) |
| `python check_split.py` | **start here for split mode.** Preflight: checks the libraries, the service bus, and each service child, then names which `AERIS_SPLIT_*` flags are safe to enable. Touches no camera or mic, so it is safe to run any time. Exit 0 = nothing failed (§6.35) |
| `python run_vision_split.py` | gestures with the camera + MediaPipe in a CHILD process; this process imports no cv2/mediapipe. The live check before the vision cutover (§6.23) |
| `python run_voice_split.py` | mic + speaker in a CHILD process; this process imports no PyAudio/vosk/pygame/PyQt5. Speaks, shows the mic stayed shut, then listens. `--say-only` proves speech needs no mic. The live check before the voice cutover (§6.25) |
| `python tools/validate_command_routing.py` | routing accuracy on the 528 curated phrasings in `data/command_examples.json`, measured through `JarvisMainEngine.route()`. Loads the engine; changes nothing |
| `python tools/analyze_corpus_overlap.py` | which intents claim near-identical training patterns — evidence for a corpus trim. Changes nothing (§6.40) |

Note the two GUI generations coexist, and `AERIS.bat` still points at the
older `run_gui.py`. Ask before changing which surface a launcher opens.

## Boot order is load-bearing

Windows-specific, and easy to break by moving imports:

- **torch's DLLs must load before `PyQt5`.** Otherwise torch's DLL init fails
  with `WinError 1114` and the brain never starts — the window opens and
  refuses every command. The package itself can still be imported later, on
  the BrainWorker thread; only the *native libraries* need to win the race.
  - `run_gui.py` calls `core.torch_dll_preload.preload_torch_dlls()` before
    importing PyQt5 (~0.2 s, versus ~1.6 s for a full `import torch`), so the
    instant path keeps its fast first paint. **This must stay above the PyQt5
    import** — running the same preload after `QApplication` exists fails with
    1114 too, so there is no working place for it inside `BrainWorker`.
  - `run_aeris_v6.py` instead does a plain `import torch` before PyQt5. Also
    correct, just heavier: it carries torch in the GUI process from boot.
  - `AERIS_SPLIT_BRAIN=1` sidesteps the whole issue — the GUI imports no torch
    and the child loads it on its own main thread with no Qt present.
  - Verified 2026-08-31 on py3.10 + torch 2.10.0+cpu, where the *unpatched*
    instant path genuinely failed. Do not "simplify" the preload away because
    a boot looks fine: check which entry point and which flags you tested.
    See docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md §6.15.
- `KMP_DUPLICATE_LIB_OK=TRUE` and the BLAS thread vars are pinned to 1 before
  the engine imports, to avoid heap corruption (`0xc0000374`) when audio and
  encode threads run concurrently. `AERIS_MATH_THREADS` overrides.
- The GUI entry points pre-import `sentence_transformers`, `sklearn`, `spacy`
  and `transformers` on the main thread, behind a splash, so `BrainWorker`
  pays no import cost. Boot is already 5–10 s; anything that lengthens it is
  visible to the user. Prefer staged init with progress signals over one big
  constructor.
- **Do not move torch/sentence-transformers back to module level** in
  `core/intent_classifier.py` or `core/intent_model.py`. They are deliberately
  function-local so `import core.brain` costs 0.2 s instead of ~15 s
  (docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md §6.7). The single-thread
  torch pin those imports used to guarantee now lives in
  `core/torch_setup.pin_torch_threads()`, called from every lazy load site —
  call it from any new one.

## How a turn flows

`process_text` → `_process_text_inner`, which walks `_TURN_STEPS` in order.
Each `_step_*` method returns a reply (the turn ends) or `_PASS` — not `None`,
which is a legitimate reply. Pending state resolves first (anticipation offer,
slot-fill, disambiguation, destructive confirm, proactive offer), then things
to *remember* rather than do (memory, goals, preferences, routines, temporal
recall), then `_run_commands` splits the utterance and runs `_process_segment`
per command. `tests/test_turn_steps.py` pins the order; a new pre-routing
behaviour is one step method plus one tuple entry.

Before splitting, `_run_commands` offers the text to **`core/chain_planner.py`**
(`_try_chain`). It claims only two shapes, with no LLM call: data flow, where a
command's reply feeds a sink (note / file / clipboard / phone / translate /
summarize — "weather batao aur phone pe bhejo", or "isko note kar lo" on the
last answer), and numeric conditions ("agar battery 30 se kam hai to …
warna …"). Every command step still goes through `_process_segment`, so routing
guards and the confirm gate apply per step; a step that asks the user something
pauses the chain. Everything else returns `None` and flows on unchanged —
plain "X aur Y" to the splitter, open-ended goals to the LLM agent. Pure tests:
`tests/test_chain_planner.py`; engine tests: `tests/test_chain_engine.py` (slow).

Inside a segment, **`route(text)`** picks the intent with no side effects:
repair alias → exact pattern → subspan scan (up to 6 trimmed variants: cheap tiers per span via
`brain.predict_fast` — LRU → exact → arithmetic → `_BUILTIN_ANCHORS` — stopping
at the first certain span, then every miss in ONE batched k-NN/neural pass via
`brain.predict_many`; keep new classifier work batch-capable) → app gazetteer
(`entity_extractor.intent_hint`) → `_guard_dangerous_route`. The validator
measures `route()` itself, so its number is what a real turn gets
(2026-09-15: 95.5% accepted, 77.3% strict).

Fixing a mis-route without a retrain (retraining is the user's to run):
- a clear signal for one intent → an anchor in `core/brain._BUILTIN_ANCHORS`
  (or, without code, `data/routing_anchors.json`)
- a request that landed in the wrong *family* → a rule in
  `_guard_dangerous_route`, which must stay two-sided: rescue the broken route,
  leave correct neighbours alone

Add the phrase **and its over-catch traps** to `tests/test_routing_anchors.py` or
`tests/test_dangerous_route_guard.py`. The gazetteer runs after the anchors and
overrides them when the text names an app ("music chalu karo" → open_app).
Anything that can shut down, delete or wipe belongs in
`confirm_gate.DESTRUCTIVE_SKILLS` before a routing rule points at it.

## What leaves the machine

**`docs/PRIVACY.md`** lists every network-capable module, what it sends, and
how to avoid it. The headline worth knowing before reading anything else here:
the *brain* is local (routing, memory, embedded Qwen, Ollama on 127.0.0.1), but
**speech recognition sends audio to Google and spoken replies send text to
Microsoft** on every voice turn. Those are the tested Hinglish picks, not
accidents. Regenerate with `python gen_privacy_doc.py`;
`tests/test_egress_registry.py` fails if a module gains network access without
an entry (§6.38).

## Environment flags

**`docs/FLAGS.md` is the complete list — all 24, generated from the source.**
Regenerate with `python gen_flags_doc.py`; `tests/test_flag_registry.py` fails
if a flag is added without a description, if a description outlives its flag,
or if the committed doc is stale (§6.36). The table below covers the load-free
subset in more depth.

## Load-free flags

Two env switches, both off by default, both safe to combine — and best
combined:

| Flag | Effect |
| --- | --- |
| `AERIS_SPLIT_BRAIN=1` | brain runs in a supervised child process; the GUI imports no ML (fixes the 0xC0000374 crash class) |
| `AERIS_LITE_ML=1` | boot loads **no** model weights; the tiered router pulls the encoder / neural head / spaCy / chat gate in on the first utterance that needs them |
| `AERIS_PREWARM` | **on by default, acts only with lite boot**: right after boot the engine loads those same models on a background thread (`start_background_warmup` → `brain.warm_up`), so boot stays fast and the first heavy command doesn't stall. A command arriving mid-warm waits on the single in-flight load; cheap-tier commands never wait. `0` restores fully lazy lite boot (`AERIS_LIGHT.bat` sets it). `tests/conftest.py` sets `0` for the suite |
| `AERIS_IDLE_UNLOAD_S=<n>` | idle window before model weights are dropped (default 300, `0` = never). The ticker starts from `setup_iter`, so it covers the in-process engine *and* the split child, and sweeps the encoder, the neural head, spaCy and the local LLM |
| `AERIS_LLM_IDLE_UNLOAD_S=<n>` | idle window for the local Qwen gguf alone — it is ~1 GB and by far the most expensive thing to reload, so you may want it held longer than the encoder. Falls back to `AERIS_IDLE_UNLOAD_S`, then 300 |
| `AERIS_SPLIT_VOICE=1` | `make_voice_engine()` returns a `RemoteVoiceEngine` — mic and speaker run in a child process behind the same six Qt signals `VoiceWorker` already consumes, so both GUIs are unchanged apart from one line each. Falls back to in-process if the split breaks. **Run `python run_voice_split.py` first.** See §6.31 |
| `AERIS_SPLIT_VISION=1` | `get_gesture_engine()` returns a `RemoteGestureEngine` — camera + MediaPipe run in a child process, and the GUI holds none of it. Presents the same seven-name surface every caller outside `core/` uses, so nothing else changes; a broken split falls back to the in-process engine. **Run `python run_vision_split.py` first.** See §6.30 |
| `AERIS_VOICE_STREAMING=1` | voice service only: live partial transcripts while you speak (`event:partial`, display-only — never delivered as a command, and suppressed while SLEEPING). **Off by default for a models reason, not a plumbing one**: `STT.listen_streaming` is Vosk end-to-end, so its *final* transcript never reaches Google en-IN — you trade Hinglish recognition quality for latency. That's your call about a tuned stack, so it isn't a default. See §6.29 |
| `AERIS_REPAIR_MEMORY=1` | in-session self-correction: when a phrasing misses and your immediate rephrase works, remember phrase→intent so the failed phrasing works from then on (`core/repair_memory.py`, stored in `data/repair_memory.json`). Sits at tier 0 of the router — one dict lookup, no encode. **Off by default** because it changes which skill fires and persists to disk; precision-first, and an alias that later misses deletes itself. See §6.24 |
| `AERIS_BRAIN_HIBERNATE_S=<n>` | **split mode only.** Retire the whole brain *child process* after N seconds with no utterance (default `0` = off). The conversation (`DialogueState`, `ConversationHistory`, the parked "haan" offer) is snapshotted out before the stop and restored into the replacement, so follow-ups still resolve across a sleep. Takes the resting footprint from ~478 MB to the GUI's own ~20 MB; the cost is ~2 s on the next utterance (lite boot) **and silence while asleep** — the proactive ticker lives in the child, so a hibernated AERIS never speaks first. See §6.22 |
| `AERIS_DISABLE_BRIDGE=1` | never start the phone bridge. `setup_iter` otherwise auto-starts it whenever a pairing exists, which opens a live Firestore listener plus presence/clipboard threads. `tests/conftest.py` sets this for the whole suite — leave it that way |
| `AERIS_CAMERA_IDLE_S=<n>` | release the webcam after N seconds with no hand in frame. **Off by default (`0`)** — unlike the other flags this trades a capability for resources: gestures stop working until switched back on |
| `AERIS_PYTHON=<path>` | interpreter override for the `.bat` launchers (see `_python.bat`) |

`AERIS_LIGHT.bat` sets the split + lite pair for you.

Measured together: brain ready in **1.9 s**, **~126 MB** across both processes,
against ~20 s / ~2.3 GB for the default single-process eager boot. The cost is
moved, not removed — the first utterance that misses every cheap tier pays the
encoder load. See §6.7 of the load-free doc.

## Skills

Skills register themselves with the `@skill(...)` decorator from
`core/skill_registry.py` into a global `REGISTRY` — ~162 call sites. Adding a
skill means writing the decorated handler; no central list to edit.

## Tests

`pytest` (config in `pytest.ini`, 192 test files under `tests/`).

```
pytest                  # everything
pytest -m "not slow"    # fast lane: pure-logic tests, seconds
pytest -m slow          # only the heavy brain/model tests
```

`tests/conftest.py` auto-tags anything that loads the encoder, neural model, or
full engine as `slow`. Tests use the eager (non-lazy) `JarvisMainEngine` path —
keep it working when refactoring init.

`tests/test_service_contracts.py` asserts the **real** classes still expose
what the process-isolation services call (`TTS.stop`, `GestureEngine
.add_listener`, `GoalStore.open_goals`, the `ServiceProxy` surface, …).
Interface-only — no instantiation, no devices. It exists because the services
inject their dependencies, so a fake with a method the real class lacks makes
the suite green while the feature does nothing (that shipped once — §6.25/§6.27).
**If you add a call on an injected device, pin it there.**

## Searching this repo

- `_archive_20260704/` is dead code kept for reference — three retired GUI
  generations and an old marketing site. Exclude it from searches; it holds
  duplicate `main`/`start`/`update` symbols that pollute results.
- `mobile/` (Kotlin), `aeris_remote/` (Dart), and `aeris_mobile/` (Dart) are
  companion apps, not part of the Python app. See below for which is which.
- The codebase-memory knowledge graph is **already indexed as project `aeris`**.
  Query it with `search_graph` / `trace_path` / `query_graph` instead of
  re-indexing. Qualified names are `aeris.<package>.<module>.<symbol>`.
  Cypher there needs explicit node labels — `(a:Function)`, not `(a)`, which
  silently returns zero rows.

## Companion apps

Three of them, with genuinely different jobs — check which one a change belongs
in before editing:

| Folder | Stack | What it is |
| --- | --- | --- |
| `aeris_remote/` | Flutter | The mature companion: pairing, LAN + Firebase bridge, wake word, WebRTC screen mirror, file transfer, on-device skills |
| `aeris_mobile/` | Flutter | Newer, started 2026-08-08. A tiered assistant: on-device skills first, then laptop, then cloud, with the answering tier shown in the UI |
| `aeris_assistant/` | Flutter + Kotlin | Newest, started 2026-11-16. Assistant-first app with a decluttered sci-fi HUD. v0.1 built (voice loop, Hinglish router, approvals, log/memory/protocols/settings); wake word next. Design rules in `aeris_assistant/docs/DESIGN.md`, plan in `docs/BUILD_GUIDE.md` |
| `mobile/android/` | Kotlin | Native app (Room DAOs for tasks/expenses) |
| `mobile/aeris_expense/` | Flutter | Standalone expense tracker |

`aeris_mobile/lib/transport/crypto.dart` is deliberately byte-compatible with
`core/cloud_bridge.py` and with `aeris_remote/lib/laptop/crypto.dart` — AES-256-GCM,
12-byte nonce, `{"n": b64(nonce), "ct": b64(ciphertext||tag)}`. If you change
the envelope on either side, change all three or pairing breaks silently.

Run its checks with `flutter analyze` and `flutter test` from `aeris_mobile/`.

**Windows Developer Mode is required to build any of the Flutter apps for
Android.** Flutter creates plugin symlinks under `android/app/.plugin_symlinks`,
which Windows refuses without it — `flutter pub get` prints "Building with
plugins requires symlink support" and the APK build then fails. Enable it once
via `start ms-settings:developers`. Web builds and `flutter test` work without it.

## Repo hygiene

**The GitHub repo (`shivangrastogi/S.Y.N.E.X`) is public.** `.gitignore` has a
PERSONAL DATA block for what AERIS learns about the user — face embeddings,
memory, notes, journals, the ledger, the expense workbook, snippets — plus
runtime state, logs and build output. The files exist locally and are created
on first use, so a fresh clone runs without them. Before committing anything
new under `data/`, decide which kind it is: shipped defaults (intents, corpora,
models, `settings.json`, `routines.json`, `macros.json`, `modes.json`) stay
tracked; anything that records the user goes in that block.
`data/user_memory.json` and one crash log are still in history pushed before
2026-09-15.

Dev-only diagnostics live in `tools/`. The root keeps the entry points and the
doc generators (`gen_*.py`), which tests and `skills/help_catalog.py` reference
by path.
