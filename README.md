# AERIS / Jarvis 3.0

**A.E.R.I.S** — Adaptive Engine for Reasoning, Intelligence & Speech  
A fully-local, Hinglish-native personal AI assistant built from scratch in Python.

---

## Table of Contents

0. [Latest Changelog (v3.3 — Phase F + G shipped)](#0-latest-changelog-v33--phase-f--g-shipped)
1. [What This Is](#1-what-this-is)
2. [Quick Start](#2-quick-start)
3. [Full Architecture](#3-full-architecture)
4. [Module Reference](#4-module-reference)
5. [All Skills / Intents](#5-all-skills--intents)
6. [Memory System](#6-memory-system)
7. [Continual Learning (Feedback Bandit)](#7-continual-learning-feedback-bandit)
8. [GUI](#8-gui)
9. [Tests](#9-tests)
10. [Configuration](#10-configuration)
11. [Known Limitations of the Current k-NN Brain](#11-known-limitations-of-the-current-k-nn-brain)
12. [Phase F — Feature Parity & Bug Fixes](#12-phase-f--feature-parity--bug-fixes)
13. [Phase G — Next-Level Upgrades](#13-phase-g--next-level-upgrades)
14. [Dependency Reference](#14-dependency-reference)
15. [Project Layout](#15-project-layout)
16. [Build Status](#16-build-status)

---

## 0. Latest Changelog (v3.3 — Phase F + G shipped)

This release implements the structural pieces of Phase F and Phase G that don't require ~GB-scale model downloads or external OAuth setup. Everything below is fully wired and runnable today:

### New core modules

| File | What it does |
|------|--------------|
| `core/skill_registry.py` | `@skill` decorator + auto-discovery of `skills/*.py` plugins. Plugin patterns merged into the brain's k-NN index, plugin handlers dispatched by the executor. |
| `core/wake_word.py` | Vosk grammar-restricted wake word detector. ~3-5% CPU, sub-second latency, fully offline. Pause/resume API for mic ownership. |
| `core/scheduler.py` | APScheduler-backed reminder scheduler. Real reminders that actually fire — no more stub. |
| `core/time_parser.py` | Hinglish/English time-string parser. Handles "5 pm", "5 baje", "subah 7 baje", "kal 9 baje", "10 minute mein", etc. |
| `core/tool_router.py` | Parses LLM JSON tool calls (single tool / chat / multi-step plan) and dispatches through the executor + memory. |
| `core/vault.py` | AES-256 (Fernet) encrypted memory vault. PBKDF2-SHA256 key derivation, 480k iterations. |

### Existing modules upgraded

| File | What changed |
|------|--------------|
| `core/intent_classifier.py` | `_load_intents()` merges plugin patterns from the registry. Hash now covers file + plugins so cache invalidates correctly. |
| `core/executor.py` | `set_reminder` is now a real call into `ReminderScheduler`. Unknown intents fall through to the plugin registry. Constructor accepts a scheduler. |
| `core/llm_chat.py` | New `reply_with_tools()` method. Dedicated tool-calling system prompt, `format=json`, low temperature for reliable structured output. |
| `core/stt.py` | New `listen_streaming(on_partial, on_final)` that fires partial results live as the user speaks. |
| `core/memory.py` | Optional `passphrase` constructor arg → all reads/writes routed through the vault. `enable_vault` / `disable_vault` migration methods. |
| `core/main_engine.py` | Phase-0 plugin discovery, scheduler wiring, optional vault, LLM tool-call routing in `_fallback`. New constructor flags: `memory_passphrase`, `enable_scheduler`, `enable_tool_calls`. |
| `main.py` | New `--wake` mode (Vosk wake word), new `--vault` flag (passphrase prompt), new REPL commands `:reminders`, `:skills`, `:vault on`. |

### New plugin skills (in `skills/`)

| Skill file | Tools registered | Status |
|------------|------------------|--------|
| `skills/clipboard.py` | `clipboard_copy`, `clipboard_paste` | Works after `pip install pyperclip` |
| `skills/file_ops.py` | `open_file`, `create_folder`, `reveal_in_explorer` | Works out of the box |
| `skills/news.py` | `news_briefing` | Works after `pip install feedparser` |
| `skills/weather.py` | `real_weather` | Set `OPENWEATHER_API_KEY` env var |
| `skills/translate.py` | `translate_to_english`, `translate_to_hindi` | Works after `pip install argostranslate` + downloading hi↔en model |
| `skills/whatsapp.py` | `send_whatsapp` | Works after `pip install pywhatkit` + `data/contacts.json` |
| `skills/vision.py` | `read_screen`, `click_text` | Works after installing Tesseract binary + `pip install pytesseract mss pillow` |
| `skills/spotify_control.py` | `spotify_play_track`, `spotify_pause`, `spotify_next` | Works after `pip install spotipy` + Spotify Developer credentials |

Every skill module fails gracefully when its optional dependency isn't installed — the skill simply tells the user what to install. The rest of AERIS keeps working.

### New tests

| Test file | Coverage |
|-----------|----------|
| `tests/test_skill_registry.py` | Decorator registration, override, manifest, intent-dict shape |
| `tests/test_time_parser.py` | All Hinglish/English time forms, relative/absolute, today/tomorrow rollover |
| `tests/test_tool_router.py` | JSON parsing (fenced, prose-wrapped, malformed), single tool, chat, multi-step plans, exception handling, memory write |
| `tests/test_vault.py` | Round-trip encrypt/decrypt, wrong-passphrase rejection, plaintext detection, `UserMemory` integration, plaintext→vault migration |
| `tests/test_scheduler.py` | Job firing, past-time rejection, listing upcoming, cancellation |

### How to use the new features

**Wake word:**
```bash
# Download Vosk model once:
# https://alphacephei.com/vosk/models  →  vosk-model-small-en-in-0.4
# Unzip to: data/models/vosk-model-small-en-in-0.4/
python main.py --wake
```

**Real reminders:**
```
You: 10 minute mein chai banane ka reminder lagao
AERIS: Reminder set: 'chai banane ka' — 10:43 AM, 09 May pe yaad dilaoonga.
[10 minutes later, AERIS speaks: "Reminder, sir: chai banane ka"]
```

**LLM tool calling** (with Ollama running):
Anything outside the trained patterns now goes through the LLM-with-tools route. The LLM returns structured JSON like `{"tool": "set_reminder", "args": {...}}` and the tool router dispatches it. Multi-step plans and conditional logic work too.

**Encrypted memory:**
```bash
python main.py --vault          # prompts for passphrase at boot
# OR mid-session in text mode:
You: :vault on
New passphrase: ******
AERIS: Memory vault enabled.
```

**Plugin skills (REPL):**
```
You: :skills
  8 plugin skills loaded:
    - clipboard_copy: Copy a piece of text to the system clipboard
    - news_briefing: Fetch latest headlines and summarize them in Hinglish
    ...
```

### What's still planned (not yet shipped)

The following Phase F + G items require model downloads (>200 MB), external auth flows, or significant UI work and are still on the roadmap:

- Hybrid transformer classifier (F1) — needs accumulated `feedback_log.sqlite` data first
- LaBSE encoder swap (F2) — drop-in, but requires re-downloading 470 MB
- faster-whisper local STT (F6) — 244 MB model
- Multilingual sentiment (F10) — 500 MB model
- GUI rewire to new engine (F8) — significant PyQt work
- Google Calendar integration (G5) — OAuth flow
- Voice cloning TTS (G9) — 2 GB Coqui XTTS model
- Mobile companion (G10) — needs separate Flutter/RN app
- Analytics dashboard (G12) — significant PyQt work

See §12 and §13 below for full specs of these items.

---

---

## 1. What This Is

Jarvis 3.0 / AERIS is a personal AI assistant that:

- Understands **Hinglish** (Hindi + English mixed speech) natively — no translation layer
- Runs **fully locally** for intent routing, memory, and system control — no mandatory cloud APIs
- **Learns from your corrections** over time using a contextual bandit policy
- Maintains **persistent memory** of facts you tell it ("my name is Shivang", "I work at Google")
- Falls back to a **local LLM** (Ollama + Phi-3 / Llama 3.2) for open-ended conversation
- Controls your Windows PC: open/close apps, search the web, take screenshots, control volume, lock screen, set reminders, create notes, and more

This is version 3.0. It replaces a previous architecture (Keras dense classifier + manual Hinglish translation map) with a multilingual semantic encoder + k-NN pipeline that requires zero retraining when you add new patterns.

---

## 2. Quick Start

### Prerequisites

- Python 3.10 or 3.13
- Windows 10/11 (most system actions use `ctypes`, `subprocess`, Windows paths)
- A microphone (optional — text mode works without one)

### Install

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional, improves NER
```

### First Run (text mode — no microphone needed)

```bash
python main.py --text
```

The brain downloads and caches the sentence encoder (~120 MB) on first boot. Subsequent boots use the cached `data/models/intent_index.pkl`.

### Voice Mode

```bash
python main.py
```

Uses Google STT (requires internet) with Vosk as offline fallback. Edge-TTS Neerja voice for speech output with pyttsx3 fallback.

### GUI

```bash
python run_gui.py
```

### In-REPL Commands (text mode only)

| Command | Action |
|---------|--------|
| `:facts` | Show all stored user facts |
| `:stats` | Show feedback DB stats (utterances logged, pending patterns, learned thresholds) |
| `:help` | List all commands |
| `quit` / `exit` | Exit |

### LLM Chit-chat Setup (optional but recommended)

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull phi3:mini       # 2.4 GB — fast, good quality
ollama pull llama3.2:3b     # 2.0 GB — slightly smaller
```

Ollama runs as a background daemon. AERIS detects it automatically. Without it, low-confidence utterances are queued for review instead of answered conversationally.

---

## 3. Full Architecture

```
┌──────────────────────────── Audio In ──────────────────────────────┐
│  Mic → STT (Google en-IN / Vosk fallback) → raw text               │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────── Brain Pipeline ─────────────────────────────┐
│                                                                      │
│  raw text                                                            │
│     │                                                                │
│     ├─[0a]─ State: is slot-filling in progress?                     │
│     │         yes → handle_follow_up(text) → executor               │
│     │                                                                │
│     ├─[0b]─ State: is disambiguation in progress?                   │
│     │         yes → parse answer → execute chosen intent            │
│     │                                                                │
│     ├─[1]── Pending feedback window: did user say "galat"?          │
│     │         yes → record correction reward on prior utterance      │
│     │                                                                │
│     ├─[2a]─ memory.detect_and_recall(text)                          │
│     │         match → return stored fact immediately                 │
│     │                                                                │
│     ├─[2b]─ memory.detect_and_store(text)                           │
│     │         match → save fact, return ack, skip pipeline           │
│     │                                                                │
│     ├─[3]── Is text a cancel keyword?                               │
│     │         yes → state.reset(), return polite message            │
│     │                                                                │
│     ├─[4]── utterance_parser.split_into_segments(text)              │
│     │         "chrome kholo aur notepad bhi" → two segments         │
│     │                                                                │
│     └─ Per segment:                                                  │
│           │                                                          │
│           ├─[5]── sentiment.classify(seg)                           │
│           │         → (label: positive/neutral/negative, score)      │
│           │                                                          │
│           ├─[6]── utterance_parser.find_best_interpretation(seg)    │
│           │         scans subspans, picks highest-confidence pred    │
│           │                                                          │
│           ├─[7]── entity_extractor.intent_hint(seg)                 │
│           │         gazetteer override for open/close app commands   │
│           │                                                          │
│           ├─[8]── feedback.get_threshold(predicted_intent)          │
│           │         per-intent learned acceptance threshold           │
│           │                                                          │
│           ├─ confidence ≥ threshold?                                 │
│           │     YES:                                                 │
│           │       ├─ disambiguator.is_close_call(pred)?             │
│           │       │     yes → prompt "A ya B?" → await answer       │
│           │       │                                                  │
│           │       └─ entity_extractor.extract(seg, intent)          │
│           │             → state_manager.process_prediction()        │
│           │             → executor.execute(intent, slots)           │
│           │             → feedback.log_utterance()                  │
│           │                                                          │
│           └─ NO (low confidence):                                    │
│                 → llm_chat.reply() if Ollama available              │
│                 → else: queue in feedback.sqlite + polite fallback  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────── Audio Out ─────────────────────────────────┐
│  response text → TTS (Edge-TTS Neerja / pyttsx3 fallback)          │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Reference

### `core/brain.py` — Orchestrator

`JarvisBrain` wraps the intent classifier. It owns the sentence encoder and index lifecycle. The `lazy=True` constructor flag lets the GUI boot it progressively without blocking the main thread.

Key methods:
- `predict(text)` → `Prediction` dataclass: `intent`, `confidence`, `top3`, `raw_text`, `normalized_text`
- `load_encoder()` — loads the sentence transformer (slow on first boot, fast on cache hit)
- `build_or_load_index()` — rebuilds k-NN index if `intents.json` has changed (MD5 hash check), else loads from `data/models/intent_index.pkl`

### `core/intent_classifier.py` — k-NN Intent Classifier

**Encoder:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 384-dimensional embeddings
- 50+ languages including Hindi natively
- ~120 MB download, ~30 ms encode per utterance on CPU

**Classifier:** `sklearn.NearestNeighbors(n_neighbors=5, metric="cosine")`
- No training step — patterns are embedded and stored directly
- New patterns take effect on next boot without any retraining

**Voting:** Exponential-weighted (temperature=10). The closest neighbour dominates. Confidence = top-1 cosine similarity across the 5-neighbour vote.

**Index cache:** `data/models/intent_index.pkl` keyed by MD5 hash of `intents.json`. Auto-rebuilds on change in ~10 seconds.

### `core/normalizer.py` — Text Normalizer

Minimal: lowercase + strip punctuation only. URL-safe characters preserved. No translation map — the multilingual encoder handles Hindi/Hinglish natively.

### `core/entity_extractor.py` — 4-Layer Entity Extractor

Extracts slots (`app_name`, `time`, `url`, `query`, `expression`, `content`, `person`, etc.) from the raw utterance. Layers fire in order; first hit wins per slot:

1. **Regex** — `time` patterns (`\d{1,2}(:\d{2})?\s*(am|pm|baje)`, `subah`, `shaam`), `url` patterns, `number`, math `expression`
2. **Gazetteer** — `app_name` from `data/entities.json` (25 apps, longest-match-wins)
3. **spaCy NER** (`en_core_web_sm`) — `PERSON` → `person` slot; `DATE/TIME` → `time` slot when regex misses
4. **Residual span** — per-intent trigger-word stripping; remainder assigned to canonical free-form slot (`query` for search/YouTube, `content` for notes, `expression` for calculate)

Also exposes `intent_hint(text)` — gazetteer + open/close verb check to override the brain's prediction when structural evidence is unambiguous. This prevents "brave open karo" from being classified as `volume_up`.

### `core/sentiment.py` — Sentiment Analyzer

VADER (`vaderSentiment`) extended with ~30 Hinglish booster terms: `mast`, `kharab`, `bakwaas`, `theek`, `shukriya`, `accha`, `bekar`, `zabardast`, etc.

Returns a `Sentiment` dataclass: `label` (positive/neutral/negative), `score` (-1.0 to 1.0).

Used by:
- LLM chit-chat system prompt (tone-adapts replies: supportive when negative, enthusiastic when positive)
- Conversation history (each user turn tagged with sentiment label)

Upgrade path: swap to `cardiffnlp/twitter-xlm-roberta-base-sentiment` for true multilingual sentiment without the manual booster lexicon.

### `core/memory.py` — Long-Term User Memory

JSON-backed persistent store at `data/user_memory.json`. Detects natural-language fact assertions and stores them automatically. Survives restart.

**Detection patterns (auto-store):**
- `"my name is X"` / `"mera naam X hai"` / `"main hoon X"` → `name`
- `"I live in X"` / `"main X mein rehta hoon"` → `location`
- `"I work at X"` → `employer`
- `"my favourite X is Y"` / `"mera fav X Y hai"` → `favorite_X`
- `"remember that X"` → `notes` list

**Hindi key aliases for recall:** `naam` → `name`, `ghar` → `location`, `kaam` → `employer`, `shahar` → `city`, `office` → `employer`

Facts injected into the LLM system prompt so chit-chat replies are user-aware even on first mention.

### `core/conversation.py` — Short-Term Context

Rolling deque of the last 8 turns (user + assistant). Each user turn tagged with sentiment label. Exported in OpenAI message format for the LLM call. Cleared on restart.

### `core/llm_chat.py` — Chit-Chat via Ollama

Pings `http://localhost:11434` to check if Ollama is running. Routes low-confidence utterances to the local LLM when available.

**System prompt includes:**
- AERIS personality: warm, witty, concise, Hinglish-native
- All stored user facts (injected from `memory.all_facts()`)
- Sentiment-driven tone hint ("be gentle and supportive" / "match their energy" / "be direct")
- Last N conversation turns as messages

Model default: `phi3:mini`. Also works with `llama3.2:3b`.

### `core/feedback.py` — Feedback Store & Bandit Policy

SQLite store at `data/feedback_log.sqlite` with three tables: `utterances`, `intent_thresholds`, `pending_patterns`.

Every utterance logged with: raw text, normalized text, predicted intent, confidence, top-3 alternatives, sentiment label/score, action taken. Feedback (accepted / corrected / cancelled) recorded after execution.

**Bandit policy (EMA threshold drift):**
- `α = 0.1` EMA smoothing factor
- Default threshold: `0.5`
- Drift down (accept faster): `avg_reward > 0.5 AND samples ≥ 5` → `threshold -= 0.01`
- Drift up (be more cautious): `avg_reward < -0.2` → `threshold += 0.02`
- Hard clamps: `[0.40, 0.90]`

### `core/disambiguator.py` — Disambiguation

Detects close calls when `top1.confidence - top2.confidence < 0.05 AND top1.confidence < 0.85`. Generates a Hinglish "A ya B?" prompt. Parses user's answer in 5 forms: digit (1/2/3), Hindi ordinal (pehla/doosra/teesra), intent name, keyword match, or defaults to top-1 on timeout.

### `core/state_manager.py` — Slot-Filling State Machine

Tracks multi-turn slot collection. When the executor is called with missing required entities, the state machine transitions to `WAITING_SLOT` and prompts for the missing value. Handles `cancel` and `reset`. Also manages `WAITING_DISAMBIG` state between turns.

### `core/executor.py` — Action Executor

Dispatches 21 intents to Python actions. All Windows-native — no external API keys required by default.

### `core/utterance_parser.py` — Multi-Command Splitter

Splits compound utterances ("chrome kholo aur notepad bhi") into segments that each run through the full pipeline independently. `find_best_interpretation` scans subspans of the segment to handle filler prefixes ("ek kaam karo notepad kholo" → recognizes `open_app` not `volume_down`).

### `core/stt.py` — Speech-to-Text

Google STT (en-IN locale) as primary. Vosk as offline fallback. Mic input via `pyaudio`. Both are hot-swappable: the engine accepts injected STT/TTS objects for testing.

### `core/tts.py` — Text-to-Speech

Edge-TTS (`hi-IN-NeerjaNeural`) as primary — best Hindi/Hinglish voice quality available online. `pyttsx3` as offline fallback. Audio played via `pygame` from cached `data/audio_cache/speech.mp3`.

### `core/main_engine.py` — Top-Level Orchestrator

`JarvisMainEngine` wires all modules. The `process_text(text)` method is a **pure function** of (text, internal state) → response string. Audio I/O is isolated to `run()`. This makes the entire brain testable without a microphone or speakers.

The `setup_iter()` generator yields progress events in 7 phases for GUI splash screens (encoder load → index build → entity extractor → sentiment+memory → feedback DB → state machine → ready).

### `core/review_cli.py` — Interactive Pattern Review

```bash
python -m core.review_cli
```

Shows pending low-confidence utterances from `data/feedback_log.sqlite`. For each: displays top-3 predictions, prompts you to assign the correct intent. Approved patterns are appended to `intents.json`. The k-NN index auto-rebuilds on next restart.

### `utils/gesture.py` — Hand Gesture Control

Uses `mediapipe` + `data/models/hand_landmarker.task` for gesture-based command triggering. Separate from the voice pipeline.

### `utils/monitor.py` — System Monitor

Background system metrics poller.

---

## 5. All Skills / Intents

21 intents currently in `data/intents.json` (~14 Hinglish patterns each):

| Intent | Example Hinglish Triggers | What Happens |
|--------|--------------------------|--------------|
| `open_app` | "chrome kholo", "spotify open karo", "vs code chalu kar" | Launches the app via `subprocess` / `os.startfile` |
| `close_app` | "chrome band karo", "notepad hatao", "close vlc" | Kills process via `psutil` |
| `get_weather` | "weather batao", "mausam kaisa hai", "barish hogi kya" | Returns current weather (stub — upgrade in §12.4) |
| `play_music` | "music chala do", "gaana lagao", "spotify kholo" | Opens Spotify app or Spotify Web |
| `stop_music` | "music rok do", "band karo gaana" | Sends `VK_MEDIA_STOP` keybd event |
| `get_time` | "time kya hai", "kitne baje hain" | Returns time + date in Hinglish |
| `take_screenshot` | "screenshot lo", "screen capture karo" | `pyautogui.screenshot()` to `data/` |
| `search_web` | "google pe X search karo", "X dhundo" | Opens Google search in browser |
| `play_youtube` | "youtube pe X chala do" | Opens YouTube search in browser |
| `open_website` | "github.com kholo", "X website open karo" | `webbrowser.open()` with auto-https |
| `system_info` | "battery kitni hai", "CPU usage batao" | `psutil` battery + CPU% + RAM used/total |
| `volume_up` | "volume badhao", "thoda louder" | `ctypes` VK_VOLUME_UP keybd event |
| `volume_down` | "volume kam karo" | `ctypes` VK_VOLUME_DOWN keybd event |
| `volume_mute` | "mute karo", "awaz band karo" | `ctypes` VK_VOLUME_MUTE keybd event |
| `lock_screen` | "screen lock karo", "computer lock kar" | `ctypes.windll.user32.LockWorkStation()` |
| `shutdown_system` | "system band karo", "shutdown karo" | `shutdown /s /t 30` (30s delay) |
| `calculate` | "12 + 7 * 3 calculate karo" | `eval()` over safe math chars |
| `create_note` | "note kar do X", "likh lo X" | Timestamped `.txt` in `data/notes/` |
| `set_reminder` | "5 baje milk lena yaad dilana" | Returns confirmation string (stub — §12.3) |
| `schedule_meeting` | "raj ke saath 5 baje meeting lagao" | Returns confirmation string |
| `greet` | "hello", "hi jarvis", "hey aeris" | Time-aware greeting (morning/afternoon/evening) |

---

## 6. Memory System

### Long-Term Memory (persists across restarts)

Stored in `data/user_memory.json`:

```json
{
  "facts": {
    "name":     {"value": "Shivang", "set_at": "2026-05-01T10:00:00", "source": "user_said"},
    "location": {"value": "Delhi",   "set_at": "...", "source": "user_said"},
    "employer": {"value": "Google",  "set_at": "...", "source": "user_said"}
  },
  "notes": ["buy milk on tuesdays"]
}
```

**Setting a fact — just say it naturally:**

```
"my name is Shivang"                    → name: Shivang
"I live in Delhi"                       → location: Delhi
"main Google mein kaam karta hoon"      → employer: Google
"my favourite browser is Brave"         → favorite_browser: Brave
"remember that I have a standup at 10"  → added to notes list
"mera favourite gaana Shape of You hai" → favorite_gaana: Shape of You
```

**Recalling a fact:**

```
"mera naam kya hai"         → "Aapka naam Shivang hai."
"where do I live"           → "Aap Delhi mein rehte hain."
"mera kaam kya hai"         → "Aapka kaam Google hai."
"what do you know about me" → lists all stored facts
"what's my pet"             → "Mujhe aapka pet pata nahi hai abhi."
```

### Short-Term Context (current session only)

Last 8 turns (user + assistant) stored in-memory as an OpenAI-format message list. Injected into every LLM call so chit-chat replies have conversation context. Cleared on restart.

---

## 7. Continual Learning (Feedback Bandit)

Every utterance is logged to SQLite. The system learns per-intent confidence thresholds from your acceptance behaviour. This is a **contextual bandit** — the right tool for this problem (one utterance → one decision → one reward signal).

### How It Works

```
You say something
  → Brain predicts intent with confidence X
  → Bandit checks: X ≥ learned_threshold[intent]?
      YES → extract entities → execute
      NO  → LLM fallback / disambiguation / queue for review

After execution:
  → If you say something unrelated → reward = +1 (implicitly accepted)
  → If you say "galat" / "wrong" / "undo" → reward = -1 (corrected)

Threshold update (EMA, α = 0.1):
  avg_reward = 0.9 * avg_reward + 0.1 * latest_reward

  if avg_reward < -0.2:
      threshold += 0.02   (more cautious)
  elif avg_reward > 0.5 AND samples ≥ 5:
      threshold -= 0.01   (more confident)
```

### Reviewing Low-Confidence Utterances

```bash
python -m core.review_cli
```

Shows utterances the brain couldn't confidently classify. You assign the correct intent. Approved patterns are appended to `intents.json` and the k-NN index rebuilds on next restart.

### Correction Words

Say one of these **immediately after** a wrong execution:
- Hinglish: `galat`, `galat hai`, `yeh galat hai`, `wapas`, `galti`
- English: `wrong`, `that's wrong`, `undo`, `no that's wrong`

---

## 8. GUI

Three UI variants exist under `ui/`:

| Folder | Style | Status |
|--------|-------|--------|
| `ui/aeris_v4/` | Dark cyan arc-reactor theme | Exists; not yet wired to new engine |
| `ui/jarvis_v31/` | Glass morphism floating dock | Exists; not yet wired to new engine |
| `ui/ui_laptop/` | Full laptop dashboard with sidebar, splash screen | Exists; not yet wired to new engine |

```bash
python run_gui.py
```

The engine is loaded with `lazy=True` so `setup_iter()` yields progress events between phases. The GUI can paint a loading bar during the cold-boot encoder download (3–5 seconds) without freezing.

All UIs built in PyQt5 and include: chat panel, system tray, custom title bar with window controls, arc-reactor animation, and a logs panel.

---

## 9. Tests

```bash
pytest                              # run all 89 tests (passes in ~3 minutes)
pytest tests/test_pipeline.py       # end-to-end pipeline only
pytest -v                           # verbose with test names
```

**Coverage:**

| Test File | Tests | What It Covers |
|-----------|-------|----------------|
| `test_normalizer.py` | 8 | Lowercase, punctuation strip, URL-safe chars preserved |
| `test_intent_classifier.py` | 13 | 10 canonical Hinglish sentences, top-1 intent, confidence ≥ 0.5 |
| `test_entity_extractor.py` | 13 | App names, URLs, times, queries, person names across 10 inputs |
| `test_sentiment.py` | 8 | Positive/negative/neutral labels, Hinglish booster terms |
| `test_memory.py` | 14 | Store, recall, disk round-trip, Hindi key aliases, unknown-key fallback |
| `test_conversation.py` | 4 | Max-turns rolling, sentiment tags, OpenAI message format |
| `test_disambiguator.py` | 9 | Close-call detection, prompt format, 5 answer parsing forms |
| `test_feedback.py` | 9 | Default threshold, drift down/up, clamp bounds, approve_pattern |
| `test_pipeline.py` | 11 | End-to-end via `process_text()` — isolated tmp DBs, no audio I/O |

All tests run against `process_text()` — no microphone or speaker required. The `conftest.py` provides `tmp_memory_path` and `tmp_feedback_db` fixtures so tests never touch the real data files. The `shared_brain`, `shared_extractor`, and `shared_sentiment` fixtures are session-scoped to avoid re-loading the encoder 89 times.

---

## 10. Configuration

| Setting | File | Default |
|---------|------|---------|
| Sentence encoder model | `core/intent_classifier.py` | `paraphrase-multilingual-MiniLM-L12-v2` |
| k-NN neighbours | `core/intent_classifier.py` | `k=5` |
| Voting temperature | `core/intent_classifier.py` | `10` |
| Conversation window (turns) | `core/main_engine.py` | `8` |
| Bandit α (EMA smoothing) | `core/feedback.py` | `0.1` |
| Default intent threshold | `core/feedback.py` | `0.5` |
| Threshold floor / ceiling | `core/feedback.py` | `[0.40, 0.90]` |
| Disambig close-call margin | `core/disambiguator.py` | `0.05` |
| Ollama model | `core/llm_chat.py` | `phi3:mini` |
| Ollama host | `core/llm_chat.py` | `http://localhost:11434` |
| User memory path | `core/main_engine.py` | `data/user_memory.json` |
| Feedback DB path | `core/main_engine.py` | `data/feedback_log.sqlite` |
| Notes folder | `core/executor.py` | `data/notes/` |
| TTS voice | `core/tts.py` | `hi-IN-NeerjaNeural` |
| STT locale | `core/stt.py` | `en-IN` |

---

## 11. Known Limitations of the Current k-NN Brain

This section is direct about where the current design has structural limits, especially for long-term daily use where your speech patterns, vocabulary, and needs will grow and shift.

### 11.1 — k-NN Does Not Generalize

A k-NN classifier is a lookup over stored patterns. It finds the most similar stored examples and votes. This means:

- **It cannot extrapolate.** If no stored pattern is semantically close to what you said, confidence drops and the system falls back to the LLM. You are always dependent on pattern coverage.
- **It cannot absorb lessons from use.** The review CLI lets you manually add approved patterns, but the brain never updates its own understanding from your actual speech. You must curate patterns yourself.
- **It is stateless during classification.** The classifier sees only the current utterance — not what you said before, not what app is open, not what time it is. The main engine injects context manually for some edge cases, but the classifier itself has no memory of the conversation.

### 11.2 — Confidence Is Cosine Similarity, Not Calibrated Probability

The `confidence` value is the top-1 cosine similarity across the k-NN vote, not a calibrated probability. This means:

- Two completely different utterances can both score `confidence=0.7` for different reasons
- The number does not mean "70% likely to be correct" — it means "this embedding is 0.7 cosine-similar to its nearest neighbour"
- The bandit's per-intent threshold drift partially compensates, but the underlying signal is noisy at the margin

### 11.3 — Pattern Dilution at Scale

Currently ~14 patterns per intent × 21 intents = ~294 patterns. This is the k-NN's comfortable operating range.

As patterns grow:
- **~1,000 patterns:** Multiple similar patterns for adjacent intents pull against each other, reducing confidence for inputs that were previously easy
- **~5,000 patterns:** The 5-neighbour vote pool gets contaminated by patterns from adjacent intents, increasing close-call disambiguation
- **~50,000 patterns:** `sklearn.NearestNeighbors` becomes slow (O(n) linear scan); would need FAISS/HNSW index

The good news is that 5,000–10,000 is likely the realistic ceiling for a personal assistant. The bad news is that accuracy degrades before you get there if patterns are not carefully curated.

### 11.4 — Hinglish Coverage Is Phrasing-Dependent

The multilingual encoder handles semantic similarity between Hindi and English, but edge cases in code-switched speech (mid-sentence script mixing, regional slang, casual contractions) still require pattern coverage. If your natural phrasing differs from what's in `intents.json`, confidence drops.

For example: `"isko launch maar"` instead of `"kholo"` will likely fail until you add that phrasing.

### 11.5 — No Cross-Intent Reasoning

The brain classifies one segment at a time. It has no model of how intents interact or depend on each other:
- Conditional commands: `"agar baadal ho toh remind karo"` — not handled
- Chained intents with shared context: limited by the segment splitter's accuracy
- Pronoun resolution: `"close it"` after `"open chrome"` requires the main engine to explicitly pass the prior-intent context, which it does not currently do

### 11.6 — Reminders Do Not Actually Fire

`set_reminder` acknowledges the reminder verbally but does not schedule anything. There is no background thread watching for reminder times. See §12.3 for the fix.

### 11.7 — Weather Is Hardcoded

`get_weather` returns `"Mausam filhaal suhana hai, around 25 degrees Celsius."` regardless of actual weather, location, or date. See §12.4 for the fix.

### 11.8 — STT Is Online-Dependent

The primary STT is Google (`en-IN` locale). Vosk kicks in offline but its Hindi model quality is noticeably lower. There is no offline STT that matches Google quality in the current build. See §12.6 (faster-whisper) for the fix.

---

## 12. Phase F — Feature Parity & Bug Fixes

This phase fixes what's missing or stubbed in the current build. These are not future ambitions — they are gaps that should be closed before claiming "v1 complete." Ordered by structural impact: §12.1 and §12.2 address the brain's core limitation.

---

### 12.1 — Hybrid Brain: k-NN + Fine-Tuned Transformer Classifier

**The problem:** k-NN generalizes only to stored patterns. For long-term daily use where your speech evolves and new phrasing appears constantly, you need a model that has learned intent *structure*, not just pattern similarity.

**The solution:** Keep k-NN as the fast zero-shot baseline. Add a fine-tunable transformer classifier that trains on your logged utterances as data accumulates from real usage.

**Recommended base model for Hinglish:**

| Model | Size | Why |
|-------|------|-----|
| `ai4bharat/indic-bert` | 592 MB | BERT fine-tuned specifically on Indic languages including Hindi |
| `google/muril` | 892 MB | Google's Multilingual Representations for Indian Languages — strongest Hindi |
| `distilbert-base-multilingual-cased` | 541 MB | Lighter option if RAM is tight |

**Architecture — hybrid routing:**

```
Utterance
    │
    ├─► k-NN (always runs first — fast, ~30ms)
    │       confidence ≥ 0.90  →  execute immediately (k-NN is certain)
    │       confidence 0.60-0.89  →  cross-check with transformer
    │       confidence < 0.60  →  transformer decides
    │
    └─► Transformer classifier (runs when k-NN is uncertain)
            both agree  →  execute with high confidence
            disagree   →  disambiguate between top-2
            transformer low confidence  →  LLM fallback
```

**Training loop — automatic, incremental:**

1. Every utterance in `feedback_log.sqlite` with `user_feedback = 'accepted'` is a positive training sample
2. Every corrected utterance with `correct_intent` set is a negative + true label
3. When 100+ new labelled samples have accumulated (or weekly): run `python -m core.classifier_trainer`
4. New checkpoint replaces old; k-NN stays unchanged as the fast path

```bash
# Training command (create core/classifier_trainer.py for this)
python -m core.classifier_trainer --min-samples 100 --epochs 3
```

**Expected improvement:** With ~500 labelled utterances from real usage, a fine-tuned `indic-bert` will handle out-of-pattern Hinglish phrasings that k-NN misses — especially regional variations and informal contractions.

**Files to create:**
- `core/transformer_classifier.py` — `AutoModelForSequenceClassification` + `AutoTokenizer` wrapper
- `core/classifier_trainer.py` — reads from SQLite, batches training, saves HuggingFace checkpoint
- Update `core/brain.py` — add hybrid routing logic with configurable threshold boundaries

---

### 12.2 — LaBSE Encoder Upgrade (Easy, Significant Impact)

**The problem:** `paraphrase-multilingual-MiniLM-L12-v2` is a good general multilingual encoder but was not specifically optimized for Indic languages or code-switched text.

**The solution:** Drop-in swap to `sentence-transformers/LaBSE` (Language-Agnostic BERT Sentence Embedding). Same API, one line change.

```python
# In core/intent_classifier.py — change this one constant:
_ENCODER_MODEL = "sentence-transformers/LaBSE"
```

The k-NN index auto-rebuilds on next boot using the new embeddings.

**Why LaBSE is better for Hinglish:**
- Trained on 109 languages with parallel corpus alignment (not just multilingual pretraining)
- Produces tighter semantic clustering for code-switched sentences
- Hindi + English embeddings land closer in the same semantic space

**Tradeoff:** LaBSE is ~470 MB vs ~120 MB for MiniLM. Encode time is ~50 ms vs ~30 ms on CPU. The accuracy gain on Hinglish inputs justifies this if you're running on hardware with 8GB+ RAM.

---

### 12.3 — Real Reminders with APScheduler

**The problem:** `set_reminder` is a stub that says "reminder set" and immediately forgets.

**Fix — 30 minutes of work:**

```bash
pip install apscheduler
```

Create `core/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

class ReminderScheduler:
    def __init__(self, tts):
        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.start()
        self._tts = tts

    def add(self, message: str, fire_at: datetime) -> bool:
        self._scheduler.add_job(
            func=lambda: self._tts.speak(f"Reminder sir: {message}"),
            trigger='date',
            run_date=fire_at,
            id=f"reminder_{fire_at.timestamp()}"
        )
        return True

    def list_upcoming(self) -> list:
        return [(job.id, job.next_run_time) for job in self._scheduler.get_jobs()]
```

Update `core/executor.py`:
```python
def set_reminder(self, slots: dict) -> str:
    msg = slots.get("message", "kuch yaad karna hai")
    time_str = slots.get("time", "")
    fire_at = parse_time(time_str)   # add a time parser utility
    if self._scheduler and fire_at:
        self._scheduler.add(msg, fire_at)
        return f"Reminder set: '{msg}' — {time_str} pe yaad dilaoonga."
    return f"Reminder note kar liya: '{msg}' — {time_str} pe."
```

The entity extractor already extracts `time` and `message` slots correctly. The only missing piece is the actual scheduler and a time-string-to-datetime parser.

---

### 12.4 — Real Weather via OpenWeatherMap

**The problem:** `get_weather` returns a hardcoded string.

**Fix — 15 minutes:**

Free API key from [openweathermap.org/api](https://openweathermap.org/api) (no credit card required for the free tier).

```python
import requests

def get_weather(self, city: str = None) -> str:
    city = city or self.memory.get("location") or "Delhi"
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=hi"
    )
    try:
        data = requests.get(url, timeout=5).json()
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        desc = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]
        return (
            f"{city} mein abhi {temp:.0f} degree hai, "
            f"feel ho raha hai {feels:.0f} degree. "
            f"{desc.capitalize()}. Humidity {humidity}%."
        )
    except Exception:
        return "Mausam ka data abhi available nahi hai."
```

Store the API key in a `.env` file (already in `.gitignore`).

---

### 12.5 — Vosk-Based Wake Word Detection

**The problem:** AERIS requires manual script launch. A real assistant should always be listening passively and activate only on "Hey Jarvis" or "Hey AERIS".

**The solution:** Reuse the Vosk model that's already in the dependency stack. Vosk supports **grammar-restricted recognition** — by passing a small JSON grammar of just the wake-word vocabulary, the recognizer becomes a fast, accurate, fully-offline wake word detector. No Porcupine, no API keys, no licensing, no extra dependency.

**Why Vosk grammar restriction is the right tool:**
- Already installed (Vosk is the offline STT fallback)
- ~40 MB model (`vosk-model-small-en-in-0.4` — Indian English, ideal for the user)
- Sub-second latency once the wake word is spoken
- Custom wake words — no need to train a model, just edit the grammar list
- Runs at ~3–5% CPU (single thread)
- Works fully offline, no external service dependency
- Free, open-source (Apache 2.0)

**Implementation — create `core/wake_word.py`:**

```python
import json
import threading
import pyaudio
import vosk


class WakeWordDetector:
    """
    Always-on wake word detector using Vosk grammar-restricted recognition.

    Runs a continuous low-quality mic stream through Vosk constrained to a
    fixed wake-word grammar. When the wake word fires:
      1. Pauses listening (releases mic for the main pipeline)
      2. Calls on_wake() — the main engine takes over for one turn
      3. Resumes listening when on_wake() returns

    Grammar restriction is the key trick: instead of running open-vocabulary
    recognition (slow, hallucinates), we tell Vosk "you may only recognize
    these phrases or [unk]". This makes it both faster and more accurate.
    """

    def __init__(
        self,
        model_path: str,
        wake_words=("jarvis", "aeris", "hey jarvis", "hey aeris"),
        sample_rate: int = 16000,
    ):
        self.model = vosk.Model(model_path)
        self.wake_words = tuple(w.lower() for w in wake_words)
        grammar = json.dumps(list(wake_words) + ["[unk]"])
        self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate, grammar)
        self.sample_rate = sample_rate
        self._listening = threading.Event()
        self._listening.set()
        self._stop = threading.Event()

    def listen(self, on_wake):
        """Block forever. Calls on_wake() once per detected wake event."""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.sample_rate, input=True,
            frames_per_buffer=4000,
        )
        stream.start_stream()
        try:
            while not self._stop.is_set():
                if not self._listening.is_set():
                    self._listening.wait()  # paused while main pipeline owns mic

                data = stream.read(4000, exception_on_overflow=False)
                if self.recognizer.AcceptWaveform(data):
                    text = json.loads(self.recognizer.Result()).get("text", "")
                else:
                    # Partial results give faster wake response (~200 ms)
                    text = json.loads(self.recognizer.PartialResult()).get("partial", "")

                text = text.lower().strip()
                if any(w in text for w in self.wake_words):
                    self.pause()
                    self.recognizer.Reset()
                    on_wake()
                    self.resume()
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def pause(self):  self._listening.clear()
    def resume(self): self._listening.set()
    def stop(self):
        self._stop.set()
        self._listening.set()
```

**Wire it up in `main.py`:**

```python
def voice_mode_with_wake():
    engine = JarvisMainEngine()
    detector = WakeWordDetector(
        model_path="data/models/vosk-model-small-en-in-0.4",
        wake_words=("jarvis", "aeris", "hey jarvis", "hey aeris"),
    )

    def on_wake():
        engine._speak("Yes sir?")
        text = engine._stt.listen()      # main STT (Google or Vosk full model)
        if text:
            response = engine.process_text(text)
            if response:
                engine._speak(response)

    print("Wake word listener active. Say 'Jarvis' or 'AERIS' to start.")
    detector.listen(on_wake)
```

**Setup step (one-time):**
```bash
# Download the Indian English Vosk model (~42 MB)
# https://alphacephei.com/vosk/models  →  vosk-model-small-en-in-0.4
# Unzip into data/models/vosk-model-small-en-in-0.4/
```

**Definition of done:**
- AERIS runs in background. CPU stays ~3–5%.
- Saying "Hey Jarvis" within 2 seconds triggers the assistant. False trigger rate < 1 per hour in normal conversation.
- Wake words are configurable in `main.py` (no code change to the detector).
- Detector pauses cleanly when main pipeline owns the mic, resumes after.

---

### 12.6 — Local STT: faster-whisper (C12 — Deferred)

**The problem:** Google STT requires internet. Vosk Hindi quality is poor.

```bash
pip install faster-whisper
```

```python
from faster_whisper import WhisperModel

class STT:
    def __init__(self, model_size="small"):
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def listen(self) -> str:
        audio = self._record_audio()
        segments, _ = self.model.transcribe(audio, language="hi")
        return " ".join(s.text for s in segments).strip()
```

`whisper-small` (~244 MB): transcribes Hinglish well, real-time on a modern CPU, fully offline.
`whisper-medium` (~769 MB): better Hindi accuracy, ~2x slower.

---

### 12.7 — Spotify API Integration

**The problem:** `play_music` opens Spotify but cannot play a specific track/artist.

```bash
pip install spotipy
```

Free Spotify Developer App: [developer.spotify.com](https://developer.spotify.com) (takes 2 minutes).

```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="user-modify-playback-state user-read-playback-state"
))

def play_track(self, query: str) -> str:
    results = sp.search(q=query, type="track", limit=1)
    tracks = results["tracks"]["items"]
    if not tracks:
        return f"'{query}' nahi mila Spotify pe."
    uri = tracks[0]["uri"]
    name = tracks[0]["name"]
    artist = tracks[0]["artists"][0]["name"]
    sp.start_playback(uris=[uri])
    return f"{artist} ka '{name}' chala raha hoon."
```

Enables: *"Arijit Singh ka Tum Hi Ho chala do"* → plays the exact track on your active Spotify device.

---

### 12.8 — GUI Rewire

**The problem:** Three UI variants exist but none connect to `JarvisMainEngine`. The visual interface currently does not function as an assistant.

**What needs to happen:**
1. Wire `JarvisMainEngine(lazy=True)` into `run_gui.py`
2. Call `engine.process_text(text)` from the chat panel's send button and voice input handler
3. Pipe `setup_iter()` progress events to the splash screen / loading bar (already supported by the engine)
4. Stream responses back to the chat panel as assistant messages
5. Pick `ui/aeris_v4` as the canonical UI (most complete components)

The engine's `lazy=True` + `setup_iter()` API was specifically designed for this GUI wiring — the splash screen painting loop already knows how to receive `(log_type, label, pct)` tuples.

---

### 12.9 — File & Clipboard Operations

| Intent | Example | Implementation |
|--------|---------|----------------|
| `open_file` | "resume kholo", "X file kholo" | `glob` search + `os.startfile` |
| `create_folder` | "projects mein new folder banao" | `os.makedirs` |
| `move_file` | "X ko downloads mein move karo" | `shutil.move` |
| `delete_file` | "temp folder clean karo" | `send2trash` (sends to Recycle Bin, recoverable) |
| `clipboard_copy` | "yeh copy kar lo" | `pyperclip.copy(text)` |
| `clipboard_paste` | "paste karo" | `pyperclip.paste()` |

---

### 12.10 — Multilingual Sentiment Upgrade

Replace VADER with `cardiffnlp/twitter-xlm-roberta-base-sentiment`. True multilingual sentiment — understands Hindi script and Hinglish without the manual booster lexicon. 3-class output (positive/neutral/negative) with calibrated probabilities.

```python
from transformers import pipeline

_sentiment_pipe = pipeline(
    "text-classification",
    model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
    return_all_scores=False
)
```

Tradeoff: ~500 MB model, ~50 ms inference vs VADER's <1 ms. Worth combining with the transformer brain upgrade in §12.1 since you're loading transformers anyway.

---

## 13. Phase G — Next-Level Upgrades

This phase is what takes AERIS from "well-built personal assistant" to **a genuinely capable AI agent**. Each item below is a 1-to-3 day project that significantly expands what AERIS can do. They are independent — pick any order.

The unifying theme: stop treating AERIS as a command parser and start treating it as a reasoning agent that has tools, vision, and presence.

---

### 13.1 — LLM Function Calling (Tool Use) — The Single Biggest Upgrade

**The vision:** Right now the LLM only does chit-chat fallback. The k-NN brain is the primary router. This means anything outside the trained patterns → fails or hits the LLM as plain conversation.

**Flip the model:** Make the LLM the **primary reasoning layer** that *calls AERIS skills as tools*, with k-NN as the fast-path shortcut for common commands.

**How it works:**

```python
SYSTEM_PROMPT = """You are AERIS. You can call these tools:

{
  "open_app":     {"args": ["app_name"]},
  "close_app":    {"args": ["app_name"]},
  "get_weather":  {"args": ["city?"]},
  "set_reminder": {"args": ["message", "fire_at_iso"]},
  "search_web":   {"args": ["query"]},
  "play_youtube": {"args": ["query"]},
  "calculate":    {"args": ["expression"]},
  "send_whatsapp":{"args": ["recipient", "message"]},
  ...
}

For each user input, respond with EXACTLY ONE of:
  (a) {"tool": "<name>", "args": {...}}      — to call a skill
  (b) {"tool": "chat", "reply": "..."}       — to just talk
  (c) {"tool": "plan", "steps": [...]}       — for multi-step tasks
"""
```

**Routing logic:**

```
Utterance
    │
    ├─► k-NN predict (fast, ~30ms)
    │       confidence ≥ 0.85  →  execute directly (skip LLM)
    │       confidence < 0.85  →  LLM with tool calling
    │
    └─► LLM reasoning
            returns {"tool": "open_app", "args": {"app_name": "chrome"}}
                → executor.execute("open_app", {"app_name": "chrome"})
            returns {"tool": "plan", "steps": [...]}
                → executes each step in sequence
            returns {"tool": "chat", "reply": "..."}
                → speak the reply
```

**Why this is transformational:**

| Before (k-NN only) | After (LLM tool calling) |
|--------------------|--------------------------|
| "open chrome" → works | "open chrome" → works (k-NN fast path) |
| "isko launch maar" → fails (unseen pattern) | "isko launch maar" → LLM understands intent, calls open_app |
| "remind me about mom's birthday on Friday" → fails to extract date | LLM parses "Friday" into ISO datetime, calls set_reminder correctly |
| "play that song from Animal" → search_web at best | LLM searches Spotify, calls play_track with proper query |
| "schedule a 30-min call with Raj tomorrow at 4" | LLM calls schedule_meeting with all slots filled correctly |
| Multi-step tasks impossible | "weather batao aur agar barish ho toh raincoat reminder lagao" → conditional plan |

**Files to create:**
- `core/tool_router.py` — JSON parser + executor dispatch from LLM output
- `core/llm_planner.py` — multi-step plan execution with rollback
- Update `core/llm_chat.py` — add `reply_with_tools()` method that returns structured JSON
- Update `core/main_engine.py` — add the routing decision

**Model choice:** `phi3:mini` already supports tool-style JSON output. For better reliability, upgrade to `qwen2.5:3b` or `llama3.1:8b` (both available via Ollama) — these are explicitly trained for function calling.

**Definition of done:**
- "remind me about mom's birthday next Friday at 6 pm" → LLM extracts message + ISO datetime, calls `set_reminder` correctly
- "open chrome aur YouTube pe lofi chala do" → LLM emits a 2-step plan, both steps execute
- Failed tool calls (invalid args) trigger an LLM retry with the error message in context

---

### 13.2 — Skill Plugin System (Drop-in Extensibility)

**The problem:** Adding a new skill currently requires editing `intents.json`, `executor.py`, and `entity_extractor.py` — three different places. This is friction every time you want a new capability.

**The solution:** A `skills/` folder where each `.py` file becomes a self-registering skill. Auto-discovery at boot.

**Each skill file:**

```python
# skills/whatsapp.py
from core.skill_registry import skill

@skill(
    name="send_whatsapp",
    description="Send a WhatsApp message to a contact by name",
    patterns=[
        "X ko whatsapp message bhejo Y",
        "send X message Y on whatsapp",
        "whatsapp pe X ko bolo Y",
    ],
    required_entities=["recipient", "message"],
    prompts={
        "recipient": "Kisko message bhejna hai?",
        "message":   "Kya likhna hai message mein?",
    },
)
def send_whatsapp(slots: dict) -> str:
    import pywhatkit
    pywhatkit.sendwhatmsg_instantly(
        phone_no=resolve_contact(slots["recipient"]),
        message=slots["message"],
    )
    return f"{slots['recipient']} ko message bhej diya."
```

**At boot:**
```python
# core/skill_registry.py walks skills/ folder, imports each module,
# registers each @skill decorator into a global REGISTRY.
# 
# JarvisBrain merges patterns from REGISTRY into the k-NN index.
# ActionExecutor's dispatch dict is built from REGISTRY at __init__.
# EntityExtractor's prompt map is built from REGISTRY.required_entities.
```

**Files to create:**
- `core/skill_registry.py` — `@skill` decorator + global registry + auto-discovery
- `skills/__init__.py`
- Refactor `core/executor.py` — replace hardcoded dispatch dict with registry lookup
- Refactor `data/intents.json` — keep as bootstrap; new skills register their own patterns

**Migration:** Convert each existing intent in `executor.py` into a `skills/<name>.py` file. The user only ever has to edit one file per skill from this point on.

**Bonus:** Sharing skills becomes trivial — drop someone else's `whatsapp.py` into your `skills/` folder and it just works.

---

### 13.3 — Vision: Screen OCR + Computer Use

**The vision:** AERIS reads what's on your screen and acts on it.

**Use cases:**
- *"Yeh article padh do"* — OCR the visible window → TTS reads it aloud
- *"Yeh error message kya hai?"* — OCR the dialog → LLM explains the error in Hinglish
- *"Login button pe click karo"* — OCR finds the button → `pyautogui.click()` on its coordinates
- *"Form fill kar do mere details se"* — OCR identifies form fields → types from `user_memory`
- *"Screenshot mein kaunsa app khula hai?"* — OCR window title → answer

**Stack:**

```bash
pip install pytesseract pillow pyautogui mss
# Plus install Tesseract binary: github.com/UB-Mannheim/tesseract/wiki
# Add hindi language pack: choose 'hin' during install
```

**Implementation:**

```python
# core/vision.py
import mss
import pytesseract
from PIL import Image

class ScreenVision:
    def __init__(self):
        self._sct = mss.mss()

    def read_screen(self, region=None) -> str:
        """OCR the full screen or a region. Returns extracted text."""
        monitor = region or self._sct.monitors[1]
        img = Image.frombytes("RGB", (monitor["width"], monitor["height"]),
                              self._sct.grab(monitor).rgb)
        # eng+hin handles English+Hindi mixed UI
        return pytesseract.image_to_string(img, lang="eng+hin")

    def find_text_location(self, target: str) -> tuple[int, int] | None:
        """Returns (x, y) center of the bounding box for `target` text on screen."""
        monitor = self._sct.monitors[1]
        img = Image.frombytes("RGB", (monitor["width"], monitor["height"]),
                              self._sct.grab(monitor).rgb)
        data = pytesseract.image_to_data(img, lang="eng+hin",
                                         output_type=pytesseract.Output.DICT)
        for i, word in enumerate(data["text"]):
            if target.lower() in word.lower():
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                return (x, y)
        return None
```

**New skills enabled:**
- `read_screen`, `read_window`, `find_on_screen`, `click_text`, `describe_screen` (LLM summarizes OCR output)

**Why this is huge:** Combined with §13.1 (tool calling), the LLM can now perceive AND act. *"AERIS, fill the contact form with my email"* → LLM plans: 1) OCR find "email" field, 2) click it, 3) type stored email. This is real computer-use capability.

---

### 13.4 — Streaming STT with Partial Results

**The problem:** Current STT waits for silence, then transcribes the whole utterance. Feels slow and unresponsive.

**The solution:** Vosk supports `PartialResult()` — words become available as the user speaks them. Show partial transcription in the GUI in real time. Send the final transcription to the brain only when silence is detected.

**Why it matters:** Latency perception drops dramatically. *"chrome..."* shows on screen instantly, *"chrome kholo"* completes 100ms later, response starts before user even finishes their sentence in some cases.

**Implementation pattern:**

```python
def listen_streaming(self, on_partial, on_final):
    while True:
        data = stream.read(4000, exception_on_overflow=False)
        if self.recognizer.AcceptWaveform(data):
            final = json.loads(self.recognizer.Result())["text"]
            if final:
                on_final(final)
                return
        else:
            partial = json.loads(self.recognizer.PartialResult())["partial"]
            if partial:
                on_partial(partial)  # GUI updates the chat bubble live
```

In the GUI, the user's chat bubble updates token-by-token as they speak. Once `on_final` fires, send to `engine.process_text()`.

---

### 13.5 — Google Calendar Integration

**The vision:** `schedule_meeting` actually creates calendar events. *"Aaj meri meetings batao"* lists today's events. *"Kab free hoon kal?"* finds free slots.

**Stack:**
```bash
pip install google-auth-oauthlib google-api-python-client
```

OAuth flow once at setup (browser pops up, user grants access, token cached locally to `data/google_token.json`).

**New skills:**
- `create_event` — replaces stub `schedule_meeting` with real event creation
- `list_events` — *"meri meetings batao"* / *"kal kya kya hai"*
- `find_free_slot` — *"kab free hoon kal afternoon?"*
- `cancel_event` — *"3 baje wali meeting cancel karo"*

**Bonus:** Combined with §13.1 (LLM tool calling), the LLM can negotiate scheduling autonomously. *"Raj se 30 min ki call lagao kal"* → LLM calls `find_free_slot` for tomorrow → calls `create_event` with the chosen slot → confirms.

---

### 13.6 — WhatsApp Automation

**The vision:** Send WhatsApp messages by voice without touching your phone.

**Stack:**
```bash
pip install pywhatkit
```

`pywhatkit` automates WhatsApp Web — opens the browser, navigates to a contact, types and sends. Free, no API key. Slower than the official Business API but works for personal use.

**New skills:**
- `send_whatsapp` — *"Raj ko whatsapp pe bolo main 5 baje aaonga"*
- `read_whatsapp` — read latest unread messages (requires WhatsApp Web Selenium scrape)

**Contact resolution:** Read contacts from `data/contacts.json` (created by user). Map names → phone numbers. Hindi name aliases supported via the same alias system as the memory module.

---

### 13.7 — News Briefing (RSS + LLM Summary)

**The vision:** *"Aaj ki news batao"* → fetches latest headlines from your chosen sources → LLM summarizes the top 5 stories in Hinglish → AERIS reads them aloud.

**Stack:**
```bash
pip install feedparser
```

Feed sources stored in `data/news_sources.json` (user-editable):
```json
{
  "tech":     ["https://hnrss.org/frontpage", "https://techcrunch.com/feed/"],
  "india":    ["https://www.thehindu.com/news/national/feeder/default.rss"],
  "business": ["https://www.livemint.com/rss/news"]
}
```

**Implementation:**

```python
def daily_briefing(self, category: str = "all") -> str:
    sources = self.news_sources.get(category, [])
    headlines = []
    for url in sources:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            headlines.append(f"- {entry.title}: {entry.summary[:200]}")

    prompt = f"Summarize these headlines in 5 short Hinglish bullet points:\n\n" + "\n".join(headlines)
    return self.llm.reply_raw(prompt)
```

**Bonus:** Schedule a daily briefing via §12.3 APScheduler — *"har subah 8 baje news batana"* → adds a recurring scheduler job.

---

### 13.8 — Translation Engine (Offline Hindi ↔ English)

**The vision:** Built-in translation that works offline. Useful both for users and as a tool the LLM can call.

**Stack:**
```bash
pip install argostranslate
# Or for higher quality (1.1 GB model):
# pip install ctranslate2
# + IndicTrans2 model from ai4bharat
```

**Argos Translate** — fully offline, free, OpenNMT-based. Hindi↔English package is ~200 MB. Quality is good for casual use.

**IndicTrans2** (ai4bharat) — best-in-class Hindi-English, also covers 22 Indian languages. ~1.1 GB but state-of-the-art.

**New skills:**
- `translate` — *"yeh sentence hindi mein translate karo: ..."*
- `live_translate` — translate user's spoken Hindi → English text on screen (great for meetings)

---

### 13.9 — Voice Cloning TTS (Coqui XTTS-v2)

**The vision:** Replace Edge-TTS Neerja with a voice you choose — yours, a celebrity's (with consent), or a custom-tuned warm assistant voice.

**Stack:**
```bash
pip install TTS  # Coqui TTS
```

Coqui XTTS-v2 clones any voice from **6 seconds of reference audio**. Multilingual including Hindi. Runs on CPU at near-real-time, GPU at much faster.

**Setup:**
1. Record 6 seconds of the target voice → `data/voices/aeris_reference.wav`
2. Update `core/tts.py` to load XTTS-v2 model
3. Pass `speaker_wav` parameter on every synthesis call

**Why it matters:** Personality. The current Neerja voice is a generic Indian female TTS. A custom voice — slow, warm, slightly textured — gives AERIS *character*. This is the difference between Siri and Jarvis-from-Iron-Man.

**Tradeoff:** Coqui XTTS is ~2 GB and ~1.5x slower than Edge-TTS on CPU. Worth it for the personality upgrade.

---

### 13.10 — Mobile Companion (LAN Bridge)

**The vision:** Talk to AERIS from your phone. Same brain, different mic.

**Architecture:**

```
[Phone App]  ──WebSocket──►  [Flask/FastAPI on Desktop]  ──►  JarvisMainEngine
   ▲                                                              │
   └──────────────── audio + responses ◄──────────────────────────┘
```

**Stack:**
```bash
pip install fastapi uvicorn websockets
```

**Implementation:**
- Add `core/lan_server.py` — FastAPI WebSocket endpoint that accepts audio chunks, runs them through `engine.process_text()`, streams responses back as audio
- Mobile client: a minimal Flutter or React Native app (or even a PWA) that records mic, sends to desktop, plays response

**Use case:** Your laptop is on but closed in another room. You ask your phone *"AERIS, system info batao"* → phone hits laptop's LAN endpoint → laptop runs the skill → speaks response back through phone speaker. Same memory, same context, same skills.

**Security:** Bind to localhost + LAN only. Token auth in WebSocket handshake. No public internet exposure.

---

### 13.11 — Encrypted Memory Vault (Privacy)

**The problem:** `data/user_memory.json` stores sensitive facts (location, employer, contacts) in plaintext. If the laptop is compromised or shared, anyone can read it.

**The solution:** AES-256 encryption of the memory file with a key derived from a user-supplied passphrase (PBKDF2). Decrypted in-memory only at boot.

**Stack:**
```bash
pip install cryptography
```

**Two-mode operation:**
- **Open mode** (current behaviour): no encryption, easy debugging
- **Vault mode**: passphrase prompt at startup, all reads/writes go through `Fernet` encryption

Add a `:vault on` REPL command that converts the existing `user_memory.json` to encrypted form.

---

### 13.12 — Usage Analytics Dashboard

**The vision:** A page in the GUI showing:
- Total utterances processed
- Most-used intents (bar chart)
- Per-intent accuracy (from feedback DB)
- Threshold drift over time (line chart)
- Recent corrections (so you can spot a pattern that needs more training)
- Conversation sentiment trend (are you happier with AERIS over time?)

All data is already in `data/feedback_log.sqlite`. Just need a dashboard tab in `ui/aeris_v4/` that queries it.

**Stack:**
```bash
pip install pyqtgraph  # for charts
```

This is mostly UI work — the data is already being collected. Useful both for the user (see how AERIS is performing) and for development (spot which intents need more pattern coverage).

---

### Phase G — Suggested Implementation Order

| Order | Item | Effort | Why first |
|-------|------|--------|-----------|
| 1 | §13.1 LLM Tool Calling | 2 days | Single biggest capability multiplier |
| 2 | §13.2 Skill Plugin System | 1 day | Foundation for everything else |
| 3 | §13.4 Streaming STT | 0.5 day | Quick perceived-latency win |
| 4 | §13.3 Vision (OCR + Click) | 2 days | Unlocks computer use |
| 5 | §13.5 Google Calendar | 1 day | Highest daily-use value |
| 6 | §13.7 News Briefing | 0.5 day | Perfect daily-driver feature |
| 7 | §13.6 WhatsApp | 1 day | High utility for Indian users |
| 8 | §13.9 Voice Cloning | 1 day | Pure personality upgrade |
| 9 | §13.10 Mobile Bridge | 2 days | Major reach extension |
| 10 | §13.8 Translation | 0.5 day | Easy add-on |
| 11 | §13.12 Analytics Dashboard | 1 day | Polish |
| 12 | §13.11 Encrypted Vault | 0.5 day | Security hardening |

Total: ~13 days of focused work transforms AERIS from a polished personal assistant into something that genuinely competes with commercial AI agents — while remaining fully local and Hinglish-native.

---

## 14. Dependency Reference

```
# Audio I/O (current)
SpeechRecognition      # online STT (Google en-IN)
vosk                   # offline STT fallback
pyaudio                # microphone input
edge-tts               # online TTS (hi-IN-NeerjaNeural)
pyttsx3                # offline TTS fallback
pygame                 # audio playback

# NLP / Brain (current)
sentence-transformers  # multilingual encoder (MiniLM-L12-v2)
scikit-learn           # k-NN intent index
spacy                  # NER (optional; python -m spacy download en_core_web_sm)
vaderSentiment         # sentiment analysis
rapidfuzz              # fuzzy fallback

# LLM chit-chat
requests               # Ollama HTTP client

# UI / System
PyQt5                  # GUI framework
psutil                 # battery, CPU, RAM metrics
keyboard               # hotkey listener
pyautogui              # screenshot capture
opencv-python          # gesture recognition
mediapipe              # hand landmark detection

# Misc
pyyaml
nltk

# Dev / Test
pytest

# Phase F — Feature parity (not yet installed)
# transformers          # fine-tuned intent classifier + multilingual sentiment
# apscheduler           # real background reminder scheduler
# faster-whisper        # local offline STT (replaces Google STT)
# spotipy               # Spotify track-level control
# pyperclip             # clipboard read/write
# send2trash            # safe file deletion (to Recycle Bin)
#                       # Wake word: uses existing Vosk dependency (no new pkg)

# Phase G — Next-level upgrades (not yet installed)
# pytesseract           # screen OCR (§13.3)        → also requires Tesseract binary + hin lang pack
# mss                   # fast screen capture (§13.3)
# google-auth-oauthlib  # Google Calendar OAuth (§13.5)
# google-api-python-client  # Calendar API client (§13.5)
# pywhatkit             # WhatsApp Web automation (§13.6)
# feedparser            # RSS news ingestion (§13.7)
# argostranslate        # offline Hindi↔English (§13.8)
# TTS                   # Coqui XTTS-v2 voice cloning (§13.9)
# fastapi + uvicorn + websockets  # mobile LAN bridge (§13.10)
# cryptography          # encrypted memory vault (§13.11)
# pyqtgraph             # analytics dashboard charts (§13.12)
```

---

## 15. Project Layout

```
New version- 3.0/
│
├── main.py                       # Entry point. --text for REPL, default for voice.
├── run_gui.py                    # GUI entry point (PyQt5)
├── requirements.txt
├── BRAIN_CHECKPOINTS.md          # Build progress tracker (C1–C12 status + validation logs)
├── BRAIN_BUILD_PLAN.md           # Detailed spec for each checkpoint
│
├── core/
│   ├── brain.py                  # JarvisBrain: encoder lifecycle + index management
│   ├── intent_classifier.py      # Multilingual k-NN intent classifier
│   ├── normalizer.py             # Lightweight text normalization
│   ├── entity_extractor.py       # 4-layer entity extraction (regex/gazetteer/NER/residual)
│   ├── sentiment.py              # VADER + 30 Hinglish booster terms
│   ├── memory.py                 # Persistent user facts + auto-detect + recall
│   ├── conversation.py           # Rolling 8-turn short-term context
│   ├── llm_chat.py               # Ollama HTTP client + system prompt assembly
│   ├── feedback.py               # SQLite utterance log + bandit threshold policy
│   ├── disambiguator.py          # Close-call detection + answer parsing
│   ├── state_manager.py          # Slot-filling + disambiguation state machine
│   ├── executor.py               # 21 intent action handlers
│   ├── main_engine.py            # Top-level pipeline orchestrator (process_text)
│   ├── utterance_parser.py       # Multi-command splitter + subspan intent scanner
│   ├── intent_engine.py          # Fuzzy fallback (legacy, rarely hit)
│   ├── review_cli.py             # Interactive low-confidence pattern review CLI
│   ├── stt.py                    # Speech-to-text (Google + Vosk fallback)
│   └── tts.py                    # Text-to-speech (Edge-TTS Neerja + pyttsx3 fallback)
│
├── data/
│   ├── intents.json              # 21 intents × ~14 Hinglish patterns
│   ├── entities.json             # App name aliases (25 apps)
│   ├── user_memory.json          # Persistent user facts (auto-created on first use)
│   ├── feedback_log.sqlite       # Utterance log + bandit thresholds (auto-created)
│   ├── hinglish_dict.json        # Reference dictionary
│   ├── notes/                    # Created notes (timestamped .txt files)
│   ├── audio_cache/              # Cached TTS audio
│   └── models/
│       ├── intent_index.pkl      # Cached k-NN index (auto-rebuilt on intents.json change)
│       ├── intent_metadata.json  # Hash + counts + encoder name + build timestamp
│       └── hand_landmarker.task  # MediaPipe hand gesture model
│
├── ui/
│   ├── aeris_v4/                 # Dark cyan arc-reactor UI (recommended for rewire)
│   │   ├── main_window.py
│   │   ├── arc_reactor.py        # Animated arc reactor widget
│   │   ├── chat_panel.py
│   │   ├── sidebar.py
│   │   ├── logs_panel.py
│   │   ├── title_bar.py
│   │   └── theme.py
│   ├── jarvis_v31/               # Glass morphism floating dock
│   ├── ui_laptop/                # Full laptop dashboard with splash + sidebar
│   └── ui_legacy/                # Previous generation UI (reference only, do not edit)
│
├── utils/
│   ├── gesture.py                # MediaPipe hand gesture → command bridge
│   └── monitor.py                # Background system metrics poller
│
└── tests/
    ├── conftest.py               # Fixtures: isolated tmp paths, session-scoped brain/extractor
    ├── test_normalizer.py        # 8 tests
    ├── test_intent_classifier.py # 13 tests
    ├── test_entity_extractor.py  # 13 tests
    ├── test_sentiment.py         # 8 tests
    ├── test_memory.py            # 14 tests
    ├── test_conversation.py      # 4 tests
    ├── test_disambiguator.py     # 9 tests
    ├── test_feedback.py          # 9 tests
    └── test_pipeline.py          # 11 end-to-end tests
```

**Folders to be created during Phase G:**

```
skills/                           # §13.2 — drop-in skill plugins (auto-discovered)
    whatsapp.py
    calendar.py
    news.py
    translate.py
    ...

data/voices/                      # §13.9 — voice cloning reference audio
    aeris_reference.wav

data/contacts.json                # §13.6 — name → phone mapping
data/news_sources.json            # §13.7 — RSS feed list per category
data/google_token.json            # §13.5 — cached OAuth token (in .gitignore)
data/models/vosk-model-small-en-in-0.4/  # §12.5 — wake word model
```

---

## 16. Build Status

| Checkpoint | What It Added | Status |
|------------|---------------|--------|
| C1 | Multilingual k-NN brain, MiniLM encoder, auto-caching index | ✅ Done — 2026-04-25 |
| C2 | 4-layer entity extractor (regex + gazetteer + spaCy NER + residual span) | ✅ Done — 2026-04-25 |
| C3 | VADER sentiment + ~30 Hinglish booster terms | ✅ Done — 2026-04-25 |
| C4 | Persistent user memory, natural-language fact detection + Hindi recall aliases | ✅ Done — 2026-04-25 |
| C5 | Rolling 8-turn conversation history with OpenAI message export | ✅ Done — 2026-04-25 |
| C6 | Ollama LLM chit-chat fallback (Phi-3 / Llama 3.2), health-check, graceful degradation | ✅ Done — 2026-04-25 |
| C7 | SQLite utterance log, contextual bandit threshold learning, review CLI | ✅ Done — 2026-04-25 |
| C8 | Close-call disambiguation, Hinglish prompt, 5-form answer parser | ✅ Done — 2026-04-25 |
| C9 | Full pipeline rewire — all 8 modules wired into `process_text()`, audio isolation | ✅ Done — 2026-04-26 |
| C10 | Memory recall via executor + `detect_and_recall` + Hindi key aliases | ✅ Done — 2026-04-26 |
| C11 | 89 pytest tests, text-mode REPL with `:facts` / `:stats` / `:help` | ✅ Done — 2026-04-26 |
| C12 | Local STT (faster-whisper) + local TTS (Piper) | ⏸ Deferred (online STT/TTS stays) |

### Phase F — Feature Parity & Bug Fixes

| Item | Description | Status |
|------|-------------|--------|
| F1 | Hybrid transformer classifier (indic-bert fine-tuned on logged utterances) | 📋 Planned — §12.1 |
| F2 | LaBSE encoder upgrade (drop-in, better Hinglish accuracy) | 📋 Planned — §12.2 |
| F3 | APScheduler real reminders (reminders that actually fire) | ✅ Shipped — v3.3 |
| F4 | OpenWeatherMap real weather API | ✅ Shipped — v3.3 (`skills/weather.py`, needs API key) |
| F5 | Vosk-based wake word detection (reuses existing dependency) | ✅ Shipped — v3.3 (`--wake` mode) |
| F6 | Local STT via faster-whisper (replaces Google STT primary) | 📋 Planned — §12.6 |
| F7 | Spotify API track-level control | ✅ Shipped — v3.3 (`skills/spotify_control.py`, needs OAuth) |
| F8 | GUI rewire to JarvisMainEngine | 📋 Planned — §12.8 |
| F9 | File + clipboard operations | ✅ Shipped — v3.3 (`skills/clipboard.py`, `skills/file_ops.py`) |
| F10 | Multilingual sentiment (XLM-RoBERTa) | 📋 Planned — §12.10 |

### Phase G — Next-Level Upgrades

| Item | Description | Status |
|------|-------------|--------|
| G1 | LLM function calling (LLM as primary reasoner, k-NN as fast path) | ✅ Shipped — v3.3 (`core/tool_router.py`, `LLMChat.reply_with_tools`) |
| G2 | Skill plugin system (drop-in `skills/*.py` auto-discovery) | ✅ Shipped — v3.3 (`core/skill_registry.py`) |
| G3 | Vision: screen OCR + computer use (Tesseract + pyautogui) | ✅ Shipped — v3.3 (`skills/vision.py`, needs Tesseract) |
| G4 | Streaming STT with partial results (live transcription) | ✅ Shipped — v3.3 (`STT.listen_streaming`) |
| G5 | Google Calendar integration (real event creation + free-slot finding) | 📋 Planned — §13.5 |
| G6 | WhatsApp automation (pywhatkit) | ✅ Shipped — v3.3 (`skills/whatsapp.py`, needs pywhatkit) |
| G7 | News briefing (RSS + LLM Hinglish summary) | ✅ Shipped — v3.3 (`skills/news.py`) |
| G8 | Translation engine (Argos / IndicTrans2 offline) | ✅ Shipped — v3.3 (`skills/translate.py`, needs argostranslate) |
| G9 | Voice cloning TTS (Coqui XTTS-v2) | 📋 Planned — §13.9 |
| G10 | Mobile companion app (LAN WebSocket bridge) | 📋 Planned — §13.10 |
| G11 | Encrypted memory vault (AES-256 with passphrase) | ✅ Shipped — v3.3 (`core/vault.py`, `--vault` flag) |
| G12 | Usage analytics dashboard (charts from feedback DB) | 📋 Planned — §13.12 |

---

## End State

When Phase F + G are complete, AERIS will be:

- **Always-on** — wake-word activated, no manual launch
- **Reasoning-driven** — LLM with tool calling decides what to do, k-NN handles the fast path
- **Extensible** — drop a Python file into `skills/`, get a new capability
- **Vision-capable** — reads your screen, clicks buttons, fills forms
- **Connected** — Calendar, WhatsApp, news, weather, translation
- **Personal** — custom-cloned voice, encrypted memory vault, your phone as a remote
- **Self-improving** — every accepted utterance becomes training data for the next classifier checkpoint
- **Fully Hinglish-native** end to end — STT, brain, sentiment, LLM, TTS all multilingual

All while staying **fully local** for the core pipeline. No cloud dependency for intent routing, memory, or system control. Cloud APIs (Calendar, WhatsApp, OpenWeatherMap) are opt-in per-skill and can be swapped or disabled.
