# AERIS — The Complete, Deeply-Detailed README

> **A.E.R.I.S.** — *Adaptive Engine for Reasoning, Intelligence & Speech*
>
> A fully local, Hinglish-native, **voice- and gesture-driven** desktop assistant
> for Windows, built from scratch in Python with a PyQt5 GUI. It behaves like a
> personal *JARVIS*: you talk to it, gesture at it, and it sees your screen, knows
> who you are, remembers what you tell it, learns from your corrections, and drives
> your machine through **~338 hand-written skills** — with a local LLM (Ollama)
> only handling the conversational glue.

This README is written to be **exhaustive**. For every subsystem, every skill
family, every automation type, and every GUI control, it answers three questions:

1. **What is it?** — what the thing does.
2. **Why is it built this way?** — the design rationale, the trade-off, the problem it solves.
3. **What are the other possibilities?** — how it could be extended, alternative
   implementations, and ideas you could bolt on next.

If you only want the flat "list of every command," jump to
[§10 — The Full Skill Catalogue](#10--the-full-skill-catalogue-all-338-skills).

> 📖 **Complete command reference with examples:** see
> **[`docs/COMMANDS.md`](docs/COMMANDS.md)** — an auto-generated catalogue of
> **all 587 abilities**, grouped into 19 categories, with **20+ example phrases
> per command** (Hinglish + English). Regenerate it anytime after adding skills
> with `python gen_commands_readme.py`.

---

## Table of Contents

**Part I — The Big Picture**
1. [Why AERIS Exists — Motivation & Philosophy](#1-why-aeris-exists--motivation--philosophy)
2. [How It's Made — Tech Stack & Design Principles](#2-how-its-made--tech-stack--design-principles)
3. [Architecture — How Every Piece Fits Together](#3-architecture--how-every-piece-fits-together)
4. [Quick Start & Boot Sequence](#4-quick-start--boot-sequence)

**Part II — The Engine Room**
5. [The Brain — Intent Understanding (Why Hybrid, Other Possibilities)](#5-the-brain--intent-understanding)
6. [Memory & Continual Learning](#6-memory--continual-learning)
7. [Voice I/O — STT & TTS](#7-voice-io--stt--tts)
8. [Vision, Gesture, Face & Presence](#8-vision-gesture-face--presence)
9. [Automations — Routines, Chains, Macros (Why + Possibilities)](#9-automations--routines-chains--macros)

**Part III — The Skills**
10. [The Full Skill Catalogue — All 338 Skills](#10--the-full-skill-catalogue-all-338-skills)
11. [Skills by Theme — Why Each Family Exists & Other Possibilities](#11-skills-by-theme--why-each-family-exists--other-possibilities)

**Part IV — The Interface**
12. [The GUI — Every Panel, Page & Control Explained](#12-the-gui--every-panel-page--control-explained)

**Part V — Operations**
13. [Data, State & Where Everything Lives](#13-data-state--where-everything-lives)
14. [Observability, Safety & Resilience](#14-observability-safety--resilience)
15. [Privacy & Security Model](#15-privacy--security-model)
16. [Tests & Health](#16-tests--health)
17. [Roadmap & Other Possibilities (Project-Wide)](#17-roadmap--other-possibilities-project-wide)
18. [Troubleshooting](#18-troubleshooting)

---

# Part I — The Big Picture

## 1. Why AERIS Exists — Motivation & Philosophy

### 1.1 The problem it was built to solve

Most "AI assistants" today fall into one of two buckets, and **both are unsatisfying** for a
power user who lives on their laptop:

- **Cloud voice assistants** (Alexa/Siri/Google Assistant): they can't drive your
  *desktop*. They can't lock your screen, snap a window, mute Chrome specifically,
  read the text on your screen, or commit your git repo. They send everything to a
  server. And they don't speak natural **Hinglish**.
- **Chat LLMs in a window** (ChatGPT-style): brilliant conversationalists, but they
  are *slow* for trivial actions, *expensive* per token, *repetitive* in phrasing,
  and — critically — they can't actually *do* things on your OS unless you wire up
  tools yourself.

**AERIS is the third option:** a *hybrid symbolic-and-neural agent* that runs
entirely on your own machine, where **338 hand-written skills** handle the long tail
of concrete desktop actions in milliseconds, and a **local LLM** is reserved only for
the conversational glue and the occasional free-form request. It is a JARVIS you own.

### 1.2 The five design principles

Everything in this codebase can be traced back to five commitments:

| Principle | What it means in practice | Where you see it |
|---|---|---|
| **Local-first** | No cloud call in the *default* path. STT can be offline (Vosk/Whisper), TTS falls back to offline, the LLM is your own Ollama, memory/vault are on-disk. Cloud bits (web search, Outlook, Spotify, Sheets) are opt-in. | `core/llm_chat.py` → localhost Ollama; `core/vault.py` → DPAPI; §15 |
| **Hinglish-native** | Hindi/English code-switching is a first-class input, not a bolt-on translation. `spotify pe arijit chala do` is a real trigger sitting next to its English twin. | Every `skills/*.py` pattern list; TTS default `en-IN-NeerjaNeural` |
| **Fast for the common case** | 95% of what you say is a simple command. Those must be instant, not a 2-second LLM round-trip. | Exact-match fast path + LRU cache in `core/brain.py` |
| **Resilient / never-corrupt** | A desktop app crashes, loses power, hits a rate limit. AERIS must degrade gracefully and never destroy your data. | `core/atomic_io.py`, 3-tier TTS, crash beacon, single-instance guard |
| **Observable like a server** | You should be able to see *what it's doing* — structured logs, a health endpoint, a telemetry dashboard, a crash dump. | `core/health_server.py`, `core/telemetry.py`, `data/logs/` |

### 1.3 Why "skills + LLM," not "just an LLM"

This is the single most important architectural decision, so it's worth stating the
*why* plainly:

- **Latency:** "what's my battery" through a skill is ~5 ms. Through an LLM it's
  1–3 s and needs the model loaded.
- **Determinism:** `lock_screen` must lock the screen *every time*, not "usually,
  depending on how the model felt about your phrasing."
- **Cost & offline:** skills cost nothing and work with no model at all.
- **Debuggability:** when a skill misfires you can read 40 lines of Python. When an
  LLM misfires you're staring at weights.

The LLM still matters — it's the fallback for anything the 338 skills don't cover,
*and* it can itself call skills as tools (see `ask_jarvis`). So you get determinism
where you want it and open-ended reasoning where you need it.

**Other possibilities (project-level):** the same skill-registry pattern could be
exposed as an **MCP server** so any external LLM (Claude, GPT) could drive AERIS as a
tool provider; or the neural brain could be swapped for a small **on-device fine-tuned
router** to remove even the sentence-transformer dependency.

---

## 2. How It's Made — Tech Stack & Design Principles

### 2.1 The stack, layer by layer

| Layer | Technology | Why this choice / other possibilities |
|---|---|---|
| **GUI** | PyQt5 (frameless custom window, glass panels, animated reactor) | PyQt5 gives native Win32 window handles (needed for always-on-top, snapping, HWND tricks) and a real event loop. *Other possibilities:* the `new_gui_latest/` folder holds a **React/Tauri** re-skin (JSX prototypes jv3→jv6) that could replace PyQt5 with a web front-end talking to the health server. |
| **Speech-to-text** | `SpeechRecognition` (Google en-IN) default; `vosk` offline + wake word; `faster-whisper` optional | Google is accurate + zero-setup; Vosk gives a fully offline wake-word path; Whisper is the most accurate for Hinglish. Three backends = graceful degradation. |
| **Text-to-speech** | `edge-tts` → `pyttsx3` → SAPI5-via-COM (3-tier) | Edge neural voices sound human and support Indian accents; if Microsoft's cloud 429s, pyttsx3 works offline; if pyttsx3's COM bindings break on a Windows update, raw SAPI5 still speaks. |
| **Intent brain** | `sentence-transformers` (paraphrase-multilingual-MiniLM-L12-v2) + `scikit-learn` k-NN + optional `transformers` XLM-R head + `rapidfuzz` | Multilingual encoder handles Hinglish embeddings; k-NN is cheap and needs no training; the MLP/XLM-R head adds accuracy; fuzzy is the last-ditch matcher. |
| **LLM chat** | Local **Ollama** over HTTP (`requests`) | Local, private, free, swappable model. *Other possibilities:* point the same client at LM Studio, llama.cpp server, or a remote API by changing one base URL. |
| **Vision** | `opencv-python` + `mediapipe` (hands) + `ultralytics` YOLOv8n (objects) + InsightFace (faces) | MediaPipe is fast landmark tracking; YOLO for object labels; InsightFace for identity. |
| **Scheduling** | `apscheduler` + an in-process 30 s tick | Real cron-style reminders and routine triggers. |
| **Crypto** | Windows **DPAPI** (via `cryptography`/`pywin32`) | Ties secrets to the Windows user account — no master password to manage. |
| **System control** | `psutil`, `pyautogui`, `keyboard`, `pycaw`/`comtypes`, Win32 calls | The muscles: process/CPU/battery, input synthesis, hotkeys, per-app audio, window management. |
| **Persistence** | Plain JSON via atomic writes; SQLite (feedback, knowledge cache); `.npz` (semantic vectors); `.xlsx` (workbook) | Human-readable where it helps, binary where it's dense. |

### 2.2 Recurring design patterns (the "how" of the "how")

These patterns show up everywhere; understanding them once explains most of the code:

- **The `@skill` decorator.** Every skill is a plain function decorated with
  `@skill(name, description, patterns, required_entities=[...])`. On import,
  `core/skill_registry.py` auto-discovers it. This is *why* adding a feature is
  usually "write one function," and *why* the help catalogue and docs can be
  generated from the live registry.
- **Atomic IO everywhere.** No module calls `open(path, 'w')` directly for state;
  they route through `core/atomic_io.py` (`tmp → fsync → rename`). *Why:* pulling the
  power cord mid-write can never corrupt `settings.json`.
- **Lazy optional imports.** Heavy/optional deps (`ultralytics`, `pytesseract`,
  `spotipy`) are imported *inside* the skill, not at module top. *Why:* a missing
  optional dependency disables exactly one skill and nothing else (see the
  `dep_check` skill which reports precisely this).
- **Circuit breakers.** `core/skill_breaker.py` wraps skill calls so a skill that
  throws repeatedly is temporarily "tripped" instead of crashing the loop.
- **Shared, multiplexed camera.** One `cv2.VideoCapture` in `core/vision_engine.py`
  fans frames out to face-gate + gesture + auto-label subscribers. *Why:* Windows
  hates two processes opening the same webcam.
- **Bounded caches.** `core/cache_registry.py` wraps `lru_cache` with a
  memory-pressure responder so caches shrink under RAM pressure.
- **Pub/sub buses.** `core/transcript_bus.py` and `ui/jarvis_v31/animation_bus.py`
  decouple producers (STT engine, animation clock) from consumers (panes, widgets).

### 2.3 By the numbers

| Metric | Count |
|---|---:|
| Voice skills | **~338** |
| Skill modules (`skills/*.py`) | **~100** |
| Core engine modules (`core/*.py`) | **~85** |
| UI modules | **~24** (plus alternate `aeris_v4`, `aeris_v6`, `jarvis_v31` stacks) |
| Test files | **~39** |
| Memory systems | **4** (conversation, semantic, knowledge-graph, response-cache) |
| STT backends | **3** (Google, Vosk, Whisper) |
| TTS tiers | **3** (edge-tts, pyttsx3, SAPI5) |
| Themes | **3** (light, dark, cyber) |

---

## 3. Architecture — How Every Piece Fits Together

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │                          USER INTERFACE (PyQt5)                        │
   │  Main window: sidebar dock · glass chat · reactor orb · logs bar       │
   │  Pages: Home · Conversations · Automations · Brain · Memory · Vision   │
   │         Workbook · System · Settings                                   │
   │  Overlays/dialogs: command palette · settings · telemetry · perms      │
   │         matrix · AR overlay · HUD · first-run & calibration wizards     │
   │  System tray · global hotkey · single-instance lock                    │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                     INPUT PIPELINES                                    │
   │  ┌── Speech ──────────────┐ ┌── Gesture ─────────┐ ┌── Hotkey/GUI ─┐   │
   │  │ STT (Google/Vosk/      │ │ MediaPipe hands +  │ │ tray, global  │   │
   │  │ Whisper) wake-word,VAD │ │ face-gate + perms  │ │ shortcut, text│   │
   │  └────────────────────────┘ └────────────────────┘ └───────────────┘   │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  BRAIN — INTENT ROUTING (core/brain.py)                │
   │  1. Exact-match fast path      (instant, O(1))                         │
   │  2. LRU cache for repeats                                              │
   │  3. Neural intent classifier   (sentence-transformer + MLP/XLM-R)      │
   │  4. k-NN over labelled embeddings                                      │
   │  5. rapidfuzz skill-registry fuzzy fallback                            │
   │  6. LLM chat (Ollama) with tool-use over registered skills            │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  SKILL REGISTRY (core/skill_registry.py)               │
   │  ~100 modules · ~338 skills · each @skill(...) decorated               │
   │  + per-skill circuit breaker · hot-reload on file change               │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                  RESPONSE PATH                                         │
   │  Response enricher (LLM-varied + cached) → TTS (edge → pyttsx3 →       │
   │  SAPI5) → chat panel → animation bus → optional toast → structured log │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │            PERSISTENCE & OBSERVABILITY                                 │
   │  Atomic JSON · settings schema versioning · semantic memory (.npz) ·   │
   │  knowledge graph · DPAPI vault · feedback bandit (SQLite) · structured │
   │  logs · health server (:8765) · crash beacon + dump · telemetry        │
   └──────────────────────────────────────────────────────────────────────┘
```

**Reading the diagram:** input can arrive three ways (speech, gesture, GUI/hotkey);
everything funnels into the brain, which routes to exactly one skill (or the LLM);
the response is enriched, spoken, shown, and logged; and everything durable is
written atomically and observable through the health server.

---

## 4. Quick Start & Boot Sequence

### 4.1 Install & run

```powershell
# 1. Create a venv (Python 3.10 recommended)
cd "New version- 3.0"
py -3.10 -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) pull a local LLM for chat-mode + enrichment
ollama pull llama3.1

# 4. (Optional, better Hinglish STT) install a Whisper model on first use
#    and the spaCy English model:
python -m spacy download en_core_web_sm

# 5. Launch the GUI
python run_gui.py
```

Other entry points: `python main.py` (headless/voice loop), `python run_aeris_v6.py`
(the alternate v6 UI), `python run_gesture_tester.py` (gesture debugging rig).

### 4.2 What happens on boot (and *why* the order matters)

The boot order in `run_gui.py` is not arbitrary — every step fixes a real Windows
failure mode:

1. **`torch` is imported *before* PyQt5.** *Why:* some PyTorch + PyQt5 combos throw
   `WinError 1114` (a DLL init failure) when torch loads after Qt has loaded its CRT
   DLLs, or when torch loads on a worker thread. Importing torch first, on the main
   thread, dodges it. (`KMP_DUPLICATE_LIB_OK=TRUE` also silences the duplicate OpenMP
   DLL clash between torch and Qt.)
2. **Single-instance lock acquired** before anything is painted — a second
   `run_gui.py` sends a focus message to the running copy and exits.
3. **Shutdown handlers + structured logging + crash-dump + crash-beacon installed
   early**, so even a crash during heavy imports still runs cleanup and leaves a
   readable dump.
4. **Splash window shows within ~500 ms** (core widgets only) so Windows marks the
   process "responsive" and never shows a "Python not responding" dialog.
5. **Heavy ML modules pre-imported on the main thread** while the splash animates —
   so the brain's `QThread` worker sees them already in `sys.modules` and pays zero
   import cost (no GIL stutter on the progress bar). If the encoder is already cached,
   `HF_HUB_OFFLINE=1` is set so HuggingFace doesn't hang 30 s pinging hf.co.
6. **Main window builds, brain worker spins up**, and when it emits `brain_ready`,
   the animation bus resumes and the chat input unlocks. `/health` flips to
   `brain_ready: true`.
7. **First-run wizard** (`skills/first_run_skill.py`) walks a new user through face
   enrollment → voice ID → theme → diagnostics.

### 4.3 Everyday shortcuts

- **Ctrl+Shift+P** (or **Ctrl+K**) — command palette (fuzzy launch any of 338 skills)
- **Global hotkey** (configurable) — focus AERIS from anywhere
- **Esc** — cancel current TTS playback
- Say **"hey aeris"** (wake word) or click the dock mic, then speak.

---

# Part II — The Engine Room

## 5. The Brain — Intent Understanding

### 5.1 What it does

When you say something, the brain (`core/brain.py`) must decide: *which of the 338
skills did you mean, with what entities, and if none, should I chat?* It does this in
**six escalating stages**, cheapest first:

| Stage | Mechanism | Why it's here |
|---|---|---|
| 1. **Exact-match fast path** | Hash the normalised utterance; if it's a known pattern verbatim, dispatch in O(1). | Trivial commands ("lock screen") must be instant. |
| 2. **LRU cache** | Wrap the whole brain in a bounded cache keyed on utterance. | Repeats ("volume up" five times) cost nothing after the first. |
| 3. **Neural classifier** | sentence-transformer → 384-d vector → MLP (or XLM-R) head → intent + softmax confidence. | Handles paraphrases and Hinglish it was never given verbatim. |
| 4. **k-NN** | Nearest labelled patterns in embedding space. | Catches intents the MLP head wasn't trained on; cheap to update. |
| 5. **Fuzzy (rapidfuzz)** | String-similarity against every registered skill's patterns. | Last-ditch matcher for typos/ASR slips. |
| 6. **LLM chat** | Ollama, with the skill registry exposed as tools. | Anything the skills don't cover — and it can still *call* a skill. |

Supporting pieces: `core/normalizer.py` (collapse fillers, expand Hinglish forms),
`core/entity_extractor.py` (pull out city/time/person/file/URL/percentage),
`core/time_parser.py` ("tomorrow 5 pm" → absolute datetime),
`core/disambiguator.py` (confidence-aware tie-break when two intents score close),
`core/sentiment.py` (tag every message positive/negative),
`core/tool_router.py` (skill vs LLM-tool vs chat decision).

### 5.2 Why hybrid (not pure-rules, not pure-LLM)

Pure-rules is rigid — it breaks the moment you phrase something a new way. Pure-LLM
is slow, non-deterministic, and can't guarantee `lock_screen` locks. The layered
design gives **determinism + speed for the 95%** and **flexibility for the 5%**, with
each layer only paying its cost when the cheaper layers miss.

### 5.3 Other possibilities

- **Confidence-calibrated abstention:** show the top-3 candidate skills as clickable
  chips when confidence is middling, instead of guessing.
- **Per-user brains:** key the k-NN corpus by the identified speaker (voice ID) so the
  same phrase can mean different things to different masters.
- **On-device fine-tuned router** (distil the sentence-transformer + head into one
  small ONNX model) to cut cold-start from ~5 s to <1 s and drop the torch dependency.
- **Streaming intent:** classify partial STT so the reactor can "lean in" before you
  finish speaking.
- **Tool-use grading:** log which LLM tool-calls the user accepted vs corrected, and
  feed that back into the feedback bandit (§6) to improve routing over time.

---

## 6. Memory & Continual Learning

AERIS has **four distinct memory systems**, each with a different job — a deliberate
separation so "remember this fact forever" and "what did we just talk about" don't
fight over one store:

| System | Remembers | Backed by | Why separate |
|---|---|---|---|
| **Conversation history** | Last N (user, assistant) turns | `core/conversation.py`, RAM → `data/conversation.json` on exit | The LLM's short-term context; cheap, volatile. |
| **Semantic memory** | Every past utterance, indexed by embedding | `core/memory.py` + `data/semantic_memory.npz` | Ask "what did I say about X?" by *meaning*, not keyword. |
| **Knowledge graph** | Curated facts (subject–predicate–object) | `core/kg_memory.py` + `data/knowledge_graph.json` | "Sara is my sister" must be exact and queryable, not fuzzy. |
| **Response cache** | Past LLM reply *variants* | `core/response_enricher.py` + `data/response_cache.json` | Keeps greetings fresh (never repeats phrasing) with offline fallback. |

**Continual learning — the feedback bandit:** every reply gets an *implicit* reward
(you said "no" → negative; "yes, perfect" → positive; you re-issued the command
differently → negative). Signals land in `data/feedback_log.sqlite`. An **offline**
retraining script (`python -m core.train_intent`) consumes them and updates the
classifier. *Why offline:* retraining mid-session would make behaviour
non-reproducible; batching it keeps the live path fast and deterministic.

**Other possibilities:** decay old semantic vectors so memory "forgets" gracefully;
add a *contradiction detector* to the KG ("you said Sara is your sister, now your
cousin — which?"); expose memory as a timeline in the Memory page with delete/pin
controls; encrypt `semantic_memory.npz` at rest for sensitive utterances.

---

## 7. Voice I/O — STT & TTS

### 7.1 Speech-to-text (three backends)

- **Google (`SpeechRecognition`)** — default; accurate, en-IN tuned, zero local setup,
  but needs internet.
- **Vosk** — fully offline; also powers the **wake word** ("aeris") and VAD so the mic
  isn't streaming to anyone until you address it.
- **Whisper (`faster-whisper`)** — the most accurate for Hinglish; model size is
  switchable (tiny → large-v3) to trade accuracy for RAM/latency.

*Why three:* privacy (Vosk), accuracy (Whisper), convenience (Google) are three
different user priorities; the `whisper_*` and `stt_prefer_*` skills let you choose.

### 7.2 Text-to-speech (three tiers)

`edge-tts` (neural, Indian-accented, human-sounding) → `pyttsx3` (offline) → **raw
SAPI5 via COM** (works even when pyttsx3's bindings break). Repeated short phrases
("Done.", "Yes sir.") can be replayed from `data/audio_cache/`. Voice, rate, and
volume are all live-tunable by voice (`voice_tuning.py`, `tts_voice.py`).

**Other possibilities:** local neural TTS (Piper/Coqui) as a fully-offline tier-0;
per-master voices; SSML emotion tags driven by `sentiment.py`; barge-in (stop
speaking the instant you start talking).

---

## 8. Vision, Gesture, Face & Presence

One shared camera (`core/vision_engine.py`) fans frames to three consumers:

```
camera frames ─┬─► face_gate      (InsightFace embeddings → who is this?)
               ├─► gesture_engine  (MediaPipe hands → pinch / peace / fist / custom)
               └─► auto_label      (YOLOv8n → name objects held to camera)
```

- **Built-in gestures:** pinch = left-click (cursor mode), two-finger pinch = scroll,
  peace = screenshot (rebindable), fist = pause-everything, open-palm-hold = wake.
- **Custom gestures:** record any pose (`record gesture <name>`) and bind it to any
  skill (`bind <gesture> to <skill>`).
- **Face gate:** only enrolled *masters* can fire gestures — so a passer-by can't.
- **Permissions matrix:** per-master gesture allowlists ("only Shivang may
  `lock_screen`; the kids get `kid_mode`"), editable in a real grid UI.
- **Presence:** auto-pauses the gesture loop when no face is seen for a few seconds,
  resumes when you return — saves CPU and prevents accidental fires.

**Why:** hands-free control is genuinely useful (dirty hands, presentations,
accessibility), but a webcam pointed at a room is a security surface — hence the
gate + permissions + presence trio.

**Other possibilities:** two-handed gestures; gesture *sequences* (like a combo);
head-pose / gaze control for accessibility; hand-tracking depth via a second camera;
sign-language shortcuts; a "gesture macro recorder" that captures a sequence of poses
into one named action.

---

## 9. Automations — Routines, Chains, Macros

AERIS has **three different automation mechanisms**, and the distinction is
intentional — each answers a different question about *when* things should happen.

### 9.1 Routines (`core/automation.py`, `data/routines.json`) — "**when** X, do a sequence"

A routine = **one trigger** + a list of **sequential actions**. This is the
event-driven workflow engine.

**Triggers** (why each exists):

| Trigger | Fires when | Example use |
|---|---|---|
| `time` (5-field cron) | A cron schedule matches (checked every 30 s) | "8 AM weekdays → open work apps" |
| `battery_below` / `battery_above` | Battery crosses a % on the falling/rising edge | "below 20% → dim + lower volume" |
| `gesture` | A gesture-engine event fires | "three-up gesture → screenshot + journal" |
| `workspace_enter` | The workspace classifier enters a profile (CODING/MEETING/GAMING) | "enter MEETING → mute notifications" |
| `manual` | Only `run_routine(id)` fires it | A named button/voice-only routine |

**Actions:** `notify` (tray toast), `open_app`, `open_url`, `run_skill`, `ai_prompt`
(feed text to the brain), `delay`. *Adding a new action is one method* —
`_action_<kind>()` is auto-discovered by the dispatcher. Threading: triggers run on
their own threads; a fired routine is submitted to a 4-worker pool; actions inside one
routine run sequentially, routines run in parallel; the scheduler is a daemon holding
no locks across sleeps, so process exit is clean mid-routine.

Shipped examples: `morning_workspace` (8 AM weekday setup), `coding_mode` (7 PM IDE +
focus + "continue yesterday's work" AI prompt), `battery_saver` (auto-dim on low
battery), `meeting_mode_auto`.

**Voice surface:** `routine_list/run/enable/disable/status/reload`.

### 9.2 Chains (`core/chain_engine.py`, `data/chains.json`) — "**after** skill X, also do Y"

A chain is a *reactive follow-up*: when a trigger event fires (a gesture name, a skill
name, or `custom:<name>`), it *also* runs the skills in `then`. Example shipped:
`screenshot → append a journal note`; `lock screen → pause music`. *Why separate from
routines:* chains hook the **output** of one action to trigger others without you
scheduling anything — they're glue, not schedules.

**Voice surface:** `chains_on/list/reload/chain_path`.

### 9.3 Macros (`core/*` + `data/macros.json`) — "**run** this saved list now"

A macro is a named, manually-invoked sequence of skills with per-step slot overrides —
a "playlist of commands." Shipped: `morning_routine`, `focus_deep`, `end_of_day`.
*Why separate:* no trigger at all; you say "run macro focus_deep" and it fires the
list. Simplest of the three.

**Voice surface:** `run_macro/list_macros/reload_macros`.

### 9.4 Which one should I use? (and other possibilities)

- **Time/battery/gesture-driven, unattended →** routine.
- **"Whenever this happens, tack on that" →** chain.
- **"I want a named button that does 5 things now" →** macro.

**Other possibilities:** a visual routine *builder* in the Automations page
(drag actions, pick a trigger — the data model already supports it); conditional
actions (`if battery < 20 and unplugged`); routine *templates* shared via the sync ZIP;
location/Wi-Fi-SSID triggers ("on home network → …"); calendar-event triggers via the
Outlook integration; a "dry-run" mode that shows what a routine *would* do.

---

# Part III — The Skills

## 10. The Full Skill Catalogue — All 338 Skills

> This section is auto-generated from the live registry
> (`core.skill_registry.all_skills()`). Each entry shows the **skill name** (what the
> brain routes to), a **one-line description**, and **three sample trigger phrases**
> (English + Hinglish). Regenerate after a feature push with the `regenerate skill
> docs` voice command (updates `docs/SKILLS.md`).

For the *why each family exists and how to extend it*, read
[§11 — Skills by Theme](#11-skills-by-theme--why-each-family-exists--other-possibilities)
alongside this list.

#### Advanced / Meta — `skills/advanced_skills.py` (3)
- **`mood_today`** — Average sentiment of recent messages. *phrases:* `mood today` / `my mood` / `sentiment today`.
- **`ocr_screen`** — OCR the whole virtual screen. *phrases:* `ocr screen` / `read screen` / `what's on my screen`.
- **`scratchpad_summarize`** — Summarise `data/scratch.md` into 3 bullets. *phrases:* `summarize scratch` / `summarise scratchpad` / `scratch summary`.

#### App + Audio Control — `skills/app_audio.py` (4)
- **`app_mute`** / **`app_unmute`** — Mute/unmute a specific app's audio. *phrases:* `mute chrome` / `unmute spotify` / `mute discord`.
- **`app_volume_list`** — List every app producing audio + its volume. *phrases:* `list app volumes` / `app volumes` / `show app audio`.
- **`app_volume_set`** — Set a per-app volume %. *phrases:* `set spotify to 30%` / `set chrome to 50` / `set discord to 20`.

#### AR Overlay — `skills/ar_overlay_skill.py` (3)
- **`ar_overlay_on` / `ar_overlay_off` / `ar_overlay_status`** — Show/hide/report the translucent always-on-top camera preview with YOLO boxes. *phrases:* `ar overlay on` / `hide ar overlay` / `ar status`.

#### Automation & Routines — `skills/automation_skill.py` (6)
- **`routine_list / routine_run / routine_enable / routine_disable / routine_status / routine_reload`** — Manage the routine engine (§9.1). *phrases:* `list routines` / `run morning routine` / `disable battery saver`.

#### Brightness Control — `skills/brightness_control.py` (3)
- **`brightness_up / brightness_down / brightness_set`** — Adjust screen brightness. *phrases:* `brighter` / `dimmer` / `brightness 50`.

#### Browser — `skills/browser_skill.py` (5)
- **`open_in_browser / search_in_browser`** — Open/search in a specific browser (+ profile). *phrases:* `open youtube in brave` / `search ai in chrome`.
- **`list_browser_profiles / set_default_browser / set_default_profile`** — Enumerate & pin browser + profile. *phrases:* `list chrome profiles` / `set default browser brave`.

#### Browser Tabs — `skills/browser_tabs.py` (6)
- **`tab_new / tab_close / tab_next / tab_prev / tab_reopen / tab_switch`** — Full tab control via keystrokes; `tab_switch` accepts digits, ordinals, and Hinglish (pehla/dusra). *phrases:* `new tab` / `close tab` / `tab 3`.

#### Clipboard — `skills/clipboard.py` (2)
- **`clipboard_copy / clipboard_paste`** — Copy text / read clipboard. *phrases:* `yeh copy karo` / `clipboard mein kya hai`.

#### Clipboard Extras — `skills/clipboard_extras.py` (3)
- **`clipboard_open_url / clipboard_say / clipboard_stats`** — Open a URL from clipboard / speak it / count chars-words-lines. *phrases:* `open clipboard url` / `say clipboard` / `clipboard size`.

#### Clipboard History — `skills/clipboard_history.py` (3)
- **`clipboard_history / copy_history_item / clipboard_clear`** — Recent clips captured by the background watcher; re-copy by index; wipe. *phrases:* `clipboard history` / `copy item 2` / `clipboard clear`.

#### Clipboard Image — `skills/clipboard_image.py` (2)
- **`image_to_clipboard / last_screenshot_to_clipboard`** — Put an image / the last screenshot onto the clipboard. *phrases:* `copy image to clipboard` / `copy last screenshot`.

#### Cloud Sync — `skills/sync_skill.py` (4)
- **`sync_export / sync_import / sync_list / sync_default_path`** — Pack/restore all customisations (settings, gestures, voice ID, KG, macros, chains, faces) into a portable ZIP. *phrases:* `sync export` / `sync import` / `what gets backed up`.

#### Code Writer — `skills/code_writer.py` (2)
- **`write_code / list_generated_code`** — Generate a script from a spec (saved under `data/generated_code/`, opened in editor) / list recent snippets. *phrases:* `write me a python script that…` / `show generated code`.

#### Command Palette — `skills/command_palette_skill.py` (1)
- **`open_command_palette`** — Fuzzy-search every skill. *phrases:* `open command palette` / `command palette` / `open palette`.

#### Compute / Math — `skills/compute_skills.py` (6)
- **`quick_math / hash_text / base64_encode / base64_decode / password_generate / qr_code`** — Calculator, SHA-256, base64, strong-password gen, QR PNG. *phrases:* `calculate` / `sha256` / `generate password` / `qr code`.

#### Conversation Recap — `skills/conversation_recap.py` (2)
- **`conversation_recap / conversation_clear`** — Repeat the last N exchanges / wipe the rolling buffer. *phrases:* `recap` / `what did we talk about` / `forget conversation`.

#### Cross-Skill Chains — `skills/chain_skill.py` (4)
- **`chains_on / chains_list / chains_reload / chain_path`** — Manage the chain engine (§9.2). *phrases:* `chains on` / `list chains` / `reload chains`.

#### Custom Gestures — `skills/custom_gestures_skill.py` (4)
- **`gesture_record / gesture_record_status / gesture_list_custom / gesture_unteach`** — Record/list/forget trained poses. *phrases:* `record gesture` / `list custom gestures` / `forget gesture`.

#### Dependency Validator — `skills/dep_validator_skill.py` (2)
- **`dep_check / dep_skills_dark`** — Which optional deps are missing + which skills go dark because of it. *phrases:* `dep check` / `broken skills`.

#### Dev Tools — `skills/dev_tools.py` (10)
- **`git_status / git_branch / git_diff / git_log / git_commit_quick / git_pull`** — Voice git. *phrases:* `git status` / `commit changes` / `git pull`.
- **`open_explorer_here / path_to_clipboard / restart_explorer / todo_today`** — Project-root explorer, copy path, restart shell, unticked TODOs from scratch.md. *phrases:* `open explorer` / `copy path` / `todo today`.

#### Diagnostics — `skills/diagnostics.py` (1)
- **`diagnostics`** — Probe TTS/gesture/vision/brain and report OK/MISSING with fix hints. *phrases:* `diagnose` / `run diagnostics`.

#### Dictionary — `skills/dictionary.py` (3)
- **`define_word / synonyms / antonyms`** — Definitions/synonyms/antonyms (dictionaryapi.dev). *phrases:* `define` / `synonyms of` / `opposite of`.

#### Docs Generator — `skills/docs_gen_skill.py` (1)
- **`regenerate_skill_docs`** — Rebuild `docs/SKILLS.md` from the live registry. *phrases:* `regenerate skill docs`.

#### Document Q&A — `skills/doc_qa_skill.py` (4)
- **`doc_index_folder / doc_query / doc_status / doc_clear`** — Embed a folder of text files and query it semantically. *phrases:* `index folder` / `search docs for` / `doc status`.

#### Expense Tracker — `skills/expense_tracker.py` (5)
- **`add_expense / add_task / add_meeting / month_summary / open_workbook`** — Log spend/tasks/meetings into the local `.xlsx` workbook with auto-category. *phrases:* `spent 500 on food` / `add task write the report` / `is mahine kitna kharcha`.

#### File Finder — `skills/file_finder.py` (2)
- **`find_file / recent_files`** — Fuzzy-find + open across common folders / list 10 most-recent files. *phrases:* `find file` / `recent files`.

#### File Operations — `skills/file_ops.py` (3)
- **`open_file / create_folder / reveal_in_explorer`** — Search-and-open a file / make a folder / open a location. *phrases:* `resume kholo` / `create folder X` / `downloads kholo`.

#### First-Run Wizard — `skills/first_run_skill.py` (1)
- **`open_first_run_wizard`** — Face → voice → theme → diagnostics onboarding. *phrases:* `first run wizard` / `setup wizard`.

#### Focus Mode (Deep) — `skills/focus_mode.py` (3)
- **`focus_deep_on / focus_deep_off / focus_deep_status`** — Close distractions + Windows DND, restore on exit. *phrases:* `deep focus on` / `exit deep focus`.

#### Gesture Calibration — `skills/calibration_skill.py` (1)
- **`start_calibration_wizard`** — Walk every gesture with live detection feedback. *phrases:* `start calibration`.

#### Gesture Core — `skills/gesture_skill.py` (5)
- **`gesture_mode_on / gesture_mode_off / gesture_status / cursor_mode_on / cursor_mode_off`** — Activate gesture control; turn index finger into a mouse (pinch = click). *phrases:* `gestures on` / `cursor mode on`.

#### Gesture Management — `skills/gesture_mgmt.py` (7)
- **`gesture_bind / gesture_unbind / gesture_bindings / what_does_gesture_do / gesture_trace / gesture_trace_clear / gesture_stats`** — Rebind poses to skills; inspect what fired. *phrases:* `bind peace to screenshot_full` / `what does peace do` / `gesture stats`.

#### Gesture Practice — `skills/gesture_practice_skill.py` (3)
- **`practice_gesture / practice_status / practice_stop`** — Timed practice session counting hits. *phrases:* `practice gesture` / `practice status`.

#### Gesture Sensitivity — `skills/gesture_sensitivity.py` (2)
- **`gesture_sensitivity_set / gesture_sensitivity_status`** — very_sensitive…very_relaxed. *phrases:* `gestures more sensitive`.

#### GPU Offload — `skills/gpu_offload_skill.py` (3)
- **`gpu_offload_on / gpu_offload_off / gpu_status`** — Move encoder/YOLO/InsightFace to CUDA (persists). *phrases:* `gpu on` / `cuda status`.

#### Help Catalog — `skills/help_catalog.py` (1)
- **`help_catalog`** — List every skill with an example phrase. *phrases:* `help` / `what can you do` / `kya kar sakte ho`.

#### HUD Overlay — `skills/hud_skill.py` (4)
- **`hud_on / hud_off / hud_move / hud_status`** — Always-on-top status widget. *phrases:* `hud on` / `hud to top right`.

#### Info Lookups — `skills/info_skills.py` (4)
- **`weather_local / currency_convert / date_diff / screen_color_pick`** — Weather (open-meteo), FX convert, days-between, pixel colour under cursor → clipboard. *phrases:* `weather` / `100 usd to inr` / `pick color`.

#### Journal — `skills/journal.py` (3)
- **`note_append / journal_show / journal_path`** — Timestamped rolling journal (`data/notes/journal.md`). *phrases:* `log this` / `show journal`.

#### Knowledge Graph — `skills/kg_skill.py` (5)
- **`kg_remember / kg_query / kg_facts_about / kg_forget / kg_list`** — Store/query facts (§6). *phrases:* `remember that Sara is my sister` / `who is` / `forget about`.

#### Live Transcript — `skills/transcript_skill.py` (4)
- **`transcript_on / transcript_off / transcript_log / transcript_status`** — Real-time STT stream pane. *phrases:* `transcript on` / `recent transcript`.

#### LLM Chat — `skills/llm_chat_skill.py` (2)
- **`ask_jarvis / llm_status`** — Free-form chat (model may auto-fire skills) + LLM health. *phrases:* `ask jarvis` / `llm status`.

#### Log Digest — `skills/log_digest.py` (1)
- **`log_digest_today`** — Summarise today's log by category. *phrases:* `log digest`.

#### Master Users — `skills/master_users.py` (6)
- **`register_face / i_am_master / add_master / remove_master / list_masters / face_gate_status`** — Enroll faces + manage the master list. *phrases:* `register my face` / `i am master` / `list masters`.

#### Memory — `skills/memory_skills.py` (2)
- **`recall / memory_stats`** — Semantic recall + store size. *phrases:* `what did i say about` / `memory stats`.

#### Multi-Monitor — `skills/monitor_swap.py` (2)
- **`monitor_list / monitor_swap`** — List monitors / move active window to next. *phrases:* `list monitors` / `next monitor`.

#### News — `skills/news.py` (1)
- **`news_briefing`** — Headlines summarised in Hinglish (tech/india/business/world). *phrases:* `aaj ki news batao`.

#### Notification Mirror — `skills/notification_mirror.py` (4)
- **`notification_mirror_on / off / status / last_notification`** — Read Windows toasts aloud. *phrases:* `read my notifications` / `last notification`.

#### Object Auto-Label — `skills/auto_label_skill.py` (5)
- **`auto_label_on / off / status / auto_label_speak_on / off`** — Narrate items held to the camera. *phrases:* `auto label on` / `speak labels`.

#### Object Detection — `skills/object_skill.py` (3)
- **`detect_holding / detect_scene / snap_and_save`** — What am I holding / what do you see / save a frame. *phrases:* `what am I holding` / `what do you see`.

#### Outlook Calendar — `skills/outlook_calendar.py` (3)
- **`next_meeting / todays_meetings / this_week_meetings`** — Read the Outlook calendar. *phrases:* `next meeting` / `today's meetings`.

#### Outlook Email — `skills/outlook_email.py` (2)
- **`compose_email / email_draft_blank`** — Open a pre-filled / blank Outlook draft (never auto-sends). *phrases:* `compose email` / `new email`.

#### Per-App Profiles — `skills/per_app_profiles.py` (4)
- **`profile_bind / profile_unbind / profile_list / profile_clear`** — Gesture bindings that apply only when a given app is focused. *phrases:* `in code bind peace to git_status`.

#### Permissions Editor — `skills/permissions_editor_skill.py` (1)
- **`open_permissions_editor`** — The masters × gestures grid. *phrases:* `permissions editor`.

#### Permissions Matrix — `skills/master_permissions.py` (6)
- **`master_grant / master_block / master_allow_all / master_kid_mode / master_permissions_show / master_permissions_clear`** — Per-master gesture allowlists. *phrases:* `kid mode for X` / `grant gesture` / `master permissions`.

#### Phone Bridge — `skills/phone_bridge_skill.py` (3)
- **`phone_pair_on / off / url`** — LAN HTTP server so a phone on the same Wi-Fi can fire skills. *phrases:* `phone pair on` / `phone bridge url`.

#### Plugin Loader — `skills/plugin_skill.py` (5)
- **`plugin_list / plugin_enable / plugin_disable / plugin_load_all / plugin_path`** — Third-party plugins under `data/plugins/`. *phrases:* `list plugins` / `enable plugin`.

#### Pomodoro — `skills/pomodoro.py` (3)
- **`pomodoro_start / pomodoro_status / pomodoro_stop`** — 25/5 cycles, 15-min long break every 4th. *phrases:* `start pomodoro`.

#### Preferences — `skills/preferences.py` (3)
- **`set_preference / get_preference / reset_preferences`** — Name/city/browser/voice etc. → `settings.json`. *phrases:* `set my name to Shivang` / `what's my name`.

#### Presence Detection — `skills/presence_skill.py` (3)
- **`presence_auto_pause_on / off / presence_status`** — Pause gestures when you walk away. *phrases:* `presence auto pause on` / `am i present`.

#### Privacy Mode — `skills/privacy_mode_skill.py` (3)
- **`privacy_mode_on / off / status`** — Hard kill-switch: mic + STT + gesture + camera + auto-label + notifications. *phrases:* `stop listening` / `go private`.

#### Productivity Extras — `skills/productivity_extras.py` (5)
- **`append_note / clipboard_transform / file_search / kill_process / quick_timer`** — Notes, clipboard transforms, file search, process kill, quick timers. *phrases:* `note this` / `uppercase clipboard` / `kill firefox`.

#### Productivity Pack — `skills/productivity_pack.py` (4)
- **`daily_briefing / focus_mode_on / focus_mode_off / smart_paste`** — Personalised briefing; focus mode + pomodoro; reformat clipboard smartly. *phrases:* `good morning` / `focus mode on` / `smart paste`.

#### Quick Calculator — `skills/quick_calc.py` (1)
- **`quick_calc`** — Evaluate a spoken expression. *phrases:* `what is` / `kya hai`.

#### Quick Info — `skills/quick_info.py` (5)
- **`battery_status / current_time / current_date / greeting / clear_chat`** — Battery, clock, date, greeting, clear-chat signal. *phrases:* `battery` / `what's the time` / `hello`.

#### Repeat Last — `skills/repeat_last.py` (1)
- **`repeat_last`** — Re-run the previous command. *phrases:* `repeat` / `repeat last command`.

#### Response Enricher — `skills/response_enricher_skill.py` (4)
- **`enrich_responses_on / off / enrich_cache_clear / enrich_status`** — LLM-varied, cached, never-repeat replies with offline fallback. *phrases:* `enable smart replies` / `enrich status`.

#### Scheduled Lock — `skills/scheduled_lock.py` (3)
- **`lock_after / cancel_lock / lock_status`** — Schedule a screen lock N minutes out. *phrases:* `lock after 5` / `cancel lock`.

#### Screenshot — `skills/screenshot_skill.py` (3)
- **`screenshot_full / screenshot_window / screenshots_folder`** — Whole desktop / active window / open folder. *phrases:* `take a screenshot` / `screenshot window`.

#### Settings Panel — `skills/settings_panel_skill.py` (1)
- **`open_settings_panel`** — GUI editor for the common preferences. *phrases:* `open settings`.

#### Settings Schema — `skills/settings_schema_skill.py` (2)
- **`settings_schema_migrate / settings_schema_status`** — Run migrations / report schema version. *phrases:* `migrate settings`.

#### Sheets Sync — `skills/sheets_sync.py` (2)
- **`sync_to_sheets / sheets_status`** — Push the local workbook to Google Sheets. *phrases:* `sync to google sheets`.

#### Snip OCR — `skills/snip_ocr.py` (2)
- **`snip_and_ocr / full_screen_ocr`** — OCR a region / the whole screen. *phrases:* `snip and read` / `full screen ocr`.

#### Snippets — `skills/snippet_skills.py` (3)
- **`text_expand / text_expand_add / text_expand_list`** — Text-expander snippets to clipboard. *phrases:* `expand sig` / `add snippet`.

#### Spotify Control — `skills/spotify_control.py` (3)
- **`spotify_play_track / spotify_pause / spotify_next`** — Play/pause/skip via Spotify API. *phrases:* `spotify pe X chala do` / `pause the music`.

#### System Health — `skills/system_health.py` (2)
- **`full_system_health / network_check`** — Deep health (battery/CPU/RAM/disk/uptime/top-proc/ping/SSID) + quick network. *phrases:* `full system health` / `wifi name kya hai`.

#### System Power — `skills/system_skills.py` (9)
- **`lock_screen / sleep_pc / restart_pc / shutdown_pc / cancel_shutdown / system_stats / cpu_info / network_status / ping`** — Power + system-info core. *phrases:* `lock screen` / `shutdown` / `system stats`.

#### Teach-Me — `skills/teach_skills.py` (3)
- **`teach_command / forget_command / list_taught`** — Teach new phrases for existing intents. *phrases:* `from now on 'open ide' means open_app`.

#### Telemetry — `skills/telemetry_skill.py` (2)
- **`open_telemetry_dashboard / telemetry_digest`** — Usage stats UI + text digest. *phrases:* `open telemetry` / `usage digest`.

#### Theming — `skills/theme_skill.py` (5)
- **`theme_light / theme_dark / theme_cyber / theme_cycle / theme_status`** — Live theme switching. *phrases:* `dark theme` / `cyber theme` / `next theme`.

#### Timers — `skills/timer_skill.py` (3)
- **`set_timer / list_timers / cancel_timer`** — Countdown timers with toast/beep. *phrases:* `set a 5 minute timer`.

#### Translate — `skills/translate.py` (2)
- **`translate_to_hindi / translate_to_english`** — Quick Hi↔En. *phrases:* `hindi mein translate karo X`.

#### Translator Pro — `skills/translator_skill.py` (3)
- **`translate_to / translate_clipboard / translate_status`** — Any-language translate (LLM/argos/Google). *phrases:* `translate this to French` / `translate clipboard`.

#### TTS Voice — `skills/tts_voice.py` (4)
- **`tts_voice_set / tts_voice_reset / tts_voice_list / tts_voice_status`** — Switch neural voice/accent. *phrases:* `set voice to indian male` / `list voices`.

#### Vault (Secrets) — `skills/vault_skills.py` (4)
- **`vault_store / vault_get / vault_list / vault_delete`** — DPAPI-encrypted secrets; values go to clipboard, never chat. *phrases:* `store secret` / `get secret` / `list secrets`.

#### Vision — `skills/vision.py` (2)
- **`read_screen / click_text`** — OCR the screen / find text and click it. *phrases:* `screen padho` / `click on X`.

#### Voice ID — `skills/voice_id_skill.py` (4)
- **`speaker_enroll / speaker_identify / speaker_list / speaker_forget`** — Speaker signatures from voice. *phrases:* `enroll my voice` / `who's speaking`.

#### Voice Macros — `skills/macros.py` (3)
- **`run_macro / list_macros / reload_macros`** — Saved skill sequences (§9.3). *phrases:* `run macro focus_deep` / `list macros`.

#### Voice Memos — `skills/voice_memo.py` (6)
- **`record_voice_memo / stop_voice_memo / play_last_memo / play_memo / list_voice_memos / delete_last_memo`** — Mic memos → WAV. *phrases:* `record voice memo` / `play last memo`.

#### Voice Tuning — `skills/voice_tuning.py` (6)
- **`voice_faster / voice_slower / voice_louder / voice_softer / voice_reset / voice_status`** — Live TTS rate/volume steps. *phrases:* `speak faster` / `louder voice`.

#### Volume Control — `skills/volume_control.py` (4)
- **`volume_up / volume_down / volume_set / volume_mute`** — System volume. *phrases:* `volume up` / `volume 50` / `mute`.

#### Weather — `skills/weather.py` + `skills/weather_for_city.py` (2)
- **`real_weather / weather_for_city`** — Live weather (stored city / named city, Open-Meteo). *phrases:* `real weather batao` / `weather in Mumbai`.

#### Web Jumps — `skills/web_jumps.py` (5)
- **`google_jump / youtube_jump / maps_jump / wikipedia_jump / translate_jump`** — Open a search/site directly. *phrases:* `google X` / `youtube X` / `maps X`.

#### Web Search — `skills/web_search.py` (3)
- **`web_search / search_cache_stats / clear_search_cache`** — Online search summarised in Hinglish + cached locally. *phrases:* `search online for X`.

#### WhatsApp — `skills/whatsapp.py` (1)
- **`send_whatsapp`** — Message a saved contact (name → phone via `data/contacts.json`). *phrases:* `whatsapp pe X ko bolo Y`.

#### Whisper STT — `skills/whisper_stt_skill.py` (5)
- **`stt_prefer_whisper / stt_prefer_google / whisper_set_model / whisper_status / whisper_transcribe_once`** — Pick STT backend + Whisper model. *phrases:* `use whisper for stt` / `whisper status`.

#### Window Manager — `skills/window_manager.py` (8)
- **`window_minimize / window_maximize / window_close / show_desktop / window_snap_left / right / top / bottom`** — Full window control. *phrases:* `snap left` / `maximize window` / `show desktop`.

#### Windows Power Utils — `skills/windows_power_utils.py` (5)
- **`window_pin_top / window_unpin_top / wallpaper_set / summarize_window / whoami_info`** — Always-on-top, wallpaper, active-window info, identity. *phrases:* `pin window` / `set wallpaper` / `whoami`.

#### Workspace Tracker — `skills/workspace_tracker_skill.py` (6)
- **`workspace_track_on / off / workspace_recent / workspace_summary / workspace_summary_today / workspace_clear`** — Foreground-app usage timeline. *phrases:* `track workspace` / `what have i been doing`.

> *(A handful of additional utility skills — `app_launch`, `open_app`, `close_app`,
> `stop_music`, `dictionary`, `focus`, `preferences` variants, etc. — live in
> `skills/system_skills.py`, `skills/info_skills.py`, and `advanced_skills.py`;
> `help` lists the definitive live set at runtime.)*

---

## 11. Skills by Theme — Why Each Family Exists & Other Possibilities

This is the section the flat catalogue can't give you: for each **family** of skills,
*why it exists* and *what else it could become*. Every one of the 338 skills belongs to
one of these families.

### 11.1 System control & power
`system_skills`, `brightness_control`, `volume_control`, `app_audio`, `window_manager`,
`windows_power_utils`, `monitor_swap`, `system_health`.

- **Why:** the core promise — a desktop assistant must *drive the desktop*. Lock,
  sleep, restart, snap windows, pin always-on-top, control per-app audio, move windows
  across monitors. These are the actions cloud assistants literally cannot do.
- **Other possibilities:** virtual-desktop switching; window *layouts* ("dev layout" =
  IDE left, docs right, terminal bottom); scheduled brightness/night-shift curves;
  "focus one app" (dim everything else); audio ducking (auto-lower music when a call
  starts); per-monitor wallpaper.

### 11.2 Browser & web
`browser_skill`, `browser_tabs`, `web_jumps`, `web_search`, `clipboard_open_url`.

- **Why:** the browser is where most work happens; controlling profiles/tabs by voice
  and doing a summarised, *cached* web search keeps you in flow without hunting for the
  window. Caching means the second time you ask, it's instant and offline.
- **Other possibilities:** read a page aloud (reader mode + TTS); "summarise this tab"
  via the Chrome extension prototypes; tab-group management; open a *set* of sites as a
  "session"; ad-free reading; screenshot-a-URL to PDF.

### 11.3 Files, clipboard & snippets
`file_ops`, `file_finder`, `clipboard*`, `snippet_skills`, `productivity_extras`.

- **Why:** the small frictions — "where did I save that," "reformat this clipboard,"
  "expand my signature" — add up. A background clipboard watcher + history means you
  never lose a copy again.
- **Other possibilities:** clipboard *sync* across devices (via the phone bridge);
  smart file tagging; "open my most recent download"; regex clipboard transforms;
  snippet variables (`{{date}}`, `{{clipboard}}`); a rename-batch skill.

### 11.4 Productivity & focus
`focus_mode`, `pomodoro`, `productivity_pack`, `timer_skill`, `scheduled_lock`,
`journal`, `workspace_tracker`, `expense_tracker`.

- **Why:** the assistant should protect your attention, not just answer questions.
  Focus mode closes distractions + enables DND; the workspace tracker builds an honest
  timeline of where your day went; the expense/task/meeting workbook is a zero-friction
  personal ledger.
- **Other possibilities:** RescueTime-style automatic categorisation + weekly report;
  "focus streak" gamification; break reminders tied to eye-strain timers; a
  budget-alert routine ("you've spent 80% of your food budget"); calendar-aware focus
  ("meeting in 10 min — wrap up").

### 11.5 Knowledge, memory & Q&A
`kg_skill`, `memory_skills`, `conversation_recap`, `doc_qa_skill`, `dictionary`,
`info_skills`, `news`, `weather*`.

- **Why:** an assistant that forgets is annoying. The KG stores exact facts; semantic
  memory recalls by meaning; doc-QA turns a folder into a searchable brain; the
  info/news/weather skills answer the everyday factual questions locally where
  possible.
- **Other possibilities:** auto-extract facts from conversation into the KG; a
  personal "second brain" search across memory + docs + journal; RAG over the doc index
  feeding the LLM; scheduled morning briefings combining weather + news + calendar +
  budget.

### 11.6 Voice & speech
`whisper_stt_skill`, `tts_voice`, `voice_tuning`, `voice_memo`, `voice_id_skill`,
`transcript_skill`, `translate`, `translator_skill`.

- **Why:** voice is the primary interface, so it must be *tunable* (rate, volume,
  accent, backend) and *identifiable* (who's speaking). Voice memos + live transcript
  make it a capture tool, not just a command line.
- **Other possibilities:** meeting transcription + summary; real-time translation
  ("speak to me in English, I'll answer in Hindi"); voice-cloned custom TTS; emotion in
  TTS from sentiment; wake-word retraining on *your* voice.

### 11.7 Vision & gesture
`gesture_skill`, `gesture_mgmt`, `custom_gestures_skill`, `gesture_practice_skill`,
`gesture_sensitivity`, `calibration_skill`, `per_app_profiles`, `object_skill`,
`auto_label_skill`, `ar_overlay_skill`, `vision`, `snip_ocr`.

- **Why:** hands-free control and screen-awareness are the "wow" features and genuine
  accessibility wins. OCR turns the screen into readable/clickable text; object
  detection turns the webcam into an eye.
- **Other possibilities:** gesture combos/sequences; gaze control; "read this and click
  the blue button" (OCR + reasoning); barcode/QR scanning via webcam; a live sign of
  what the AR overlay sees on a second monitor.

### 11.8 Identity, permissions & privacy
`master_users`, `master_permissions`, `permissions_editor_skill`, `voice_id_skill`,
`privacy_mode_skill`, `presence_skill`, `vault_skills`.

- **Why:** a camera + mic + OS control is a serious security surface. The face gate +
  per-master permissions + presence + hard privacy kill-switch + DPAPI vault are what
  make it *safe to leave running*. (See §15.)
- **Other possibilities:** voice as a second auth factor at routing time; time-of-day
  permission windows ("kids can't lock the PC after 9 PM"); audit log of who did what;
  encrypted-at-rest memory; a physical "privacy LED" indicator.

### 11.9 Automation & extensibility
`automation_skill`, `chain_skill`, `macros`, `plugin_skill`, `teach_skills`,
`code_writer`, `repeat_last`.

- **Why:** the assistant should grow with you *without code*. Routines/chains/macros
  cover unattended, reactive, and manual automation (§9); the plugin loader + teach-me
  let you extend it at runtime; code_writer even generates scripts.
- **Other possibilities:** a visual automation builder; a plugin marketplace/registry;
  "teach by demonstration" (record a sequence of actions → save as a skill); LLM-authored
  skills that get reviewed then registered.

### 11.10 Integrations (opt-in cloud)
`outlook_email`, `outlook_calendar`, `spotify_control`, `sheets_sync`, `whatsapp`,
`phone_bridge_skill`, `notification_mirror`.

- **Why:** these reach *out* to services you already use — deliberately opt-in, so the
  local-first promise holds unless you choose to connect them.
- **Other possibilities:** Google Calendar/Gmail; Slack/Teams presence; Telegram bot
  bridge; smart-home (Home Assistant) control; a proper mobile companion PWA over the
  phone bridge; calendar-driven routines.

### 11.11 Meta / self-management
`diagnostics`, `dep_validator_skill`, `docs_gen_skill`, `settings_schema_skill`,
`settings_panel_skill`, `telemetry_skill`, `log_digest`, `gpu_offload_skill`,
`sync_skill`, `theme_skill`, `help_catalog`, `first_run_skill`, `status_report`.

- **Why:** a big system needs to *explain and repair itself*. Diagnostics probes every
  subsystem; dep_check tells you exactly which optional install is missing; the sync
  ZIP makes AERIS portable between machines; docs/help regenerate from the live
  registry so documentation can't drift.
- **Other possibilities:** self-update; a "what changed in the last 24h?" summary from
  the structured logs; auto-fix suggestions from diagnostics; cloud backup of the sync
  ZIP; a settings-diff between two machines.

---

# Part IV — The Interface

## 12. The GUI — Every Panel, Page & Control Explained

AERIS ships several GUI generations (all in the repo). The **primary, current** one is
`ui/jarvis_v31/` (the "JARVIS v3.1" window launched by `run_gui.py`); there are also
`ui/aeris_v4/`, `ui/aeris_v6/` (a page-based redesign), and the `new_gui_latest/`
React/HTML prototypes (jv3→jv6) that map a future web front-end. This section documents
what the **v3.1 window** presents and the option surfaces behind it.

### 12.1 The main window layout

```
┌───────────────────────────────────────────────────────────────┐
│ ● ● ●   AERIS                                        ─  □  ✕   │  ← custom title bar
├──────┬────────────────────────────────────────────────────────┤
│      │                                                         │
│ DOCK │            REACTOR ORB (pulses on state)                │
│ Home │                                                         │
│ Conv │         GLASS CHAT PANEL (markdown, per-msg TTS)        │
│ Auto │                                                         │
│ Brain│                                                         │
│ Mem  │                                                         │
│ Vis  │        [ type or speak…            ] 🎙  📷            │
│ Work │                                                         │
│ Sys  ├────────────────────────────────────────────────────────┤
│ Set  │ logs bar: tail of data/logs/aeris.log                  │
└──────┴────────────────────────────────────────────────────────┘
```

- **Custom title bar** (`title_bar.py`) — frameless window with traffic-light
  minimise/maximise/close; drag to move. *Why custom:* a frameless window lets the glass
  aesthetic bleed to the edges and enables the always-on-top / snapping tricks.
- **Reactor orb** (`reactor.py`) — the pulsing core that visually reflects state:
  idle, **listening**, **thinking**, **speaking**. Subscribes to the shared
  `animation_bus` so it pauses/resumes with the rest of the UI. *Why:* immediate,
  glanceable feedback that AERIS heard you.
- **Glass chat panel** (`glass_chat_panel.py`) — frosted chat with markdown rendering
  and **per-message TTS controls** (replay/stop any reply). Listens for the `clear_chat`
  skill signal to wipe itself.
- **Logs bar** (`logs_bar.py`) — a live tail of `data/logs/aeris.log` along the bottom,
  so the internals are always visible.

### 12.2 The sidebar dock — the nine pages

The dock (`floating_dock.py`) is an auto-hiding vertical navigation grouped into three
clusters (**core / intel / system**). Each item switches the main content to a page:

| Page | Group | What it shows / does |
|---|---|---|
| **Home** | core | Landing dashboard — greeting, quick status (battery, time), quick-action tiles. |
| **Conversations** | core | The chat history / transcript-centric view. |
| **Automations** | core | Routines, chains, and macros — list, enable/disable, run (surfaces §9). |
| **Brain** | intel | Intent/brain state — model, confidence, recent routing, retrain status. |
| **Memory** | intel | The four memory stores — semantic recall, knowledge-graph facts, conversation. |
| **Vision** | intel | Camera/gesture/face/object state — enroll, calibrate, AR toggle. |
| **Workbook** | intel | Expenses / tasks / meetings from the local `.xlsx`. |
| **System** | system | Health metrics — CPU/RAM/disk/battery/network, diagnostics. |
| **Settings** | system | The full settings surface (below). |

The dock's **Options** menu adds: **Account**, **Preferences**, **Switch Theme**,
**Sign Out**.

*Why a page-based dock:* 338 skills are too many for one screen; grouping the surfaces
into nine themed pages makes the assistant browsable, not just voice-only.

### 12.3 The command palette (Ctrl+Shift+P / Ctrl+K)

A Spotlight-style floating overlay (`command_palette.py`) that fuzzy-searches **all 338
skills** by name/description and runs one on Enter. *Why:* the fastest path when you
know *what* you want but not the exact phrase. **Other possibilities:** recent/favourite
skills, argument prompts inline, keyboard-only argument entry.

### 12.4 The settings panel — every option

Opened by `open settings` (`ui/settings_panel.py`). A modal form editing the
most-touched `settings.json` keys without hand-editing JSON:

| Control | Options / range | Backing key |
|---|---|---|
| **Assistant name** | free text (default "AERIS") | `assistant_name` |
| **Wake word** | free text (default "aeris") | `wake_word` |
| **Speech rate** | spin box (~120–220 wpm, default 175) | `speech_rate` |
| **Voice volume** | 0.0–1.0 | `voice_volume` |
| **TTS voice** | picker of 8 neural voices: `en-IN-Neerja/Prabhat`, `hi-IN-Swara/Madhur`, `en-US-Aria/Guy`, `en-GB-Sonia/Ryan` | `voice_gender`/voice key |
| **Language** | hinglish / english / hindi | `language` |
| **Gesture sensitivity** | very_sensitive · sensitive · normal · relaxed · very_relaxed | sensitivity key |
| **Master users + gate strictness** | list editor | `master_users` |
| **Default browser** | system / chrome / edge / brave (+ profile) | `default_browser`, `default_browser_profile` |
| **Focus mode apps** | close-list / open-list / pomodoro minutes | `focus_mode_close/open/pomodoro_min` |
| **Presence** | enabled, heartbeat_s, quiet hours, speak-moments | `presence.*` |

*Why a curated subset:* ~20 of ~80 known keys cover the common cases; the rest are
"advanced — JSON only" (documented gap in §17). The settings are **schema-versioned**
(`settings_schema.py`) with a migration registry, so upgrading never leaves stale keys.

### 12.5 Other GUI surfaces (dialogs & overlays)

| Surface | File | What it does |
|---|---|---|
| **Telemetry dashboard** | `telemetry_dashboard.py` | Tabbed usage stats: gestures, skills, workspace, memory. |
| **Permissions matrix editor** | `permissions_editor.py` | The masters × gestures grid — grant/block per user in one view. |
| **AR overlay** | `ar_overlay.py` | Translucent always-on-top camera preview with YOLO boxes. |
| **HUD overlay** | `hud_overlay.py` | Always-on-top status widget, movable to any corner. |
| **First-run wizard** | `first_run_wizard.py` | Face → voice → theme → diagnostics onboarding. |
| **Calibration wizard** | `calibration_wizard.py` | Walk every gesture with live detection feedback. |
| **Transcript pane** | `transcript_pane.py` | Live STT stream — partial + final events as they arrive. |
| **System tray** | `system_tray.py` | Tray icon + menu + **global hotkey** to focus AERIS. |

### 12.6 Themes

Three live-switchable themes (`core/theme.py`, tokens in `ui/jarvis_v31/tokens.py`):
**light**, **dark**, **cyber** (neon-on-black). Switch by voice (`dark theme`) or the
dock Options menu. *Why design tokens:* every panel reads colours/radii/fonts from one
token file, so a new theme is a token set, not a rewrite. **Other possibilities:**
custom user themes, auto light/dark by time of day, per-page accent colours.

---

# Part V — Operations

## 13. Data, State & Where Everything Lives

```
data/
├── settings.json                # Preferences, gesture bindings, voice tuning, presence
├── settings_schema (in code)    # Versioned schema + migrations
├── intents.json                 # Pattern → intent labelled corpus (k-NN)
├── entities.json                # Entity slot vocab
├── hinglish_dict.json           # Hinglish normalisation dictionary
├── feedback_log.sqlite          # Bandit reward signals (continual learning)
├── semantic_memory.npz          # Vector store for conversation recall
├── knowledge_graph.json         # Subject–predicate–object facts
├── knowledge_cache.sqlite       # Cached web-search answers
├── user_memory.json             # Misc user memory
├── user_patterns.json           # Learned usage patterns
├── chains.json                  # Cross-skill chains (§9.2)
├── routines.json                # Automation routines (§9.1)
├── macros.json                  # Voice macros (§9.3)
├── custom_gestures.json         # Trained custom gestures
├── face_registry_insight.json   # InsightFace enrollments
├── jarvis_workbook.xlsx         # Expenses / tasks / meetings
├── snippets.json                # Text-expander snippets
├── clipboard_history.json       # Clipboard watcher history
├── presence_journal.jsonl       # Presence events
├── scratch.md / notes/journal.md# Quick notes + rolling journal
├── notes/audio/                 # Voice memo WAVs
├── snips/ , generated_code/     # OCR snips, generated scripts
├── audio_cache/                 # TTS pre-renders for repeated phrases
├── plugins/                     # Third-party plugins
├── logs/                        # Structured JSON-line logs (rotated)
└── models/                      # Local model files (YOLO, InsightFace, Whisper…)
```

**Every** JSON write routes through `core/atomic_io.py` (`tmp → fsync → rename`) so a
crash mid-write can't corrupt state. Human-readable JSON where editability matters;
SQLite for dense append-heavy stores; `.npz` for vectors; `.xlsx` for the workbook so
you can open it in Excel.

## 14. Observability, Safety & Resilience

- **Structured logs** — `data/logs/aeris.log` is JSON-lines with rotating handlers.
- **Health server** — `127.0.0.1:8765` exposes `/health`, `/skills`, `/metrics`,
  `/shutdown`. Real liveness, like a server.
- **Crash beacon + dump** — a "dirty" marker is written at boot and flipped clean on
  graceful exit; if the previous run crashed, the beacon detects it and a faulthandler
  dump (`crash_<ts>.txt`, all-thread state + log tail) is written on the fault.
- **Single-instance guard** — a second launch focuses the running window and exits.
- **Graceful shutdown** — drains pending work + flushes memory before Qt exits;
  handlers install *before* heavy imports so even an import-time crash cleans up.
- **Circuit breakers** — a repeatedly-throwing skill trips instead of crashing the loop.
- **Resource monitor** — samples CPU/RAM/GPU and throttles heavy skills under pressure.
- **3-tier TTS + 3 STT backends** — speech keeps working through cloud outages.

*Why this much:* a personal assistant that runs all day must fail *quietly and
recoverably*, and you must be able to see what it's doing when it misbehaves.

## 15. Privacy & Security Model

- **Local by default:** default STT can be offline (Vosk/Whisper), TTS falls back
  offline, the LLM is your own Ollama, memory/vault are on-disk. Cloud reaches
  (web search, Outlook, Spotify, Sheets, WhatsApp) are **opt-in per skill**.
- **The vault** (`core/vault.py`) encrypts secrets with **Windows DPAPI** — tied to
  your Windows account, no master password. Retrieved secrets go to the **clipboard,
  never the chat log**.
- **Privacy mode** is a hard kill-switch: mic + STT + gesture + camera + auto-label +
  notification mirror all off in one command. It does **not** auto-resume — you
  re-enable only what you want.
- **Face gate + permissions matrix + presence:** only enrolled masters fire gestures,
  each with a per-user allowlist, and the loop pauses when nobody's there.
- **No telemetry leaves the machine** — the telemetry dashboard is in-memory/local only.

**Other possibilities:** encrypt semantic memory at rest; an audit log of every
skill fire with speaker ID; a visible recording indicator; redaction of secrets from
logs; per-skill network-permission prompts.

## 16. Tests & Health

- ~**39** test files under `tests/`; ~950 cumulative passing across the tier 1–8 loop.
- Per-tier suites (`test_tier1…8`), per-iteration suites (`test_iter1…9_*`), plus
  focused ones (e.g. `test_response_enricher.py` — cache round-trip, LLM stubbing,
  non-repeat ordering, skill wiring).

```powershell
python -m pytest -q                         # everything
python -m pytest tests/test_response_enricher.py -v   # one suite
```

> Note: the intent-classifier training scripts (`python -m core.train_intent`) are run
> **by you**, deliberately — AERIS never auto-invokes training.

## 17. Roadmap & Other Possibilities (Project-Wide)

**Coverage gaps worth closing:**
- Tests for the gesture pipeline (a fake-frame replay rig) and the TTS fallback chain.
- A smoke test for `core/main_engine.py` orchestration (send "hi" → assert TTS fired).

**UX:**
- Show *which* skill fired under each reply ("greeting · enriched · 12 ms").
- A global 5-second **undo toast** for destructive skills (`window_close`,
  `kill_process`, `forget_command`).
- First-run wizard verifies Ollama reachability with a "skip for now" branch.
- Expand the settings panel to the remaining keys (or document the "JSON-only" set).

**Performance:**
- Parallel-load the encoder + InsightFace to shave 2–3 s off cold start.
- Release the camera after N seconds with no subscribers (LED off).
- Wire `data/audio_cache/` so common short phrases replay from disk.

**Bigger features:**
- Visual routine builder (data model already supports it).
- A "what did you change in the last 24h?" self-summary from structured logs.
- Wake-word retraining on your own voice.
- Mobile companion PWA over the phone bridge (`/skills` → buttons).
- Voice ID as a second-factor gate at routing time.
- Expose the skill registry as an **MCP server** for external LLMs.

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| GUI freezes on splash | torch DLL conflict when imported off-main-thread | Launch via `run_gui.py` (it pre-imports torch on the main thread first). |
| "intent … missing" | Stale brain index vs live registry | Restart; if needed delete `data/models/intent_index.pkl` to regenerate, and run `regenerate skill docs` + a corpus rebuild after big skill batches. |
| Left panel paused, no animation | `_anim_bus.resume()` didn't run (brain-ready failed) | Tail `data/logs/aeris.log` for `_on_brain_ready: done`; read the traceback above if absent. |
| Whisper unavailable | `large-v3` is ~3 GB | `whisper_set_model tiny` (≈75 MB); Google STT is the fallback. |
| Camera won't release | Vision engine still has subscribers | `gesture mode off`, `auto label off`, `ar overlay off`. |
| TTS silent | edge-tts hit a 429 | It falls through to pyttsx3 → SAPI5; check the log for the tier switch. |
| A skill "went dark" | Missing optional dependency | Run `dep check` — it names the exact package and the skills it disables. |
| Ollama chat/enrichment not firing | Ollama not running / model not pulled | `ollama serve`, `ollama pull llama3.1`; check `llm status`. |

---

*This README was assembled by walking the live skill registry and reading the actual
`core/`, `skills/`, `ui/`, and `data/` sources. Skill names, descriptions, and sample
phrases come from `core.skill_registry.all_skills()`. To refresh the catalogue after a
feature push: `regenerate skill docs` (updates `docs/SKILLS.md`), then rebuild the
relevant sections here. The previous README is preserved as
`README_pre_expand_<date>.md` and `README_OLD.md`.*
