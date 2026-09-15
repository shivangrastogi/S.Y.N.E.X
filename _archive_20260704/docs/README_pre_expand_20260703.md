# AERIS / JARVIS v3.1 — The Complete README

> **A.E.R.I.S.** — *Adaptive Engine for Reasoning, Intelligence & Speech*
>
> A fully local, Hinglish-native, gesture- and voice-driven desktop assistant
> built from scratch in Python. Windows-only. PyQt5 GUI. ~338 voice skills.
> No cloud calls in the default path; LLM goes through your local Ollama; web
> search and a few Outlook/Spotify integrations are optional, opt-in.

**Status at a glance** (as of this build):

| Metric                 | Count |
|------------------------|------:|
| Voice skills           | **338** |
| Skill modules          | **100** |
| Core engine modules    | **78** |
| UI modules             | **24** |
| Test files             | **39** |
| Latest commit          | `202e598 feat: gesture tester, splash progress, robust camera probe, automation + skills` |
| Working-tree state     | ~26 modified + ~110 untracked (8-tier feature loop uncommitted) |
| Boot health            | Brain reaches ready, `/health` reports `brain_ready: true`, animation bus resumes |

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [How It All Fits Together](#2-how-it-all-fits-together)
3. [Quick Start](#3-quick-start)
4. [Core Engine — `core/*.py`](#4-core-engine--corepy)
5. [UI Layer — `ui/*.py` + `ui/jarvis_v31/*.py`](#5-ui-layer--uipy--uijarvis_v31py)
6. [Every Skill, Grouped — All 338 Voice Commands](#6-every-skill-grouped--all-338-voice-commands)
7. [Memory, Learning & The Brain Stack](#7-memory-learning--the-brain-stack)
8. [Gesture + Vision Subsystem](#8-gesture--vision-subsystem)
9. [Data Files & Where State Lives](#9-data-files--where-state-lives)
10. [Tests & CI Health](#10-tests--ci-health)
11. [Current Scenario — What's Working Right Now](#11-current-scenario--whats-working-right-now)
12. [Things of Appreciation](#12-things-of-appreciation)
13. [Improvements & Next Steps](#13-improvements--next-steps)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. What This Is

AERIS is a desktop assistant that runs entirely on your Windows machine and
behaves like a personal JARVIS:

- You **talk to it** in English, Hindi, or natural Hinglish (`spotify pe arijit chala do`).
- You can **gesture at it** with your hand in front of the webcam — pinch to
  click, peace sign to screenshot, custom-trained gestures bound to any skill.
- It **sees the screen** when asked (OCR), recognises **who you are** by face
  (InsightFace) and **by voice signature**, and has a **per-master permission
  matrix** so different people get different gesture allowlists.
- It **understands intent** through a hybrid brain (sentence-transformer
  embeddings + neural classifier + k-NN + exact-match fast path + LRU cache),
  and falls through to a **local LLM** (Ollama) for free-form chat — which can
  itself fire skills.
- It **learns continually** — every reply is rated implicitly via a feedback
  bandit; corrections retrain the intent classifier offline.
- It **logs structured events**, exposes a **health endpoint** at
  `127.0.0.1:8765/health`, has a **system tray** with global hotkey, a
  **graceful shutdown** flow, a **crash beacon + dump writer**, and a
  **single-instance** guard.

It is not "ChatGPT in a window." It is a hybrid symbolic-and-neural agent
where 338 hand-written skills handle the long tail of "open Chrome", "what's
my battery", "lock the screen", "screenshot this window", "add expense 500
food", "translate clipboard to Hindi", "pin this window", and the LLM only
handles the conversational glue.

---

## 2. How It All Fits Together

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │                          USER INTERFACE                              │
   │  PyQt5 main window (ui/jarvis_v31/main_window.py)                    │
   │    ├── Glass chat panel, reactor, floating dock, logs bar            │
   │    ├── Command palette (Ctrl+Shift+P)                                │
   │    ├── Settings panel · Telemetry · Permissions matrix · AR overlay  │
   │    ├── First-run wizard · Calibration wizard · HUD · Transcript pane │
   │    └── System tray · Global hotkey · Single-instance lock            │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                     INPUT PIPELINES                                  │
   │  ┌── Speech ──────────────┐ ┌── Gesture ─────────┐ ┌── Hotkey ────┐  │
   │  │ STT (Google / Whisper) │ │ MediaPipe hands +  │ │ Tray + global│  │
   │  │ wake-word, VAD         │ │ face-gate (Insight)│ │ shortcut     │  │
   │  └────────────────────────┘ └────────────────────┘ └──────────────┘  │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  BRAIN — INTENT ROUTING (core/brain.py)              │
   │  1. Exact-match fast path         (instant, O(1))                    │
   │  2. LRU cache for repeats                                            │
   │  3. Neural intent classifier      (sentence-transformer + MLP)       │
   │  4. k-NN over labelled embeddings                                    │
   │  5. Skill-registry fuzzy fallback                                    │
   │  6. LLM chat (Ollama) with tool-use over registered skills           │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  SKILL REGISTRY (core/skill_registry.py)             │
   │  100 modules, 338 skills, every one decorated with                   │
   │  @skill(name, description, patterns, required_entities=[…])          │
   │  + per-skill circuit breaker, hot-reload on file change              │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  RESPONSE PATH                                       │
   │  Response enricher (LLM-varied + cached) → TTS (edge-tts → pyttsx3   │
   │  → SAPI5 COM) → chat panel → animation bus → optional toast → log    │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  PERSISTENCE & OBSERVABILITY                         │
   │  Atomic JSON IO · settings schema versioning · semantic memory       │
   │  (.npz) · knowledge graph · vault (DPAPI) · feedback bandit (SQLite) │
   │  · structured logs · health server · crash beacon + dump · telemetry │
   └──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Quick Start

```powershell
# 1. Clone + create a venv
git clone <your-fork>
cd "new version- 3.0"
py -3.10 -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) pull a local LLM for chat-mode
ollama pull llama3.1

# 4. Launch the GUI
python run_gui.py
```

What happens on first boot:

1. Splash window appears with a progress bar — torch + sentence-transformer
   warm-load happens on the **main** thread first (a hard-won fix; see the
   feedback memory `feedback_torch_qt_dll.md`).
2. Brain workers spin up; once `_on_brain_ready` fires, the animation bus is
   resumed and the chat panel is unlocked.
3. The first-run wizard (`skills/first_run_skill.open_first_run_wizard`)
   walks you through face enrollment, voice ID, theme, and a diagnostics
   check.
4. From then on say `hey aeris` (or click the dock) and start talking.

Useful keyboard shortcuts:

- **Ctrl+Shift+P** — Command palette (Spotlight-style fuzzy skill launcher)
- **Win+Shift+J** (configurable) — Global hotkey to focus AERIS
- **Esc** — Cancel current TTS playback

---

## 4. Core Engine — `core/*.py`

Below is every module under `core/` with a one-line purpose. The grouping is
thematic; alphabetical inside each group.

### 4.1 Brain stack & language understanding

| Module | Role |
|---|---|
| `core/brain.py` | The hybrid intent router: neural classifier + k-NN + exact-match + LRU + LLM fallback. |
| `core/intent_classifier.py` | The neural part of the brain — sentence-transformer embeddings → MLP head. |
| `core/entity_extractor.py` | Slot/entity extraction (city, time, person, file, URL, percentage…). |
| `core/normalizer.py` | Hinglish/English normalisation (collapse fillers, expand "kya hai" patterns, etc.). |
| `core/disambiguator.py` | Confidence-aware tie-breaker when two intents score similarly. |
| `core/tool_router.py` | Decides whether to call a skill, an LLM tool-call, or fall through to chat. |
| `core/time_parser.py` | "tomorrow 5 pm", "in 10 minutes", "next Monday" → absolute datetimes. |
| `core/sentiment.py` | Positive/negative tag attached to every user message (used by enricher + journal). |
| `core/llm_chat.py` | Ollama client. `LLMChat().reply(...)` is the universal chat fallback. |
| `core/response_enricher.py` | **NEW** — Generates varied greetings/replies via the LLM and caches them per-slot. |

### 4.2 Skill plumbing

| Module | Role |
|---|---|
| `core/skill_registry.py` | The `@skill` decorator + `discover_skills()` + per-skill circuit breaker. |
| `core/executor.py` | Dispatch dictionary for legacy intents (`greet`, `open_app`, `schedule_meeting`…). |
| `core/main_engine.py` | Glue that ties the brain → executor → registry → response path. |
| `core/skill_loader.py` | Hot-reload watcher — edit a skill file, it re-registers without restart. |
| `core/plugin_loader.py` | Loads third-party plugins from `data/plugins/<name>/` with a manifest. |
| `core/automation.py` | Routines & action chains. Triggers can be gesture, time, app focus, idle. |
| `core/chain_engine.py` | "When skill X fires, also do Y, Z." Declared in `data/chains.json`. |

### 4.3 Memory, persistence, vault

| Module | Role |
|---|---|
| `core/memory.py` + `data/semantic_memory.npz` | Vector store for conversation recall ("what did I say about X?"). |
| `core/conversation.py` | Rolling N-turn buffer used by the LLM and recap skill. |
| `core/kg_memory.py` | Knowledge graph (`subject — predicate — object`) for "remember that Sara is my sister". |
| `core/vault.py` | DPAPI-backed encrypted secrets store. Values never appear in chat. |
| `core/atomic_io.py` | Crash-safe `tmp → rename` JSON writes for every persistent file. |
| `core/settings.py` + `core/settings_schema.py` | Versioned settings with a migration registry. |
| `core/feedback.py` | SQLite-backed feedback bandit — implicit reward signals retrain the brain offline. |
| `core/cache_registry.py` | `bounded_cache()` wrapper around `functools.lru_cache` with a memory-pressure responder. |

### 4.4 Speech I/O

| Module | Role |
|---|---|
| `core/stt.py` | Google STT (default) with wake-word + VAD. |
| `core/stt_whisper.py` | Whisper STT fallback / preference. |
| `core/tts.py` | Three-tier resilience: **edge-tts → pyttsx3 → SAPI5 via COM**. |
| `core/transcript_bus.py` | Pub/sub bus that streams partial + final STT events to subscribers (transcript pane). |
| `core/voice_id.py` | Speaker enrollment + identification (ECAPA-style embeddings on 4 s of audio). |
| `core/translator.py` | LLM-or-Argos translation; used by the translator-pro skills. |

### 4.5 Vision, gesture, presence

| Module | Role |
|---|---|
| `core/vision_engine.py` | Shared camera grabber + frame multiplexer (so multiple subscribers share one cap). |
| `core/gesture_engine.py` | MediaPipe hand-landmark loop + heuristics for built-in gestures (pinch, peace, fist…). |
| `core/custom_gestures.py` | Records and matches user-trained custom gestures. |
| `core/gesture_practice.py` | Focused practice sessions — counts hits over a configurable window. |
| `core/gesture_trace.py` | Ring buffer of recent gesture fires + blocks for `gesture_trace` skill. |
| `core/face_recognition.py` | InsightFace embeddings + cosine matcher. |
| `core/face_gate.py` | Allow/deny gesture commands based on which master is in front of the camera. |
| `core/presence.py` | Auto-pause gestures when nobody is in front of the camera. |
| `core/auto_label.py` | YOLO-based object labelling overlay for AR mode. |

### 4.6 OS subsystems (the **2026-05-17** addition — see memory `project_aeris_os_subsystems.md`)

| Module | Role |
|---|---|
| `core/resource_monitor.py` | Background CPU/RAM/GPU sampler; throttles heavy skills under pressure. |
| `core/single_instance.py` | OS-level mutex so a second `run_gui.py` exits cleanly. |
| `core/graceful_shutdown.py` | Drains pending work + flushes memory before Qt exits. |
| `core/crash_beacon.py` + `core/crash_dump.py` | Detects last-run crash via beacon file; writes a Python-faulthandler dump on signal. |
| `core/health_server.py` | `127.0.0.1:8765` — `/health`, `/skills`, `/metrics`, `/shutdown`. |
| `core/structured_logs.py` | JSON-line logs with rotating handlers under `data/logs/`. |
| `core/telemetry.py` | In-memory usage counters surfaced by the telemetry dashboard. |

### 4.7 Misc helpers

| Module | Role |
|---|---|
| `core/browser_launcher.py` | Chrome/Edge/Brave profile enumerator + smart launcher. |
| `core/docs_gen.py` | Walks the live registry → writes `docs/SKILLS.md`. |
| `core/dep_validator.py` | "Which optional deps are missing, and which skills go dark because of it?" |
| `core/notify_listener.py` | Subscribes to Windows toast notifications and forwards them. |
| `core/phone_bridge.py` | LAN HTTP endpoint so a phone on the same WiFi can fire skills. |
| `core/gpu_offload.py` | Persists "use CUDA?" preference; encoder + YOLO + InsightFace respect it. |
| `core/privacy_mode.py` | Hard kill-switch — disables mic, camera, gesture, auto-label, notification mirror. |
| `core/sync.py` | Pack/unpack a portable AERIS profile ZIP (settings, gestures, KG, faces…). |
| `core/theme.py` | Three themes (light / dark / cyber) + live switching. |
| `core/workspace_tracker.py` | Polls foreground app every 30 s → usage timeline. |
| `core/doc_index.py` | Embedding-based document Q&A over a folder. |
| `core/scheduler.py` | Tiny in-process scheduler (used by reminders, scheduled-lock, etc.). |

---

## 5. UI Layer — `ui/*.py` + `ui/jarvis_v31/*.py`

### 5.1 Main window stack (`ui/jarvis_v31/`)

| Module | Role |
|---|---|
| `main_window.py` | `JarvisV31Window` — composes every panel, owns the chat + reactor + dock + tray. |
| `splash.py` | Pre-boot splash with progress bar; closes on `brain_ready`. |
| `reactor.py` | The pulsing core orb that reacts to TTS, listening, and thinking states. |
| `glass_chat_panel.py` | Frosted-glass chat panel with markdown rendering and per-message TTS controls. |
| `floating_dock.py` | Auto-hiding bottom dock with mic, camera, theme, settings buttons. |
| `logs_bar.py` | Tail of `data/logs/aeris.log` along the bottom of the window. |
| `title_bar.py` | Custom frameless title bar with traffic-light buttons. |
| `tab_panels.py` | Secondary tab area for plugin/utility panels. |
| `animation_bus.py` | Shared `QTimer` singleton with pause/resume — every animated widget subscribes here. |
| `system_tray.py` | System-tray icon + menu + global hotkey integration. |
| `wiring_system.py` | Connects engine signals (`brain_ready`, `tts_done`, `gesture_fired`…) to UI slots. |
| `tokens.py` | Design tokens (colours, radii, font stacks) consumed by every panel. |
| `command_palette.py` | Floating Ctrl+K overlay alternative to `Ctrl+Shift+P`. |

### 5.2 Standalone dialogs (`ui/*.py`)

| Module | Role |
|---|---|
| `ar_overlay.py` | Translucent always-on-top camera preview with YOLO boxes. |
| `calibration_wizard.py` | Walks a new user through every gesture with live detection feedback. |
| `command_palette.py` | Spotlight-style fuzzy launcher for every skill. |
| `dashboard.py` | Thread runner for the voice loop without freezing Qt. |
| `first_run_wizard.py` | Onboarding wizard (face → voice → theme → diagnostics). |
| `hud_overlay.py` | Always-on-top translucent status widget. |
| `permissions_editor.py` | The `masters × gestures` permissions matrix grid. |
| `settings_panel.py` | Edits the most-touched preferences without hand-editing JSON. |
| `telemetry_dashboard.py` | Tabbed view of usage stats (gestures, skills, workspace, memory). |
| `transcript_pane.py` | Live STT stream window — partial and final events as they arrive. |
| `animations.py` | Reusable easing curves + property animators. |

---

## 6. Every Skill, Grouped — All 338 Voice Commands

Each block shows the **skill name** (what the brain routes to), a **one-line
description** (what it does), and **three sample trigger phrases** so you can
see how to invoke it. All 338 skills are listed.

#### Advanced / Meta — `skills/advanced_skills.py` (3 skills)

- **`mood_today`** — Average sentiment of recent user messages (positive/negative trend).  Sample phrases: `mood today` / `my mood` / `sentiment today`.
- **`ocr_screen`** — Read the text currently on screen (full virtual screen OCR).  Sample phrases: `ocr screen` / `read screen` / `what's on my screen`.
- **`scratchpad_summarize`** — Summarise data/scratch.md into 3 bullets via the brain.  Sample phrases: `summarize scratch` / `summarise scratchpad` / `scratch summary`.

#### App + Audio Control — `skills/app_audio.py` (4 skills)

- **`app_mute`** — Mute a specific application's audio (e.g. 'mute chrome').  Sample phrases: `mute chrome` / `mute spotify` / `mute discord`.
- **`app_unmute`** — Unmute a specific application's audio.  Sample phrases: `unmute chrome` / `unmute spotify` / `unmute discord`.
- **`app_volume_list`** — List every app currently producing audio with its volume %.  Sample phrases: `list app volumes` / `app volumes` / `show app audio`.
- **`app_volume_set`** — Set the per-app volume percentage (e.g. 'set spotify to 30%').  Sample phrases: `set spotify to` / `set chrome to` / `set discord to`.

#### AR Overlay — `skills/ar_overlay_skill.py` (3 skills)

- **`ar_overlay_off`** — Hide the AR camera overlay.  Sample phrases: `ar overlay off` / `hide ar overlay` / `ar preview off`.
- **`ar_overlay_on`** — Show the AR camera overlay — translucent always-on-top live preview with YOLO bounding boxes.  Sample phrases: `ar overlay on` / `show ar overlay` / `ar preview on`.
- **`ar_overlay_status`** — Report whether the AR overlay is currently shown.  Sample phrases: `ar overlay status` / `ar status` / `is ar overlay on`.

#### Automation & Routines — `skills/automation_skill.py` (6 skills)

- **`routine_disable`** — Disable a routine so its trigger no longer fires.  Sample phrases: `disable morning routine` / `disable coding mode` / `disable battery saver`.
- **`routine_enable`** — Enable a routine so its trigger fires it.  Sample phrases: `enable morning routine` / `enable coding mode` / `enable battery saver`.
- **`routine_list`** — List all automation routines and their current state.  Sample phrases: `list routines` / `show routines` / `automation list`.
- **`routine_reload`** — Re-read data/routines.json from disk (after editing it manually).  Sample phrases: `reload routines` / `refresh routines` / `routines refresh karo`.
- **`routine_run`** — Run a routine right now by name (bypasses its trigger).  Sample phrases: `run morning routine` / `start coding mode` / `trigger battery saver`.
- **`routine_status`** — Show the current state of a specific routine.  Sample phrases: `routine status` / `is coding mode on` / `morning routine status`.

#### Brightness Control — `skills/brightness_control.py` (3 skills)

- **`brightness_down`** — Decrease screen brightness by ~10%.  Sample phrases: `dimmer` / `brightness down` / `screen dim karo`.
- **`brightness_set`** — Set screen brightness to an absolute percentage.  Sample phrases: `brightness 50` / `brightness set to 30` / `brightness 60 percent`.
- **`brightness_up`** — Increase screen brightness by ~10%.  Sample phrases: `brighter` / `brightness up` / `screen bright karo`.

#### Browser — `skills/browser_skill.py` (5 skills)

- **`list_browser_profiles`** — List profiles configured in Chrome / Edge / Brave.  Sample phrases: `list chrome profiles` / `chrome profiles batao` / `edge profiles dikhao`.
- **`open_in_browser`** — Open a website or search a topic in a specific browser (and optionally a specific profile).  Sample phrases: `open youtube in brave` / `open gmail in chrome` / `open github in edge`.
- **`search_in_browser`** — Search Google for a query in a specific browser (and optionally a specific profile).  Sample phrases: `search ai in brave` / `search machine learning in chrome` / `google python in edge`.
- **`set_default_browser`** — Set the assistant's preferred browser for searches and URL opens.  Sample phrases: `set default browser brave` / `default browser chrome karo` / `make brave my default browser`.
- **`set_default_profile`** — Remember a default Chrome / Edge / Brave profile so AERIS stops asking.  Sample phrases: `set default chrome profile 1` / `default profile brave shivang work` / `default chrome profile work karo`.

#### Browser Tabs — `skills/browser_tabs.py` (6 skills)

- **`tab_close`** — Close the current browser tab (Ctrl+W).  Sample phrases: `close tab` / `close this tab` / `ye tab band karo`.
- **`tab_new`** — Open a new browser tab (Ctrl+T).  Sample phrases: `new tab` / `open new tab` / `naya tab kholo`.
- **`tab_next`** — Switch to the next browser tab (Ctrl+Tab).  Sample phrases: `next tab` / `tab next` / `agla tab`.
- **`tab_prev`** — Switch to the previous browser tab (Ctrl+Shift+Tab).  Sample phrases: `previous tab` / `prev tab` / `tab prev`.
- **`tab_reopen`** — Reopen the last closed tab (Ctrl+Shift+T).  Sample phrases: `reopen tab` / `reopen closed tab` / `undo close tab`.
- **`tab_switch`** — Jump to a numbered browser tab (Ctrl+1..9). Accepts digits, ordinal words (first / third / last), and Hinglish (pehla / dusra).  Sample phrases: `tab 1` / `tab 2` / `tab 3`.

#### Clipboard — `skills/clipboard.py` (2 skills)

- **`clipboard_copy`** — Copy a piece of text to the system clipboard.  Sample phrases: `yeh copy karo` / `isko copy kar lo` / `copy this text`.
- **`clipboard_paste`** — Read the current clipboard contents.  Sample phrases: `clipboard mein kya hai` / `paste karo` / `clipboard padho`.

#### Clipboard Extras — `skills/clipboard_extras.py` (3 skills)

- **`clipboard_open_url`** — Open the URL currently in clipboard in the default browser.  Sample phrases: `open clipboard url` / `open url from clipboard` / `clipboard url kholo`.
- **`clipboard_say`** — Speak the current clipboard text aloud (truncated to ~400 chars).  Sample phrases: `say clipboard` / `read clipboard` / `speak clipboard`.
- **`clipboard_stats`** — Quick stats about the current clipboard (chars, words, lines).  Sample phrases: `clipboard size` / `clipboard stats` / `clipboard mein kitne characters`.

#### Clipboard History — `skills/clipboard_history.py` (3 skills)

- **`clipboard_clear`** — Wipe stored clipboard history.  Sample phrases: `clipboard clear` / `clipboard history clear karo` / `clipboard wipe karo`.
- **`clipboard_history`** — Show the most recent clipboard items captured by the background watcher.  Sample phrases: `clipboard history` / `clipboard history dikhao` / `show my clipboard`.
- **`copy_history_item`** — Push a previous clipboard entry back to the clipboard by index.  Sample phrases: `copy item 1` / `copy item 2` / `copy item 3`.

#### Clipboard Image — `skills/clipboard_image.py` (2 skills)

- **`image_to_clipboard`** — Copy an image (path or fuzzy name from ~/Pictures) to clipboard.  Sample phrases: `copy image to clipboard` / `put image in clipboard` / `share image`.
- **`last_screenshot_to_clipboard`** — Copy the most-recent AERIS screenshot to clipboard as image.  Sample phrases: `copy last screenshot` / `last screenshot to clipboard` / `last screenshot copy karo`.

#### Cloud Sync — `skills/sync_skill.py` (4 skills)

- **`sync_default_path`** — Print the path the next sync export will write to.  Sample phrases: `sync default path` / `sync path` / `where will sync save`.
- **`sync_export`** — Pack all AERIS customisations (settings, custom gestures, voice ID, knowledge graph, macros, chains, faces) into a ZIP under ~/Documents (or a custom path).  Sample phrases: `sync export` / `export sync` / `export my settings`.
- **`sync_import`** — Restore AERIS customisations from a sync ZIP.  Sample phrases: `sync import` / `import sync` / `restore aeris`.
- **`sync_list`** — List every file that the next sync export would pack.  Sample phrases: `sync list` / `list sync files` / `what gets backed up`.

#### Code Writer — `skills/code_writer.py` (2 skills)

- **`list_generated_code`** — List recently generated code snippets.  Sample phrases: `show generated code` / `konsa code generate kiya hai` / `list my code snippets`.
- **`write_code`** — Generate a code snippet/script from a natural-language spec, save it under data/generated_code/, and open it in an editor.  Sample phrases: `write me a python script that scrapes a website` / `code likho jo ek list ko sort kare` / `ek script banao jo file rename kare`.

#### Command Palette — `skills/command_palette_skill.py` (1 skill)

- **`open_command_palette`** — Open the AERIS command palette — fuzzy-search every skill.  Sample phrases: `open command palette` / `command palette` / `open palette`.

#### Compute / Math — `skills/compute_skills.py` (6 skills)

- **`base64_decode`** — Base64-decode the clipboard (or given text).  Sample phrases: `base64 decode` / `decode base64` / `b64 decode`.
- **`base64_encode`** — Base64-encode the clipboard (or given text).  Sample phrases: `base64 encode` / `encode base64` / `b64 encode`.
- **`hash_text`** — SHA-256 hash of clipboard (or given text).  Sample phrases: `hash` / `sha256` / `sha 256`.
- **`password_generate`** — Generate a strong random password (default 20 chars, mixed).  Sample phrases: `generate password` / `new password` / `password banao`.
- **`qr_code`** — Generate a QR code for a URL or text (saves PNG + opens it).  Sample phrases: `qr code` / `qr` / `qr code banao`.
- **`quick_math`** — Evaluate a math expression (+ - * / ** sqrt sin pi etc.).  Sample phrases: `math` / `calculate` / `compute`.

#### Conversation Recap — `skills/conversation_recap.py` (2 skills)

- **`conversation_clear`** — Wipe the rolling ConversationHistory buffer (does NOT clear the chat panel — see clear_chat for that).  Sample phrases: `clear conversation memory` / `forget conversation` / `conversation history clear`.
- **`conversation_recap`** — Repeat the last N user/assistant exchanges so you remember what was just discussed.  Sample phrases: `recap` / `conversation recap` / `what did we talk about`.

#### Cross-Skill Chains — `skills/chain_skill.py` (4 skills)

- **`chain_path`** — Print the chains.json absolute path so it can be edited.  Sample phrases: `chain path` / `chains path` / `chains file`.
- **`chains_list`** — List every defined chain (trigger + step count).  Sample phrases: `chains list` / `list chains` / `show chains`.
- **`chains_on`** — Activate the cross-skill chain engine — fires follow-up skills automatically when configured triggers happen.  Sample phrases: `chains on` / `chain engine on` / `enable chains`.
- **`chains_reload`** — Reload data/chains.json after editing.  Sample phrases: `reload chains` / `chains reload karo` / `refresh chains`.

#### Custom Gestures — `skills/custom_gestures_skill.py` (4 skills)

- **`gesture_list_custom`** — List all trained custom gestures.  Sample phrases: `list custom gestures` / `custom gestures dikhao` / `show custom gestures`.
- **`gesture_record`** — Record a new custom gesture under a name — hold the pose until AERIS confirms it's saved.  Sample phrases: `record gesture` / `record new gesture` / `teach new gesture`.
- **`gesture_record_status`** — Report whether a custom-gesture recording is in progress.  Sample phrases: `gesture record status` / `gesture recording status` / `recording status gesture`.
- **`gesture_unteach`** — Forget a previously-trained custom gesture.  Sample phrases: `unteach gesture` / `forget gesture` / `remove custom gesture`.

#### Dependency Validator — `skills/dep_validator_skill.py` (2 skills)

- **`dep_check`** — Report every optional dependency + which skills go dark when it's missing.  Sample phrases: `dep check` / `dependency check` / `check dependencies`.
- **`dep_skills_dark`** — List skills that are currently broken because of a missing optional dependency.  Sample phrases: `dark skills` / `broken skills` / `skills dark`.

#### Dev Tools — `skills/dev_tools.py` (10 skills)

- **`git_branch`** — Current git branch + commit-ahead/behind summary.  Sample phrases: `git branch` / `what branch` / `current branch`.
- **`git_commit_quick`** — Commit currently-staged changes with a message taken from the spoken text.  Sample phrases: `git commit` / `commit changes` / `git commit karo`.
- **`git_diff`** — Short stat of uncommitted changes (lines added/removed per file).  Sample phrases: `git diff` / `show diff` / `what changed`.
- **`git_log`** — Last 10 commits of the project repo (short hash + subject + relative date).  Sample phrases: `git log` / `show git log` / `recent commits`.
- **`git_pull`** — git pull --ff-only — fast-forward only, won't create merge commits.  Sample phrases: `git pull` / `pull changes` / `git pull karo`.
- **`git_status`** — Short git status of the AERIS project root.  Sample phrases: `git status` / `git st` / `what's uncommitted`.
- **`open_explorer_here`** — Open File Explorer at the project root.  Sample phrases: `open explorer` / `open folder` / `open file explorer`.
- **`path_to_clipboard`** — Copy the project root path to the clipboard.  Sample phrases: `copy path` / `path copy karo` / `project path`.
- **`restart_explorer`** — Restart explorer.exe (taskbar / desktop refresh).  Sample phrases: `restart explorer` / `explorer restart karo` / `refresh desktop`.
- **`todo_today`** — Show unticked TODO lines from data/scratch.md (last 7 days).  Sample phrases: `todo today` / `what todos` / `my todos`.

#### Diagnostics — `skills/diagnostics.py` (1 skill)

- **`diagnostics`** — Full health check — probe TTS, gesture, vision, brain subsystems and report each as OK/MISSING with a fix hint.  Sample phrases: `diagnose` / `diagnostics` / `run diagnostics`.

#### Dictionary — `skills/dictionary.py` (3 skills)

- **`antonyms`** — List antonyms (opposite-meaning words) for a word.  Sample phrases: `antonyms of` / `antonyms for` / `opposite of`.
- **`define_word`** — Look up a word's definition (dictionaryapi.dev).  Sample phrases: `define` / `definition of` / `what does X mean`.
- **`synonyms`** — List synonyms for a word.  Sample phrases: `synonyms of` / `synonyms for` / `X ke synonyms`.

#### Docs Generator — `skills/docs_gen_skill.py` (1 skill)

- **`regenerate_skill_docs`** — Regenerate docs/SKILLS.md from the live skill registry.  Sample phrases: `regenerate skill docs` / `regen skill docs` / `rebuild skill docs`.

#### Document Q&A — `skills/doc_qa_skill.py` (4 skills)

- **`doc_clear`** — Wipe the document-QA index.  Sample phrases: `doc clear` / `clear doc index` / `wipe doc index`.
- **`doc_index_folder`** — Walk a folder + embed every text file into the doc-QA index.  Sample phrases: `index folder` / `doc index folder` / `index documents`.
- **`doc_query`** — Search the indexed documents for a query — returns top matching files + chunk indices.  Sample phrases: `doc query` / `search docs for` / `query docs`.
- **`doc_status`** — Report current doc-QA index size + indexed folder.  Sample phrases: `doc status` / `doc index status` / `docs status`.

#### Expense Tracker — `skills/expense_tracker.py` (5 skills)

- **`add_expense`** — Log a new expense (amount + description) into the local workbook with auto category.  Sample phrases: `spent 500 on food` / `i spent 1200 on groceries` / `log expense 1500 grocery`.
- **`add_meeting`** — Add a meeting entry to the Meetings tab.  Sample phrases: `schedule meeting with rohan tomorrow 5 pm` / `meeting add karo with team monday` / `rohan ke saath meeting tomorrow 10 am`.
- **`add_task`** — Add a personal task to the Tasks tab with priority + due date.  Sample phrases: `add task write the report` / `task add karo project finish karna hai` / `remind me to call mom tomorrow`.
- **`month_summary`** — Speak the current month's spending breakdown.  Sample phrases: `is mahine kitna kharcha` / `month ka kharcha kitna hai` / `this month spending`.
- **`open_workbook`** — Open the local jarvis workbook (expenses, tasks, meetings) in Excel.  Sample phrases: `open expense sheet` / `open jarvis workbook` / `show expenses`.

#### File Finder — `skills/file_finder.py` (2 skills)

- **`find_file`** — Fuzzy-search the user's common folders for a filename, show top matches and open the best one.  Sample phrases: `find file` / `find my file` / `search file`.
- **`recent_files`** — List the 10 most recently modified files across Documents, Downloads, Desktop, Pictures.  Sample phrases: `recent files` / `show recent files` / `recently modified files`.

#### File Operations — `skills/file_ops.py` (3 skills)

- **`create_folder`** — Create a new folder by path or simple name (under Documents by default).  Sample phrases: `naya folder banao X` / `create folder X` / `X folder banao Documents mein`.
- **`open_file`** — Search Documents/Downloads/Desktop/Pictures for a file by name and open it.  Sample phrases: `X file kholo` / `resume kholo` / `X document open karo`.
- **`reveal_in_explorer`** — Open File Explorer at a common location.  Sample phrases: `downloads kholo` / `documents kholo` / `desktop kholo file explorer mein`.

#### First-Run Wizard — `skills/first_run_skill.py` (1 skill)

- **`open_first_run_wizard`** — Open the AERIS first-run setup wizard — guides through face enrollment + voice + theme + diagnostics.  Sample phrases: `first run wizard` / `open first run wizard` / `setup wizard`.

#### Focus Mode — `skills/focus_mode.py` (3 skills)

- **`focus_deep_off`** — Exit DEEP focus mode — restore apps + clear DND.  Sample phrases: `deep focus off` / `stop deep focus` / `exit deep focus`.
- **`focus_deep_on`** — Enter DEEP focus mode — close distracting apps + Windows DND.  Sample phrases: `deep focus on` / `deep work mode` / `deep focus karo`.
- **`focus_deep_status`** — Report whether DEEP focus mode is currently on.  Sample phrases: `deep focus status` / `deep focus on hai kya` / `is deep focus on`.

#### Gesture Calibration — `skills/calibration_skill.py` (1 skill)

- **`start_calibration_wizard`** — Launch the gesture calibration wizard — walks you through each gesture with live detection feedback.  Sample phrases: `start calibration` / `calibration wizard` / `gesture calibration`.

#### Gesture Core — `skills/gesture_skill.py` (5 skills)

- **`cursor_mode_off`** — Stop the air-cursor (gesture engine stays on for other gestures).  Sample phrases: `cursor mode off` / `mouse mode off` / `cursor off karo`.
- **`cursor_mode_on`** — Turn your index finger into a mouse — pinch = left click.  Sample phrases: `cursor mode on` / `mouse mode on` / `cursor on karo`.
- **`gesture_mode_off`** — Stop the gesture controller and release the camera.  Sample phrases: `gesture mode off` / `gestures off` / `close gesture mode`.
- **`gesture_mode_on`** — Activate hand-gesture control — sequenced, collision-free gestures for hands-free desktop control.  Sample phrases: `gesture mode on` / `gestures on` / `open gesture mode`.
- **`gesture_status`** — Report whether gesture control is currently active.  Sample phrases: `gesture status` / `gestures chalu hain kya` / `is gesture mode on`.

#### Gesture Management — `skills/gesture_mgmt.py` (7 skills)

- **`gesture_bind`** — Rebind a gesture to a registered skill name (e.g. 'bind peace to screenshot_full').  Sample phrases: `bind gesture` / `bind peace to` / `bind double_pinch to`.
- **`gesture_bindings`** — List every custom gesture binding currently in effect.  Sample phrases: `list gesture bindings` / `show gesture bindings` / `gesture bindings dikhao`.
- **`gesture_stats`** — Aggregate gesture trace counts by name + face for the last hour.  Sample phrases: `gesture stats` / `gesture statistics` / `kya kya gestures hue`.
- **`gesture_trace`** — Show the last 10 gesture events (fires + blocks).  Sample phrases: `gesture trace` / `show gesture trace` / `gesture log`.
- **`gesture_trace_clear`** — Wipe the gesture trace log.  Sample phrases: `clear gesture trace` / `gesture trace clear` / `wipe gesture log`.
- **`gesture_unbind`** — Remove a gesture binding override — revert to the built-in action.  Sample phrases: `unbind gesture` / `unbind peace` / `reset gesture binding`.
- **`what_does_gesture_do`** — Describe the effective action for a gesture (override if set, else built-in default).  Sample phrases: `what does peace do` / `what does double_pinch do` / `what does my peace gesture do`.

#### Gesture Practice — `skills/gesture_practice_skill.py` (3 skills)

- **`practice_gesture`** — Start a focused practice session for one gesture — counts hits over a window (default 30 s).  Sample phrases: `practice gesture` / `practice` / `gesture practice karo`.
- **`practice_status`** — Report current gesture-practice session stats.  Sample phrases: `practice status` / `gesture practice status` / `kya practice chal raha hai`.
- **`practice_stop`** — Stop the current gesture-practice session and return stats.  Sample phrases: `practice stop` / `stop practice` / `practice band karo`.

#### Gesture Sensitivity — `skills/gesture_sensitivity.py` (2 skills)

- **`gesture_sensitivity_set`** — Set the gesture engine sensitivity — very_sensitive / sensitive / normal / relaxed / very_relaxed.  Sample phrases: `gesture sensitivity` / `set gesture sensitivity` / `gestures more sensitive`.
- **`gesture_sensitivity_status`** — Report the current gesture sensitivity level + multiplier.  Sample phrases: `gesture sensitivity status` / `what is gesture sensitivity` / `current gesture sensitivity`.

#### GPU Offload — `skills/gpu_offload_skill.py` (3 skills)

- **`gpu_offload_off`** — Revert heavy ML models to CPU on next reload.  Sample phrases: `gpu off` / `disable gpu` / `gpu offload off`.
- **`gpu_offload_on`** — Switch heavy ML models (encoder / YOLO / InsightFace) to GPU on next reload — persists across restarts.  Sample phrases: `gpu on` / `enable gpu` / `gpu offload on`.
- **`gpu_status`** — Report GPU offload preference + CUDA availability.  Sample phrases: `gpu status` / `cuda status` / `is gpu enabled`.

#### Help Catalog — `skills/help_catalog.py` (1 skill)

- **`help_catalog`** — List every available skill with one example trigger phrase per skill.  Sample phrases: `help` / `what can you do` / `kya kar sakte ho`.

#### HUD Overlay — `skills/hud_skill.py` (4 skills)

- **`hud_move`** — Move the HUD to a named corner.  Sample phrases: `hud move` / `move hud` / `hud to top right`.
- **`hud_off`** — Hide the heads-up overlay.  Sample phrases: `hud off` / `hide hud` / `heads up off`.
- **`hud_on`** — Show the always-on-top AERIS heads-up overlay.  Sample phrases: `hud on` / `show hud` / `heads up on`.
- **`hud_status`** — Report whether the HUD is currently visible.  Sample phrases: `hud status` / `is hud on` / `hud kya hai`.

#### Info Lookups — `skills/info_skills.py` (4 skills)

- **`currency_convert`** — Convert between currencies (e.g. '100 usd to inr').  Sample phrases: `convert currency` / `currency convert` / `100 usd to inr`.
- **`date_diff`** — Days between two dates ('days between 2026-01-01 and today').  Sample phrases: `days between` / `date diff` / `how many days`.
- **`screen_color_pick`** — Read the pixel under the cursor and copy hex to clipboard.  Sample phrases: `pick color` / `color pick` / `screen color`.
- **`weather_local`** — Current weather + today's forecast (open-meteo, no API key).  Sample phrases: `weather` / `today's weather` / `weather batao`.

#### Journal — `skills/journal.py` (3 skills)

- **`journal_path`** — Print the journal file path so it can be opened in an editor.  Sample phrases: `journal path` / `journal file` / `where is my journal`.
- **`journal_show`** — Read back the last 10 journal entries.  Sample phrases: `show journal` / `journal dikhao` / `read journal`.
- **`note_append`** — Append a timestamped line to the rolling journal (data/notes/journal.md).  Sample phrases: `log` / `log this` / `add to journal`.

#### Knowledge Graph — `skills/kg_skill.py` (5 skills)

- **`kg_facts_about`** — List every stored fact about a subject.  Sample phrases: `facts about` / `tell me facts about` / `facts of`.
- **`kg_forget`** — Forget every stored fact about a subject.  Sample phrases: `forget about` / `kg forget` / `remove facts about`.
- **`kg_list`** — List every stored knowledge-graph triple.  Sample phrases: `list knowledge` / `kg list` / `all facts`.
- **`kg_query`** — Ask the knowledge graph a question — 'who is X', 'where do I live', 'what's my Y'.  Sample phrases: `who is` / `where do i live` / `where do i work`.
- **`kg_remember`** — Save a fact into the knowledge graph (e.g. 'remember that Sara is my sister').  Sample phrases: `remember that` / `note that` / `store that`.

#### Live Transcript — `skills/transcript_skill.py` (4 skills)

- **`transcript_log`** — Print the last 10 STT events from the transcript bus.  Sample phrases: `transcript log` / `recent transcript` / `show transcript history`.
- **`transcript_off`** — Close the live transcript pane.  Sample phrases: `transcript off` / `hide transcript` / `close transcript`.
- **`transcript_on`** — Open the live STT transcript pane — see your speech and AERIS replies stream in real-time.  Sample phrases: `transcript on` / `show transcript` / `open transcript`.
- **`transcript_status`** — Report whether the transcript pane is visible.  Sample phrases: `transcript status` / `is transcript on` / `transcript visible kya hai`.

#### LLM Chat — `skills/llm_chat_skill.py` (2 skills)

- **`ask_jarvis`** — Free-form chat with the local LLM — model may auto-fire any registered AERIS skill to satisfy the request.  Sample phrases: `ask jarvis` / `ask aeris` / `ask ai`.
- **`llm_status`** — Report local-LLM health — model, reachable state, tool count.  Sample phrases: `llm status` / `ai status` / `ollama status`.

#### Log Digest — `skills/log_digest.py` (1 skill)

- **`log_digest_today`** — Summarize today's data/logs/aeris.log entries by category.  Sample phrases: `summarize logs` / `log digest` / `logs digest`.

#### Master Users — `skills/master_users.py` (6 skills)

- **`add_master`** — Add an already-registered face to the master_users list.  Sample phrases: `add master` / `add master shivang` / `add master sara`.
- **`face_gate_status`** — Explain whether the face gate is open/closed and the last-seen status.  Sample phrases: `face gate status` / `gate status` / `is face gate on`.
- **`i_am_master`** — Register the current face as a new master user and add them to the master_users list in one shot.  Sample phrases: `i am master` / `i am the master` / `main hu master`.
- **`list_masters`** — List every user marked as master (allowed to drive gestures).  Sample phrases: `list masters` / `show masters` / `who are masters`.
- **`register_face`** — Enroll a face from the current camera frame under a name. Pre-requisite for marking that name as a master.  Sample phrases: `register my face` / `register face` / `face register karo`.
- **`remove_master`** — Remove a name from the master_users list.  Sample phrases: `remove master` / `remove master shivang` / `remove from masters`.

#### Memory — `skills/memory_skills.py` (2 skills)

- **`memory_stats`** — Show semantic-memory size (records / embedded / queue).  Sample phrases: `memory stats` / `memory size` / `memory ka size`.
- **`recall`** — Recall past conversations semantically (by meaning, not keyword).  Sample phrases: `recall` / `remember when` / `what did i say about`.

#### Multi-Monitor — `skills/monitor_swap.py` (2 skills)

- **`monitor_list`** — List all physical monitors with their virtual-screen rectangles.  Sample phrases: `list monitors` / `show monitors` / `how many monitors`.
- **`monitor_swap`** — Move the active window to the next physical monitor.  Sample phrases: `monitor swap` / `next monitor` / `move to next monitor`.

#### News — `skills/news.py` (1 skill)

- **`news_briefing`** — Fetch latest headlines and summarize them in Hinglish (categories: tech, india, business, world).  Sample phrases: `aaj ki news batao` / `news sunao` / `latest headlines kya hain`.

#### Notification Mirror — `skills/notification_mirror.py` (4 skills)

- **`last_notification`** — Describe the most recent Windows toast notification.  Sample phrases: `last notification` / `what was the last notification` / `pichli notification`.
- **`notification_mirror_off`** — Stop reading Windows toasts aloud.  Sample phrases: `stop reading notifications` / `notification mirror off` / `stop notifications`.
- **`notification_mirror_on`** — Read each new Windows toast notification aloud via TTS.  Sample phrases: `read my notifications` / `notification mirror on` / `speak notifications`.
- **`notification_mirror_status`** — Report whether notification mirror is on / available.  Sample phrases: `notification mirror status` / `is notification mirror on` / `notifications status`.

#### Object Auto-Label — `skills/auto_label_skill.py` (5 skills)

- **`auto_label_off`** — Stop auto object labeling.  Sample phrases: `auto label off` / `object label off` / `stop labeling`.
- **`auto_label_on`** — Start auto object labeling — narrate items held up to the camera.  Sample phrases: `auto label on` / `object label on` / `start labeling`.
- **`auto_label_speak_off`** — Stop speaking auto-label results (chat/log entries continue).  Sample phrases: `stop speaking labels` / `narrate labels off` / `labels mat bolo`.
- **`auto_label_speak_on`** — Make auto-label speak each new object's name out loud.  Sample phrases: `speak labels` / `narrate labels on` / `speak objects`.
- **`auto_label_status`** — Report whether auto-labeling is running and what was seen recently.  Sample phrases: `auto label status` / `labels status` / `what did you see`.

#### Object Detection — `skills/object_skill.py` (3 skills)

- **`detect_holding`** — Look at the webcam and identify what the user is holding.  Sample phrases: `what am I holding` / `what is in my hand` / `yeh kya hai mere haath mein`.
- **`detect_scene`** — Describe what the webcam currently sees.  Sample phrases: `what do you see` / `describe the scene` / `camera mein kya dikh raha hai`.
- **`snap_and_save`** — Grab a webcam frame and save it to data/snapshots/.  Sample phrases: `snap a photo` / `selfie le lo` / `webcam ka photo lo`.

#### Outlook Calendar — `skills/outlook_calendar.py` (3 skills)

- **`next_meeting`** — Show the next upcoming Outlook appointment.  Sample phrases: `next meeting` / `what's my next meeting` / `agla meeting kya hai`.
- **`this_week_meetings`** — List appointments in the next 7 days.  Sample phrases: `this week meetings` / `week ka schedule` / `is hafte ki meetings`.
- **`todays_meetings`** — List every appointment on today's calendar.  Sample phrases: `todays meetings` / `today's meetings` / `today's calendar`.

#### Outlook Email — `skills/outlook_email.py` (2 skills)

- **`compose_email`** — Open an Outlook draft window pre-filled with recipient / subject / body parsed from your voice. Does NOT send.  Sample phrases: `compose email` / `write email` / `draft email`.
- **`email_draft_blank`** — Open an empty Outlook draft window.  Sample phrases: `blank email` / `new email` / `new outlook email`.

#### Per-App Profiles — `skills/per_app_profiles.py` (4 skills)

- **`profile_bind`** — Bind a gesture to a skill ONLY when a specific app is in foreground (e.g. 'in code bind peace to git_status').  Sample phrases: `in code bind` / `in chrome bind` / `for vs code bind`.
- **`profile_clear`** — Wipe all per-app gesture profile overrides.  Sample phrases: `clear profiles` / `reset profiles` / `profiles clear karo`.
- **`profile_list`** — List every per-app gesture profile override.  Sample phrases: `list profiles` / `show profiles` / `profiles dikhao`.
- **`profile_unbind`** — Remove a per-app gesture override.  Sample phrases: `in code unbind` / `for chrome unbind` / `in vs code unbind`.

#### Permissions Editor — `skills/permissions_editor_skill.py` (1 skill)

- **`open_permissions_editor`** — Open the masters × gestures permissions matrix — edit every per-user gesture allowance in one grid.  Sample phrases: `open permissions editor` / `permissions editor` / `edit permissions`.

#### Permissions Matrix — `skills/master_permissions.py` (6 skills)

- **`master_allow_all`** — Grant a master full access to every gesture.  Sample phrases: `allow all gestures for` / `master allow all` / `give X all gestures`.
- **`master_block`** — Block a specific gesture for a master (removes from their allowlist).  Sample phrases: `block gesture` / `deny gesture` / `remove gesture for`.
- **`master_grant`** — Grant a specific gesture to a master (adds to their allowlist).  Sample phrases: `grant gesture` / `allow gesture` / `add gesture for`.
- **`master_kid_mode`** — Restrict a master to a small set of safe gestures (no lock screen, no volume control, no app-switch).  Sample phrases: `kid mode for` / `set kid mode` / `X ko kid mode pe rakho`.
- **`master_permissions_clear`** — Wipe per-master gesture permissions (everyone reverts to allow-all).  Sample phrases: `clear master permissions` / `reset master permissions` / `permissions clear karo`.
- **`master_permissions_show`** — Show the per-master gesture allowlist.  Sample phrases: `master permissions` / `show master permissions` / `permissions dikhao`.

#### Phone Bridge — `skills/phone_bridge_skill.py` (3 skills)

- **`phone_pair_off`** — Stop the phone-bridge HTTP server.  Sample phrases: `phone pair off` / `stop phone bridge` / `phone bridge off`.
- **`phone_pair_on`** — Start the LAN phone-bridge HTTP server so a phone browser on the same WiFi can fire AERIS skills.  Sample phrases: `phone pair on` / `start phone bridge` / `phone bridge on`.
- **`phone_pair_url`** — Show the phone-bridge URL + access token.  Sample phrases: `phone pair url` / `phone bridge url` / `phone pair status`.

#### Plugin Loader — `skills/plugin_skill.py` (5 skills)

- **`plugin_disable`** — Disable a plugin (won't load on next restart).  Sample phrases: `disable plugin` / `plugin disable` / `plugin band karo`.
- **`plugin_enable`** — Enable a plugin by name (also loads it now if possible).  Sample phrases: `enable plugin` / `plugin enable` / `plugin chalu karo`.
- **`plugin_list`** — List discovered AERIS plugins under data/plugins/.  Sample phrases: `list plugins` / `show plugins` / `plugins dikhao`.
- **`plugin_load_all`** — Load every enabled plugin (idempotent).  Sample phrases: `load all plugins` / `load plugins` / `plugins load karo`.
- **`plugin_path`** — Print the plugins folder absolute path.  Sample phrases: `plugin path` / `plugin folder` / `plugins kahan hai`.

#### Pomodoro Timer — `skills/pomodoro.py` (3 skills)

- **`pomodoro_start`** — Start a Pomodoro session (default 25-min work + 5-min breaks; long 15-min break every 4th cycle).  Sample phrases: `start pomodoro` / `pomodoro start karo` / `begin pomodoro`.
- **`pomodoro_status`** — Report current pomodoro phase + time remaining.  Sample phrases: `pomodoro status` / `pomodoro kahan tak` / `pomodoro time left`.
- **`pomodoro_stop`** — Stop the current pomodoro session.  Sample phrases: `stop pomodoro` / `pomodoro stop karo` / `cancel pomodoro`.

#### Preferences — `skills/preferences.py` (3 skills)

- **`get_preference`** — Read back a saved preference (name/city/browser/voice/etc.).  Sample phrases: `what's my name` / `what is my name` / `mera naam kya hai`.
- **`reset_preferences`** — Restore all preferences to their default values.  Sample phrases: `reset preferences` / `preferences reset karo` / `restore defaults`.
- **`set_preference`** — Save a user preference (name/city/browser/voice/etc.) to settings.json.  Sample phrases: `set my name to Shivang` / `remember my name is Shivang` / `remember my city as Mumbai`.

#### Presence Detection — `skills/presence_skill.py` (3 skills)

- **`presence_auto_pause_off`** — Disable the camera-presence auto-pause for gestures.  Sample phrases: `presence auto pause off` / `stop presence` / `presence off`.
- **`presence_auto_pause_on`** — Auto-pause the gesture engine when you walk away from the camera and resume when you return.  Sample phrases: `presence auto pause on` / `auto pause gestures` / `camera presence on`.
- **`presence_status`** — Report whether AERIS currently sees a user in front of the camera.  Sample phrases: `presence status` / `am i present` / `is anyone there`.

#### Privacy Mode — `skills/privacy_mode_skill.py` (3 skills)

- **`privacy_mode_off`** — Disable privacy mode (does NOT auto-resume subsystems — you re-enable what you want).  Sample phrases: `privacy mode off` / `resume listening` / `privacy off`.
- **`privacy_mode_on`** — Hard 'stop listening' — disables wake-word + STT + gesture engine + camera + auto-label + notification mirror.  Sample phrases: `privacy mode on` / `stop listening` / `go private`.
- **`privacy_mode_status`** — Report privacy mode state + per-subsystem on/off.  Sample phrases: `privacy mode status` / `privacy status` / `is privacy mode on`.

#### Productivity Extras — `skills/productivity_extras.py` (5 skills)

- **`append_note`** — Append a quick note to data/scratch.md with a timestamp.  Sample phrases: `note this` / `add note` / `save note`.
- **`clipboard_transform`** — Transform clipboard contents (upper/lower/slug/json/strip/reverse).  Sample phrases: `uppercase clipboard` / `lowercase clipboard` / `slugify clipboard`.
- **`file_search`** — Search recent user files by substring (case-insensitive).  Sample phrases: `find file` / `search file` / `file dhundo`.
- **`kill_process`** — Terminate a process by name (e.g. 'firefox', 'discord').  Sample phrases: `kill process` / `kill firefox` / `close process`.
- **`quick_timer`** — Set a timer — '5 minute timer', '10 min timer', '30 minute pomodoro'.  Sample phrases: `5 minute timer` / `10 minute timer` / `15 minute timer`.

#### Productivity Pack — `skills/productivity_pack.py` (4 skills)

- **`daily_briefing`** — Speak a quick personalized briefing: greeting, weather, tasks, expenses, system status.  Sample phrases: `good morning` / `daily briefing` / `morning briefing`.
- **`focus_mode_off`** — Exit focus mode and cancel the pomodoro.  Sample phrases: `focus mode off` / `focus mode band karo` / `focus mode stop karo`.
- **`focus_mode_on`** — Enter focus mode: close distracting apps, open work apps, start a pomodoro.  Sample phrases: `focus mode on` / `focus mode start karo` / `deep work mode chalu karo`.
- **`smart_paste`** — Reformat the current clipboard content: JSON → pretty, URL → page title, long text → summary, code → de-indent.  Sample phrases: `smart paste` / `clipboard format karo` / `format my clipboard`.

#### Quick Calculator — `skills/quick_calc.py` (1 skill)

- **`quick_calc`** — Evaluate a math expression spoken in English / Hinglish.  Sample phrases: `calculate` / `what is` / `kya hai`.

#### Quick Info — `skills/quick_info.py` (5 skills)

- **`battery_status`** — Battery percentage, plugged-in state, estimated time left.  Sample phrases: `battery` / `battery status` / `battery kitni hai`.
- **`clear_chat`** — Acknowledge a clear-chat request. The UI listens for this and wipes the chat history pane.  Sample phrases: `clear chat` / `chat clear karo` / `wipe chat`.
- **`current_date`** — Speak today's date and weekday.  Sample phrases: `what's the date` / `today's date` / `current date`.
- **`current_time`** — Speak the wall-clock time (24h + AM/PM).  Sample phrases: `what's the time` / `what is the time` / `current time`.
- **`greeting`** — Acknowledge a wake/hello with a time-of-day greeting.  Sample phrases: `hello` / `hi` / `hey jarvis`.

#### Repeat Last — `skills/repeat_last.py` (1 skill)

- **`repeat_last`** — Re-execute the previous user command (skips this 'repeat' trigger itself).  Sample phrases: `repeat` / `repeat last` / `repeat last command`.

#### Response Enricher — `skills/response_enricher_skill.py` (4 skills)

- **`enrich_cache_clear`** — Forget all cached enriched replies and start fresh.  Sample phrases: `clear response cache` / `response cache clear karo` / `forget cached replies`.
- **`enrich_responses_off`** — Disable LLM-backed response variation (use plain templates).  Sample phrases: `disable response enrichment` / `responses enrich band karo` / `turn off response enrichment`.
- **`enrich_responses_on`** — Enable LLM-backed response variation so stock replies stay fresh.  Sample phrases: `enable response enrichment` / `responses enrich karo` / `enable smart replies`.
- **`enrich_status`** — Report enrichment toggle, LLM availability, and cached counts.  Sample phrases: `response enrichment status` / `enrich status` / `are smart replies on`.

#### Scheduled Lock — `skills/scheduled_lock.py` (3 skills)

- **`cancel_lock`** — Cancel a pending scheduled lock (from lock_after).  Sample phrases: `cancel lock` / `lock cancel karo` / `abort lock`.
- **`lock_after`** — Schedule a lock-screen N minutes from now (default 5 min). Replaces any previously scheduled lock.  Sample phrases: `lock after` / `lock in` / `lock screen after`.
- **`lock_status`** — Report how long until the scheduled lock fires.  Sample phrases: `lock status` / `lock kab hoga` / `when will it lock`.

#### Screenshot — `skills/screenshot_skill.py` (3 skills)

- **`screenshot_full`** — Capture the entire desktop (all monitors) to Pictures/AERIS/.  Sample phrases: `screenshot` / `take a screenshot` / `screenshot lo`.
- **`screenshot_window`** — Capture just the active window (focused app) to Pictures/AERIS/.  Sample phrases: `screenshot window` / `active window screenshot` / `this window screenshot`.
- **`screenshots_folder`** — Open the folder where AERIS saves screenshots (Pictures/AERIS).  Sample phrases: `open screenshots folder` / `screenshots folder kholo` / `show screenshots`.

#### Settings Panel — `skills/settings_panel_skill.py` (1 skill)

- **`open_settings_panel`** — Open the AERIS settings dialog — edit voice, gestures, masters, browser without touching settings.json.  Sample phrases: `open settings panel` / `open settings` / `settings panel kholo`.

#### Settings Schema — `skills/settings_schema_skill.py` (2 skills)

- **`settings_schema_migrate`** — Run pending settings.json migrations + fill any missing default keys. Idempotent — safe to call repeatedly.  Sample phrases: `migrate settings` / `settings migrate karo` / `run settings migration`.
- **`settings_schema_status`** — Report current settings schema version + whether a migration is pending.  Sample phrases: `settings schema status` / `settings version` / `schema status`.

#### Sheets Sync — `skills/sheets_sync.py` (2 skills)

- **`sheets_status`** — Show whether Google Sheets sync is configured and where the synced sheet lives.  Sample phrases: `sheets sync status` / `google sheets connect hai kya` / `sheets configured hai kya`.
- **`sync_to_sheets`** — Upload the local AERIS workbook to Google Sheets.  Sample phrases: `sync to google sheets` / `google sheets pe upload karo` / `cloud pe save karo expenses`.

#### Snip OCR — `skills/snip_ocr.py` (2 skills)

- **`full_screen_ocr`** — OCR the entire current screen and return the text.  Sample phrases: `full screen ocr` / `saari screen padho` / `whole screen text`.
- **`snip_and_ocr`** — Select a screen region and read the text inside it (OCR).  Sample phrases: `snip and read` / `screenshot ke text padho` / `yeh padh ke batao`.

#### Snippets — `skills/snippet_skills.py` (3 skills)

- **`text_expand`** — Expand a snippet trigger to its full text on the clipboard.  Sample phrases: `expand sig` / `expand email` / `expand date`.
- **`text_expand_add`** — Add or update a snippet: 'add snippet trig=value text'.  Sample phrases: `add snippet` / `new snippet` / `snippet add karo`.
- **`text_expand_list`** — List every available snippet trigger.  Sample phrases: `list snippets` / `show snippets` / `snippets list`.

#### Spotify Control — `skills/spotify_control.py` (3 skills)

- **`spotify_next`** — Skip to next Spotify track.  Sample phrases: `agla gaana chalao` / `next song` / `skip karo`.
- **`spotify_pause`** — Pause Spotify playback on the active device.  Sample phrases: `spotify pause karo` / `music pause kar do` / `pause the music`.
- **`spotify_play_track`** — Search Spotify for a specific track and start playback on the active device.  Sample phrases: `spotify pe X chala do` / `play X on spotify` / `X gaana chala do spotify pe`.

#### System Health — `skills/system_health.py` (2 skills)

- **`full_system_health`** — Deep system check: battery, CPU, RAM, disk, uptime, top processes, network ping, WiFi SSID.  Sample phrases: `full system health` / `system health check karo` / `deep system check`.
- **`network_check`** — Quick network status: ping, public IP, WiFi name.  Sample phrases: `network check karo` / `internet check karo` / `wifi name kya hai`.

#### System Power — `skills/system_skills.py` (9 skills)

- **`cancel_shutdown`** — Abort a pending shutdown.  Sample phrases: `cancel shutdown` / `shutdown cancel karo` / `ruk jao shutdown`.
- **`cpu_info`** — CPU model, core count, current frequency.  Sample phrases: `cpu info` / `kaun sa processor` / `what cpu`.
- **`lock_screen`** — Lock the workstation (Win+L equivalent).  Sample phrases: `lock screen` / `lock the pc` / `lock karo`.
- **`network_status`** — Local IP, WiFi SSID, public IP.  Sample phrases: `network status` / `wifi status` / `kya wifi connect hai`.
- **`ping`** — Ping a host and report round-trip time.  Sample phrases: `ping` / `ping google` / `internet check karo`.
- **`restart_pc`** — Schedule a restart in 60 s (can be cancelled).  Sample phrases: `restart pc` / `reboot` / `computer restart`.
- **`shutdown_pc`** — Schedule a shutdown in 60 s (can be cancelled).  Sample phrases: `shutdown` / `shutdown pc` / `power off`.
- **`sleep_pc`** — Put the PC to sleep (S3 standby).  Sample phrases: `sleep pc` / `sleep mode` / `pc sleep karo`.
- **`system_stats`** — Snapshot of CPU, RAM, disk, uptime.  Sample phrases: `system stats` / `system status` / `system info`.

#### Teach-Me — `skills/teach_skills.py` (3 skills)

- **`forget_command`** — Remove a user-taught phrase (or all phrases for an intent).  Sample phrases: `forget command` / `remove command` / `untrain`.
- **`list_taught`** — Show every user-taught phrase.  Sample phrases: `list taught` / `list commands` / `show taught`.
- **`teach_command`** — Teach AERIS a new utterance for an existing intent or skill.  Sample phrases: `from now on 'open ide' means open_app` / `teach open_app 'fire up vscode'` / `open_app = 'launch editor'`.

#### Telemetry — `skills/telemetry_skill.py` (2 skills)

- **`open_telemetry_dashboard`** — Open the AERIS telemetry dashboard — usage stats for gestures, skills, workspace, memory.  Sample phrases: `open telemetry` / `open telemetry dashboard` / `telemetry dashboard`.
- **`telemetry_digest`** — Print a text digest of usage stats (gestures, skills, memos, journal, KG, faces) over the last hour.  Sample phrases: `telemetry digest` / `usage digest` / `stats digest`.

#### Theming — `skills/theme_skill.py` (5 skills)

- **`theme_cyber`** — Switch the AERIS UI to the cyber (neon-on-black) theme.  Sample phrases: `cyber theme` / `theme cyber` / `set theme cyber`.
- **`theme_cycle`** — Rotate to the next available theme.  Sample phrases: `cycle theme` / `next theme` / `theme switch`.
- **`theme_dark`** — Switch the AERIS UI to the dark theme.  Sample phrases: `dark theme` / `theme dark` / `set theme dark`.
- **`theme_light`** — Switch the AERIS UI to the light theme.  Sample phrases: `light theme` / `theme light` / `set theme light`.
- **`theme_status`** — Report the current theme + available options.  Sample phrases: `theme status` / `current theme` / `what theme is on`.

#### Timers — `skills/timer_skill.py` (3 skills)

- **`cancel_timer`** — Cancel an active timer by id, or all if 'all' is given.  Sample phrases: `cancel timer` / `stop timer` / `timer cancel karo`.
- **`list_timers`** — List all active timers.  Sample phrases: `list timers` / `active timers batao` / `konse timers chalu hain`.
- **`set_timer`** — Set a countdown timer that fires a desktop toast/beep.  Sample phrases: `set a 5 minute timer` / `5 minute ka timer lagao` / `10 minute timer chalu karo`.

#### Translate — `skills/translate.py` (2 skills)

- **`translate_to_english`** — Translate a Hindi or Hinglish phrase into English.  Sample phrases: `english mein translate karo X` / `X ko english mein bolo` / `translate to english X`.
- **`translate_to_hindi`** — Translate an English phrase into Hindi.  Sample phrases: `hindi mein translate karo X` / `X ko hindi mein bolo` / `translate to hindi X`.

#### Translator Pro — `skills/translator_skill.py` (3 skills)

- **`translate_clipboard`** — Translate the current clipboard contents into a target language (default English).  Sample phrases: `translate clipboard` / `translate clipboard to` / `translate clipboard into`.
- **`translate_status`** — Report which translation backends (LLM / argos / Google URL) are reachable.  Sample phrases: `translate status` / `translator status` / `translation backends`.
- **`translate_to`** — Translate text into a target language. Format: 'translate <text> to <language>'.  Sample phrases: `translate this to` / `translate to` / `translate text to`.

#### TTS Voice — `skills/tts_voice.py` (4 skills)

- **`tts_voice_list`** — List the curated TTS voice aliases.  Sample phrases: `list voices` / `list tts voices` / `available voices`.
- **`tts_voice_reset`** — Revert the TTS voice (language/accent) to the AERIS default (en-IN-NeerjaNeural). Note: separate from 'voice reset' which restores rate+volume.  Sample phrases: `reset tts voice` / `tts voice reset` / `default tts voice`.
- **`tts_voice_set`** — Switch the TTS voice. Accepts aliases (hindi/indian male/american female/etc.) or raw Edge-TTS neural names.  Sample phrases: `set voice to` / `change voice to` / `switch voice to`.
- **`tts_voice_status`** — Report the currently selected TTS voice (language/accent). For rate+volume use 'voice status'.  Sample phrases: `tts voice status` / `what tts voice am i using` / `current tts voice`.

#### Vault (Secrets) — `skills/vault_skills.py` (4 skills)

- **`vault_delete`** — Remove a secret from the vault.  Sample phrases: `vault delete` / `delete secret` / `remove secret`.
- **`vault_get`** — Decrypt a vault secret and copy it to the clipboard (never to chat log).  Sample phrases: `vault get` / `get secret` / `retrieve secret`.
- **`vault_list`** — List all stored secret names (values never returned).  Sample phrases: `vault list` / `list secrets` / `list vault`.
- **`vault_store`** — Encrypt + store a secret in the Windows DPAPI vault.  Sample phrases: `vault store` / `store secret` / `save secret`.

#### Vision — `skills/vision.py` (2 skills)

- **`click_text`** — Find a piece of text on the screen and click its center.  Sample phrases: `X pe click karo` / `click on X` / `X button dabao`.
- **`read_screen`** — OCR the visible screen and return all extracted text.  Sample phrases: `screen padho` / `yeh screen padh do` / `read this screen`.

#### Voice ID — `skills/voice_id_skill.py` (4 skills)

- **`speaker_enroll`** — Record 4 seconds of your voice and store a speaker signature for future identification.  Sample phrases: `enroll my voice` / `speaker enroll` / `register my voice`.
- **`speaker_forget`** — Remove an enrolled speaker from the voice-ID registry.  Sample phrases: `forget speaker` / `speaker forget` / `delete speaker`.
- **`speaker_identify`** — Listen for 2 s and identify the loudest enrolled speaker.  Sample phrases: `identify speaker` / `who's speaking` / `kaun bol raha hai`.
- **`speaker_list`** — List every enrolled speaker.  Sample phrases: `list speakers` / `show speakers` / `speakers dikhao`.

#### Voice Macros — `skills/macros.py` (3 skills)

- **`list_macros`** — List every macro saved in data/macros.json.  Sample phrases: `list macros` / `show macros` / `available macros`.
- **`reload_macros`** — Reload macros from disk (after editing data/macros.json).  Sample phrases: `reload macros` / `macros reload karo` / `refresh macros`.
- **`run_macro`** — Execute a saved macro from data/macros.json (a chain of skills).  Sample phrases: `run macro` / `execute macro` / `macro chalao`.

#### Voice Memos — `skills/voice_memo.py` (6 skills)

- **`delete_last_memo`** — Delete the most recently recorded voice memo.  Sample phrases: `delete last memo` / `last memo delete karo` / `remove last memo`.
- **`list_voice_memos`** — List the most recent voice memos with timestamps.  Sample phrases: `list memos` / `list voice memos` / `show memos`.
- **`play_last_memo`** — Play the most recently recorded voice memo.  Sample phrases: `play last memo` / `play last voice memo` / `last memo chalao`.
- **`play_memo`** — Play a memo by partial filename match (e.g. timestamp prefix).  Sample phrases: `play memo` / `play voice memo` / `memo chalao`.
- **`record_voice_memo`** — Record a short voice memo via the mic (default 10s, max 120s). Saved as WAV under data/notes/audio/.  Sample phrases: `record voice memo` / `voice memo record karo` / `record memo`.
- **`stop_voice_memo`** — Stop an in-progress voice memo recording.  Sample phrases: `stop voice memo` / `stop recording` / `memo stop karo`.

#### Voice Tuning — `skills/voice_tuning.py` (6 skills)

- **`voice_faster`** — Speed up the TTS voice by one step (~25 wpm).  Sample phrases: `speak faster` / `speed up voice` / `voice fast karo`.
- **`voice_louder`** — Increase TTS voice volume by one step.  Sample phrases: `speak louder` / `louder voice` / `voice loud karo`.
- **`voice_reset`** — Restore TTS voice rate and volume to defaults (175 wpm, 100%).  Sample phrases: `reset voice` / `voice reset karo` / `voice defaults`.
- **`voice_slower`** — Slow down the TTS voice by one step (~25 wpm).  Sample phrases: `speak slower` / `speak more slowly` / `slow down voice`.
- **`voice_softer`** — Decrease TTS voice volume by one step.  Sample phrases: `speak softer` / `softer voice` / `voice low karo`.
- **`voice_status`** — Report current TTS voice rate + volume.  Sample phrases: `voice status` / `current voice settings` / `voice settings`.

#### Volume Control — `skills/volume_control.py` (4 skills)

- **`volume_down`** — Decrease system volume by ~10%.  Sample phrases: `volume down` / `volume kam karo` / `softer`.
- **`volume_mute`** — Mute or unmute system audio.  Sample phrases: `mute` / `mute karo` / `unmute`.
- **`volume_set`** — Set system volume to an absolute percentage.  Sample phrases: `volume 50` / `volume 50 percent` / `volume set to 30`.
- **`volume_up`** — Increase system volume by ~10%.  Sample phrases: `volume up` / `volume badhao` / `louder`.

#### Weather — `skills/weather.py` (1 skill)

- **`real_weather`** — Live weather for a city (defaults to user's stored location or Delhi).  Sample phrases: `real weather batao` / `actual weather kya hai` / `live weather X`.

#### Weather for City — `skills/weather_for_city.py` (1 skill)

- **`weather_for_city`** — Weather + today's forecast for a named city (Open-Meteo).  Sample phrases: `weather in` / `weather for` / `weather at`.

#### Web Jumps — `skills/web_jumps.py` (5 skills)

- **`google_jump`** — Open Google search for the spoken query (or google.com if blank).  Sample phrases: `google` / `google search` / `open google`.
- **`maps_jump`** — Open Google Maps for the spoken location or directions.  Sample phrases: `maps` / `open maps` / `maps kholo`.
- **`translate_jump`** — Open Google Translate (with the spoken phrase pre-filled if any).  Sample phrases: `translate` / `google translate` / `open translate`.
- **`wikipedia_jump`** — Open Wikipedia article for the spoken topic.  Sample phrases: `wikipedia` / `wiki` / `open wikipedia`.
- **`youtube_jump`** — Open YouTube search results for the spoken query.  Sample phrases: `youtube` / `open youtube` / `youtube kholo`.

#### Web Search — `skills/web_search.py` (3 skills)

- **`clear_search_cache`** — Clear the local web-search knowledge cache.  Sample phrases: `clear search cache` / `knowledge cache clear karo` / `search cache wipe karo`.
- **`search_cache_stats`** — Show how many web searches are cached locally and the most recent ones.  Sample phrases: `search cache stats` / `kitne searches cache mein hain` / `cached searches dikhao`.
- **`web_search`** — Search the web online, summarize the top results in Hinglish, and cache the answer locally for instant recall later.  Sample phrases: `search online` / `search online ai` / `search online for ai`.

#### WhatsApp — `skills/whatsapp.py` (1 skill)

- **`send_whatsapp`** — Send a WhatsApp message to a saved contact (resolves name → phone via data/contacts.json).  Sample phrases: `whatsapp pe X ko bolo Y` / `X ko whatsapp message bhejo Y` / `send whatsapp to X saying Y`.

#### Whisper STT — `skills/whisper_stt_skill.py` (5 skills)

- **`stt_prefer_google`** — Mark Google as the preferred STT backend (default).  Sample phrases: `use google for stt` / `prefer google stt` / `switch stt to google`.
- **`stt_prefer_whisper`** — Mark Whisper as the preferred STT backend in settings.  Sample phrases: `use whisper for stt` / `prefer whisper` / `whisper se sunoo`.
- **`whisper_set_model`** — Switch Whisper model size — tiny/base/small/medium/large-v3.  Sample phrases: `set whisper model` / `whisper model set karo` / `use whisper tiny`.
- **`whisper_status`** — Report Whisper STT availability and current model size.  Sample phrases: `whisper status` / `is whisper available` / `whisper stt status`.
- **`whisper_transcribe_once`** — Record ~4 seconds of audio and transcribe via Whisper.  Sample phrases: `whisper transcribe` / `transcribe with whisper` / `whisper se transcribe karo`.

#### Window Manager — `skills/window_manager.py` (8 skills)

- **`show_desktop`** — Minimize all windows (Win+D).  Sample phrases: `show desktop` / `desktop dikhao` / `minimize all`.
- **`window_close`** — Close the active window (sends WM_CLOSE).  Sample phrases: `close window` / `close this` / `band karo window`.
- **`window_maximize`** — Maximize the active window.  Sample phrases: `maximize window` / `maximize` / `full screen window`.
- **`window_minimize`** — Minimize the active window.  Sample phrases: `minimize window` / `minimize` / `hide window`.
- **`window_snap_bottom`** — Snap the active window to the bottom half of its monitor.  Sample phrases: `snap bottom` / `window bottom` / `bottom half`.
- **`window_snap_left`** — Snap the active window to the left half of its monitor.  Sample phrases: `snap left` / `window left` / `left half`.
- **`window_snap_right`** — Snap the active window to the right half of its monitor.  Sample phrases: `snap right` / `window right` / `right half`.
- **`window_snap_top`** — Snap the active window to the top half of its monitor.  Sample phrases: `snap top` / `window top` / `top half`.

#### Windows Power Utils — `skills/windows_power_utils.py` (5 skills)

- **`summarize_window`** — Copy the active app's name and window title to clipboard.  Sample phrases: `summarize window` / `what window am i on` / `what app is open`.
- **`wallpaper_set`** — Set the Windows desktop wallpaper from a file path or a fuzzy name (looks under Pictures).  Sample phrases: `set wallpaper` / `change wallpaper` / `set my wallpaper to`.
- **`whoami_info`** — Quick identity: username, hostname, local IP, OS, uptime.  Sample phrases: `whoami` / `who am i` / `system identity`.
- **`window_pin_top`** — Make the foreground window always-on-top (Win32 HWND_TOPMOST).  Sample phrases: `pin window` / `pin this window` / `always on top`.
- **`window_unpin_top`** — Remove always-on-top from the foreground window.  Sample phrases: `unpin window` / `unpin this window` / `remove always on top`.

#### Workspace Tracker — `skills/workspace_tracker_skill.py` (6 skills)

- **`workspace_clear`** — Wipe the workspace tracker's rolling event buffer.  Sample phrases: `workspace clear` / `clear workspace history` / `wipe workspace tracker`.
- **`workspace_recent`** — Show the last 10 foreground-app switches.  Sample phrases: `workspace recent` / `recent app switches` / `what apps did i switch to`.
- **`workspace_summary`** — Summarise the last hour of foreground app usage.  Sample phrases: `workspace summary` / `what have i been doing` / `kya kya kaam kiya is hour`.
- **`workspace_summary_today`** — Summarise the last 24 hours of app usage.  Sample phrases: `workspace summary today` / `aaj kya kiya` / `today's workspace`.
- **`workspace_track_off`** — Stop the workspace tracker (keeps buffered events).  Sample phrases: `workspace track off` / `stop workspace tracking` / `stop watching workspace`.
- **`workspace_track_on`** — Start the autonomous workspace tracker (polls foreground app every 30 s, builds a usage timeline).  Sample phrases: `workspace track on` / `start workspace tracking` / `track workspace`.


---

## 7. Memory, Learning & The Brain Stack

AERIS has **four** distinct memory systems, each with a different job:

| System | What it remembers | Backed by |
|---|---|---|
| **Conversation history** | Last N turns of (user, assistant) for context. | `core/conversation.py`, in-RAM, dumped to `data/conversation.json` on exit. |
| **Semantic memory** | Past user utterances indexed by embedding so you can ask "what did I say about X?" | `core/memory.py` + `data/semantic_memory.npz`. |
| **Knowledge graph** | Hand-curated facts ("Sara is my sister", "I work at Acme"). | `core/kg_memory.py` + `data/knowledge_graph.json`. |
| **Response cache** | Past LLM-generated reply variants so greetings stay fresh, never repeat. | `core/response_enricher.py` + `data/response_cache.json`. |

On top of that there is **implicit learning via the feedback bandit**:

1. Every reply gets an implicit reward (you said "no" → negative; you said
   "yes, that's right" → positive; you re-issued the same command differently
   → negative).
2. The signal lands in `data/feedback_log.sqlite`.
3. An offline retraining script consumes the log and updates the neural
   classifier's pattern-to-intent labels.

The intent classifier itself is a **two-stage hybrid**:

- **Stage 1**: sentence-transformer (`paraphrase-multilingual-MiniLM-L12-v2`)
  encodes the user utterance → 384-d vector. A small MLP head maps it to one
  of the registered intent IDs. Confidence is the softmax max.
- **Stage 2**: k-NN over the labelled-pattern corpus catches everything the
  MLP wasn't trained on. The two are blended with confidence weights.
- **Exact-match fast path** sits in front of both; if the utterance hashes to
  a known pattern verbatim, we skip the whole neural pipeline.
- **LRU cache** wraps the brain so repeated utterances are O(1).
- **LLM chat fallback** kicks in only when confidence is below threshold AND
  the user explicitly opted in via `enable smart replies`.

---

## 8. Gesture + Vision Subsystem

The camera is shared by three consumers via `core/vision_engine.py`:

```
camera frames ─┬─► face_gate (InsightFace embeddings)
               ├─► gesture_engine (MediaPipe hands)
               └─► auto_label (YOLOv8n object detection)
```

Built-in gestures (configurable in `data/settings.json` under `gesture_bindings`):

- **Pinch (index + thumb)** → left-click (only in cursor mode)
- **Two-finger pinch** → scroll
- **Peace sign** → screenshot (rebindable)
- **Fist** → pause-everything
- **Open palm hold (2 s)** → "wake" AERIS

You can record arbitrary new gestures with `record gesture <name>` and bind
them to any skill with `bind <gesture> to <skill>`.

The **face gate** means only enrolled masters can fire gestures. The
**permissions matrix** (`ui/permissions_editor.py`) lets you say "only allow
Shivang to use lock_screen; everyone else gets kid_mode".

The **presence detector** auto-pauses the gesture loop the moment no face is
detected for 5 seconds, and resumes when you return — so a passer-by's
silhouette doesn't trigger anything.

---

## 9. Data Files & Where State Lives

```
data/
├── settings.json                  # User preferences, gesture bindings, voice tuning
├── intents.json                   # Pattern → intent labelled corpus
├── entities.json                  # Entity slot vocab
├── feedback_log.sqlite            # Bandit reward signals
├── semantic_memory.npz            # Vector store for conversation recall
├── knowledge_graph.json           # Subject-predicate-object triples
├── conversation.json              # Rolling N-turn buffer (on-exit dump)
├── chains.json                    # Cross-skill chains
├── routines.json                  # Automation routines
├── macros.json                    # Voice macros
├── face_registry_insight.json     # InsightFace enrollments
├── custom_gestures.json           # Trained custom gestures
├── response_cache.json            # NEW — enricher cache (per-slot)
├── workspace_events.json          # Foreground-app timeline
├── scratch.md                     # Quick-note dump
├── notes/journal.md               # Append-only journal
├── notes/audio/                   # Voice memo WAVs
├── plugins/                       # Third-party plugins
├── snapshots/                     # Object-detection saved frames
├── audio_cache/                   # TTS pre-renders for repeated phrases
├── logs/                          # Structured JSON-line logs (rotated)
└── models/                        # Local model files (YOLO, InsightFace, Whisper, etc.)
```

Every JSON write goes through `core/atomic_io.py` — `tmp → fsync → rename` —
so a crash mid-write can never corrupt your settings.

---

## 10. Tests & CI Health

- **39 test files** under `tests/`.
- ~950 tests pass cumulatively across the tier 1–8 loop.
- Latest dedicated suites:
  - `test_response_enricher.py` — 13 tests; cache round-trip, LLM stubbing,
    non-repeat ordering, skill wiring for `greeting` and `ActionExecutor.greet`.
  - `test_tier1_phase1.py` … `test_tier8.py` — one suite per roadmap tier.
  - `test_iter1_skills.py` … `test_iter9_voice_perms.py` — one suite per
    feature iteration.

Run everything:

```powershell
python -m pytest -q
```

Run just one:

```powershell
python -m pytest tests/test_response_enricher.py -v
```

---

## 11. Current Scenario — What's Working Right Now

**Boot path** (verified end-to-end):

1. `run_gui.py` launches → splash shows progress → torch loads on main
   thread (avoids the Windows + PyQt5 + sentence-transformers DLL crash
   pattern documented in memory).
2. `JarvisV31Window` constructs; the Ctrl+Shift+P palette shortcut
   registers; the animation bus starts paused.
3. Brain worker thread initialises in the background → emits `brain_ready`
   → `_on_brain_ready` resumes the animation bus + unlocks chat input.
4. `data/logs/aeris.log` shows `[main_window] _on_brain_ready: done`.
5. `/health` reports `brain_ready: true`. Tray icon goes from grey to live.

**Verified live flows**:

- Saying **"hi" / "hello" / "good morning"** routes to `greeting` at
  confidence ~0.92. With the response enricher ON and Ollama reachable, the
  reply is now varied and cached so it never repeats the same phrasing twice
  in a row. Offline, it falls back to the original template.
- **`Ctrl+Shift+P`** opens the command palette, fuzzy-searches across all 338
  skills, executes on Enter.
- **Gesture mode on** → `cursor mode on` → pinch-click works against any
  Windows window; face gate enforces master allowlists.
- **Telemetry dashboard** shows live gesture / skill / workspace counts.
- **First-run wizard** completes face enroll → voice enroll → theme select →
  diagnostics → success.

**Recent feature deliveries** (this session and previous loop iterations):

- Tier 1 → 8 of the long-picture roadmap (~106 new skills, ~22 new core
  modules, ~9 new UI dialogs, plugin loader, doc-QA, KG, voice ID, face gate
  + permissions matrix, gesture practice + custom gestures, telemetry,
  workspace tracker, automation engine, settings schema migration, dep
  validator, regen docs, first-run wizard).
- **Response enricher** (today) — LLM-backed reply variation with on-disk
  cache, persistent toggle, voice surface (`enrich_responses_on/off`,
  `enrich_cache_clear`, `enrich_status`), wired into `greeting` and
  `executor.greet`. 13 new tests, all green.

---

## 12. Things of Appreciation

These are the parts that punch well above their weight — worth being proud
of.

- **The hybrid brain.** Most "voice assistant" projects either go pure
  rule-based (rigid) or pure LLM (slow, expensive, repetitive). AERIS is a
  layered system where 338 hand-written skills handle the long tail in
  milliseconds and the LLM is reserved for the conversational glue. The
  exact-match fast path + LRU cache make trivial commands instant.

- **Hinglish-first design.** Patterns like `agla gaana chalao`,
  `is mahine kitna kharcha`, `screen padho` aren't translations bolted on
  later — they're first-class triggers right next to their English
  equivalents. The TTS defaults to `en-IN-NeerjaNeural` for the same reason.

- **Three-tier TTS resilience.** `edge-tts → pyttsx3 → SAPI5 via COM`. If
  Microsoft's voice cloud is down, you still get speech. If pyttsx3's COM
  bindings break (they sometimes do on Windows updates), the raw SAPI5 COM
  path still works.

- **The atomic IO discipline.** Every persistent writer in the project routes
  through `core/atomic_io.py`. You will not corrupt your settings.json by
  pulling the power cord.

- **The face-gate + permissions matrix.** This is the feature most personal
  assistants don't even attempt. A spouse, kid, or houseguest sitting in
  front of the camera gets a different gesture allowlist — and the matrix
  has a UI, not just a JSON file.

- **The plugin loader.** Drop a folder under `data/plugins/<name>/` with a
  manifest, and you get a fully isolated, hot-reloadable third-party skill.

- **The single-instance + graceful-shutdown + crash-beacon trio.** A second
  `run_gui.py` exits politely. Ctrl+C drains pending work. If we *did*
  crash last run, the beacon detects it and writes a faulthandler dump that
  you can read.

- **The structured logs + health server.** `data/logs/aeris.log` is JSON
  lines. `127.0.0.1:8765/health` is a real liveness endpoint. This is
  observability you'd expect from a server, not a desktop app.

- **The skill catalogue itself.** 338 skills covering app launching, browser
  control, clipboard, expenses, knowledge graph, vault, voice memos, voice
  cloning, OCR, gestures, screen reading, weather, dictionary, file
  operations, system power, focus mode, pomodoro, journal, automation —
  hand-tuned with English + Hinglish patterns each.

- **The continual-learning loop.** Most assistants don't ship one. Yours
  does: feedback bandit → SQLite → offline retrain → new neural weights.

- **The response enricher** (today's addition). One small module that turns
  every stock template into a varied, cached, never-repeats reply — with a
  clean offline fallback. The pattern can be extended to any other template
  in the codebase: pass through `enriched_reply(slot, base, hint)`.

---

## 13. Improvements & Next Steps

Honest list of "what's a bit rough" and "what's not yet done":

### 13.1 Hygiene

- **Working tree.** ~26 modified + ~110 untracked files sitting on `main`
  uncommitted. The whole tier 1–8 loop + enricher is one big checkpoint
  away. **Recommendation:** split into logical commits (tier-per-tier),
  push, then continue iterating.
- **`README_OLD.md`** has been auto-backed-up as part of this rewrite. Once
  you're happy with the new README, delete the old one.

### 13.2 Correctness / robustness

- The **legacy `core/executor.py` dispatch dict** is now only partially used
  (most intents route through the skill registry). Worth auditing what's
  still needed and deleting the rest, so there's one canonical dispatch path.
- The **brain's k-NN labelled corpus** is in `data/intents.json` — but it
  hasn't been regenerated against the live 338-skill registry recently. Run
  `regenerate_skill_docs` *and* a corpus rebuild after large skill batches.
- **Whisper STT** is wired but defaults to Google STT. Whisper is more
  accurate for Hinglish; consider making it the default once the local model
  download is small enough (`tiny` or `base`).
- **GPU offload** is wired but not auto-detected — you have to flip the
  toggle. A "detect CUDA on first run, ask the user" UX would be nicer.

### 13.3 Coverage gaps

- **No tests** for the gesture pipeline beyond unit-level. A scripted
  "fake-frame" replay rig that drives `gesture_engine.py` from a fixture
  video would catch regressions.
- **No tests** for the TTS three-tier fallback chain. Mocking each backend
  to fail in sequence + asserting the next one is reached would be cheap and
  high-value.
- **No tests** for `core/main_engine.py` orchestration — the big lump where
  brain → registry → enricher → TTS get wired together. Even a smoke test
  ("send 'hi' → assert TTS got called with a non-empty string") would help.

### 13.4 UX

- The **chat panel** does not yet show *which* skill fired. A small chip
  ("greeting · enriched · 12 ms") under each reply would make debugging the
  brain trivially easier.
- **No global "undo last action"** for destructive skills (`window_close`,
  `kill_process`, `forget_command`). A 5-second undo toast would prevent a
  lot of "wait no" moments.
- **The first-run wizard** doesn't currently verify Ollama is reachable.
  Adding that check (with a "skip — I'll set it up later" branch) would let
  the user know the LLM fallback won't fire yet.
- **The settings panel** edits only ~20 of the ~80 known settings keys.
  Either expand it to cover the rest or document which keys are
  intentionally "advanced — JSON only".

### 13.5 Performance

- The **brain warm-up** still takes 4–7 seconds on a cold start because we
  load sentence-transformer + the InsightFace model serially. They could
  load in parallel (different threads, careful about the torch-on-main rule)
  and shave 2–3 seconds.
- The **vision engine** wakes the camera lazily but doesn't release it after
  N seconds of no subscribers. A "release after 30 s idle" timer would let
  the webcam LED turn off when nothing wants frames.
- **TTS edge-tts** currently re-synthesises common phrases ("Yes sir.",
  "Done.") every time. The `data/audio_cache/` is already there — wire it
  up so identical short phrases get replayed from disk.

### 13.6 Features worth adding next

- **A scheduled-routines UI.** `data/routines.json` is editable by voice but
  there's no dialog to see "what fires at 9am Monday?"
- **A "what did you change?" diff skill.** After a tier of loop iterations,
  you'd love to ask AERIS itself: "summarise everything you added in the
  last 24h". The structured logs already record the data.
- **Wake-word retraining.** "Hey AERIS" is the default but it's not yours.
  Recording 30 utterances and fine-tuning a small wake-word model would
  remove the need for the open-palm fallback.
- **Mobile-side companion.** The phone bridge exists; a tiny PWA that hits
  `/skills` and renders buttons would turn any phone into a remote.
- **Multi-user voice ID at routing time.** Voice ID exists but isn't wired
  into the permissions gate yet — currently only the face gate enforces
  master ID. Adding voice as a second-factor gate would close the loop.

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| GUI freezes on splash | torch DLL conflict with sentence-transformers when imported off-main-thread. | Make sure `run_gui.py` is the entry point — it pre-imports torch on the main thread. See memory `feedback_torch_qt_dll.md`. |
| "intent greeting missing" | Stale brain index — `data/intents.json` doesn't have the pattern. | Restart the GUI; if the rebuild is needed, delete `data/models/intent_index.pkl` so it regenerates on next boot. |
| Left panel paused, no animation | `_anim_bus.resume()` didn't run — typically a brain-ready failure. | Tail `data/logs/aeris.log` for `_on_brain_ready: done`. If absent, check the traceback above it. |
| `NameError: 'log' is not defined` in `main_window.py` | Edit was made with a bare `log.info()` instead of `_log.getLogger(__name__).info()`. | Already fixed; use the `_log = logging.getLogger(__name__)` pattern when adding new logging. |
| Whisper not available | The `large-v3` model can be ~3 GB; falls back to Google. | `whisper_set_model tiny` to switch to a 75 MB model. |
| Camera doesn't release | Vision engine has live subscribers (gesture, auto-label, AR overlay). | `gesture mode off`, `auto label off`, `ar overlay off`. |
| TTS silent | edge-tts hit a 429 rate limit. | It will fall through to pyttsx3; check `data/logs/aeris.log` for the tier switch. |
| `_skill_dump.json` / `_skill_blocks.md` / `_skill_md.txt` / `_core_md.txt` exist at the repo root | Intermediates from the README generator. | Safe to delete. They're regenerated whenever the README is rebuilt. |

---

*This README was generated by walking the live skill registry — every name,
description, and sample phrase here came from `core.skill_registry.all_skills()`
at the time of writing. To regenerate it after a feature push, ask AERIS
itself: `regenerate skill docs` (which updates `docs/SKILLS.md`), then
rebuild this file by hand from the new dump.*
