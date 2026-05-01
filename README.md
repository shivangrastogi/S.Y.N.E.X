# A.E.R.I.S / JARVIS v3.2

**Adaptive Emotional Reasoning & Intelligent System**
*A production-grade, Hinglish-native personal AI assistant for Windows*

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [File Structure](#3-file-structure)
4. [All Commands & Voice Triggers](#4-all-commands--voice-triggers)
5. [All Automations & Background Processes](#5-all-automations--background-processes)
6. [Built-in Intents & Skills](#6-built-in-intents--skills)
7. [NLP Pipeline](#7-nlp-pipeline)
8. [GUI Components](#8-gui-components)
9. [Data & Configuration](#9-data--configuration)
10. [Testing](#10-testing)
11. [Dependencies & Setup](#11-dependencies--setup)
12. [Project Stats](#12-project-stats)
13. [Roadmap — Next 12 Months](#13-roadmap--next-12-months)

---

## 1. Project Overview

AERIS is a fully local, Hinglish-speaking personal AI assistant that runs on Windows. It listens continuously via microphone, understands mixed Hindi-English commands, executes desktop automation tasks, learns from user corrections, and falls back to a local LLM (Ollama/phi3) for open-ended conversation.

**Core design principles:**
- No cloud dependency for inference — all NLP runs locally
- Native Hinglish understanding without translation
- Reward-shaped per-intent learning from user feedback
- Full PyQt5 GUI with animated reactor, floating dock, and glass chat panel
- Graceful degradation when optional dependencies are missing (spaCy, Vosk, Ollama)

**Entry points:**
```bash
python main.py            # Voice mode (STT → brain → TTS)
python main.py --text     # Text-only REPL
python main.py --verbose  # Debug logging
python run_gui.py         # PyQt5 GUI (JARVIS v3.1 window)
```

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ENTRY LAYER                          │
│   main.py (terminal)         run_gui.py (Qt5 GUI)           │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    BRAIN PIPELINE                           │
│                   main_engine.py                            │
│                                                             │
│  1. State Check (slot-fill / disambig pending?)             │
│  2. Memory Recall (before splitting)                        │
│  3. Feedback Window (one-turn correction)                   │
│  4. Cancel Keyword Check                                    │
│  5. Multi-Command Split (utterance_parser)                  │
│  Per segment:                                               │
│    ├── Sentiment Classification (sentiment.py)              │
│    ├── Subspan Scanner / Filler Strip                       │
│    ├── Gazetteer Override (app name + verb)                 │
│    ├── Confidence Threshold Check (feedback.get_threshold)  │
│    ├── Disambiguation Decision (disambiguator.py)           │
│    ├── Entity Extraction (entity_extractor.py)              │
│    └── Slot-Fill or Execute (executor.py)                   │
│  Fallback: LLM Chit-Chat (llm_chat.py → Ollama)            │
└─────────┬───────────────────────────────────────┬───────────┘
          │                                       │
┌─────────▼──────┐                    ┌───────────▼──────────┐
│   BRAIN CORE   │                    │   ACTION EXECUTOR    │
│  brain.py      │                    │  executor.py         │
│  ↓             │                    │  19 skills           │
│  IntentClassif │                    │  25+ app aliases     │
│  (MiniLM+k-NN) │                    │  Windows API calls   │
└────────────────┘                    └──────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│                   SUPPORT MODULES                          │
│  memory.py   conversation.py   feedback.py   state_mgr.py  │
│  normalizer  sentiment        disambiguator  utterance_pars │
└────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│                   AUDIO I/O LAYER                          │
│    stt.py (Google SR → Vosk fallback)                      │
│    tts.py (Edge-TTS → pyttsx3 fallback)                    │
│    voice_engine.py (wake/sleep state machine + Qt signals) │
└────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│                   GUI LAYER (jarvis_v31)                   │
│  main_window.py  →  BrainWorker + VoiceWorker + SpeakWorker│
│  glass_chat_panel    reactor    floating_dock    logs_bar   │
└────────────────────────────────────────────────────────────┘
```

**Threading model:**
- Qt main thread — UI event loop
- `BrainWorker` QThread — heavy NLP processing
- `VoiceWorker` QThread — continuous mic listening
- `SpeakWorker` QThread — async TTS playback
- Daemon threads — Vosk model pre-loading, voice capture loop

---

## 3. File Structure

```
new version-3.0/
│
├── main.py                         Terminal entry point (voice + text REPL)
├── run_gui.py                      PyQt5 GUI launcher (JARVIS v3.1)
├── requirements.txt                Full dependency list
│
├── core/                           Brain pipeline — 20 files, ~3,700 lines
│   ├── main_engine.py             Orchestrator — full pipeline (419 lines)
│   ├── brain.py                   Intent classifier wrapper (41 lines)
│   ├── intent_classifier.py       MiniLM encoder + k-NN (280 lines)
│   ├── intent_engine.py           Fuzzy fallback (53 lines)
│   ├── entity_extractor.py        4-layer extraction (345 lines)
│   ├── normalizer.py              Hinglish text cleaner (50 lines)
│   ├── sentiment.py               VADER + Hinglish lexicon (123 lines)
│   ├── memory.py                  Persistent user facts (371 lines)
│   ├── conversation.py            Ephemeral context buffer (82 lines)
│   ├── llm_chat.py                Ollama chit-chat fallback (173 lines)
│   ├── disambiguator.py           Close-call intent handler (151 lines)
│   ├── state_manager.py           Slot-fill state machine (135 lines)
│   ├── feedback.py                SQLite reward logging + EMA (466 lines)
│   ├── utterance_parser.py        Multi-command splitter (263 lines)
│   ├── stt.py                     Speech-to-text (77 lines)
│   ├── tts.py                     Text-to-speech (65 lines)
│   ├── voice_engine.py            Continuous listening + wake/sleep (232 lines)
│   ├── executor.py                Skill dispatch + execution (267 lines)
│   ├── review_cli.py              Interactive pattern review tool (126 lines)
│   └── __init__.py
│
├── ui/
│   ├── jarvis_v31/                Current production UI (9 files)
│   │   ├── main_window.py        Qt5 main window + threading (26 KB)
│   │   ├── glass_chat_panel.py   Right chat rail (49 KB)
│   │   ├── reactor.py            Animated core + particles (25 KB)
│   │   ├── floating_dock.py      Left sidebar docking (24 KB)
│   │   ├── tab_panels.py         Tab management (20 KB)
│   │   ├── wiring_system.py      Interconnected cards (25 KB)
│   │   ├── logs_bar.py           Collapsible logs panel (11 KB)
│   │   ├── title_bar.py          Custom frameless titlebar (10 KB)
│   │   └── tokens.py             Design tokens + colors (3 KB)
│   │
│   ├── aeris_v4/                  Previous AERIS iteration (preserved)
│   ├── ui_laptop/                 Desktop variant (8 files + widgets/)
│   └── ui_legacy/                 Archived earlier versions
│
├── data/
│   ├── intents.json               21 intent definitions with Hinglish patterns
│   ├── entities.json              25+ app name gazetteer + aliases
│   ├── user_memory.json           Persistent facts (name, location, etc.)
│   ├── hinglish_dict.json         Romanized Hindi vocabulary
│   ├── models/
│   │   ├── intent_index.pkl       Cached k-NN embeddings (auto-rebuilt)
│   │   └── intent_metadata.json   Hash + encoder metadata
│   ├── audio_cache/               TTS output (speech.mp3)
│   ├── logs/                      System logs
│   └── notes/                     User-created notes (JSON)
│
├── tests/                         13 pytest test files
│   ├── conftest.py
│   ├── test_brain.py              IntentClassifier / IntentEngine
│   ├── test_conversation.py       ConversationHistory
│   ├── test_disambiguator.py      Disambiguator
│   ├── test_entity_extractor.py   EntityExtractor (all 4 layers)
│   ├── test_feedback.py           FeedbackStore (SQLite + EMA)
│   ├── test_intent_classifier.py  k-NN + cache rebuild
│   ├── test_memory.py             UserMemory store + recall
│   ├── test_normalizer.py         HinglishNormalizer
│   ├── test_pipeline.py           End-to-end pipeline
│   ├── test_sentiment.py          SentimentAnalyzer
│   ├── test_stt.py                STT (mocked)
│   └── test_tts.py                TTS (mocked)
│
├── utils/
│   ├── gesture.py                 OpenCV + MediaPipe hand tracking
│   ├── monitor.py                 System monitoring utilities
│   └── __init__.py
│
├── BRAIN_BUILD_PLAN.md            9-checkpoint architecture document
├── BRAIN_CHECKPOINTS.md           Implementation status tracker
└── BRAIN_REVIEW.md                Code review notes
```

---

## 4. All Commands & Voice Triggers

### Terminal Mode CLI (`main.py`)

| Flag | Effect |
|------|--------|
| `--text` | Text-only REPL, no microphone |
| `--verbose` | INFO-level debug logging |

| REPL Command | Aliases | Effect |
|---|---|---|
| `quit` | `exit`, `q`, `:q` | Exit program |
| `:stats` | `stats` | Show feedback statistics |
| `:facts` | `facts` | Print all saved memory facts |
| `:help` | `help`, `?` | Show command help |

### Pattern Review CLI (`core/review_cli.py`)

```bash
python -m core.review_cli
```

| Key | Effect |
|-----|--------|
| `1` / `2` / `3` | Approve pattern as that top-3 guess |
| `<intent_name>` | Approve with custom intent label |
| `s` | Skip (review later) |
| `r` | Reject (discard pattern) |
| `l` | List all pending |
| `q` | Quit review session |

### Voice Wake / Sleep

| Phrase | Effect |
|--------|--------|
| `jarvis wake up` | Wake from sleep mode |
| `wake up jarvis` | Wake from sleep mode |
| `ok jarvis` | Wake from sleep mode |
| `hey jarvis` | Wake from sleep mode |
| `activate` | Wake from sleep mode |
| `jarvis sleep` | Enter sleep mode |
| `go to sleep` | Enter sleep mode |
| `sleep mode` | Enter sleep mode |
| `sleep now` | Enter sleep mode |
| `stand by` | Enter sleep mode |

### Cancel / Abort Keywords (any active state)

```
cancel    cancel karo    ruko    rok do    rehne do
nahi karna    nevermind    never mind    stop
```

### Correction Keywords (one-turn feedback window)

```
galat    galat hai    yeh galat hai    wrong    that's wrong
undo    wapas
```

### Memory Store Patterns

| Example Utterance | Stored Fact |
|---|---|
| `mera naam Shivang hai` | `name: Shivang` |
| `my name is Shivang` | `name: Shivang` |
| `main Delhi mein rehta hoon` | `location: Delhi` |
| `i live in Mumbai` | `location: Mumbai` |
| `main Google mein kaam karta hoon` | `employer: Google` |
| `mera favorite color blue hai` | `favorite_color: blue` |
| `my favorite music is jazz` | `favorite_music: jazz` |
| `remember ki meeting at 3pm` | note saved |
| `yaad rakho ki buy milk` | note saved |

### Memory Recall Patterns

| Utterance | Returns |
|---|---|
| `mera naam kya hai?` | Saved name |
| `main kahan se hoon?` | Saved location |
| `main kahan rehta hoon?` | Saved location |
| `main kahan kaam karta hoon?` | Saved employer |
| `aap kaun ho?` | AERIS self-intro |

---

## 5. All Automations & Background Processes

### Boot-Time Automations

| Process | Trigger | What It Does |
|---------|---------|--------------|
| **Intent Index Rebuild** | App start (if intents.json hash changed) | Re-embeds all patterns via MiniLM, fits k-NN, saves `intent_index.pkl` |
| **Vosk Model Pre-load** | App start | Loads offline STT model on daemon thread so first listen is fast |
| **FeedbackStore Init** | App start | Creates SQLite tables (`utterances`, `intent_thresholds`, `pending_patterns`) if missing |
| **UserMemory Load** | App start | Reads `data/user_memory.json` into memory |
| **ConversationHistory Init** | App start | Creates rolling 8-turn deque buffer |

### Continuous Background Processes

| Process | Module | Frequency | Description |
|---------|--------|-----------|-------------|
| **Voice Capture Loop** | `voice_engine.py` | Always-on daemon thread | Reads mic, emits captured text when ACTIVE, listens for wake words when SLEEPING |
| **Brain Processing** | `main_window.py::BrainWorker` | Per-utterance, QThread | Full NLP pipeline isolated from UI thread |
| **TTS Playback** | `main_window.py::SpeakWorker` | Per-response, QThread | Async Edge-TTS or pyttsx3, non-blocking |
| **Qt Particle Animation** | `reactor.py::ParticleField` | 30fps timer | Drifting particle background (Lissajous motion) |
| **Reactor Ring Animation** | `reactor.py::ReactorRings` | 30fps timer | 4 rings + rotating wireframe 3D sphere |

### Event-Driven Automations

| Event | Automation | Module |
|-------|-----------|--------|
| User says "galat" within one turn | Feedback recorded, EMA threshold updated | `main_engine.py` + `feedback.py` |
| Brain confidence < per-intent threshold | Low-confidence utterance queued to SQLite for review | `feedback.py::queue_low_confidence` |
| User approves pattern in review CLI | Pattern appended to `intents.json` | `review_cli.py` + `feedback.py` |
| `intents.json` file hash changes (next boot) | k-NN index auto-rebuilds | `intent_classifier.py::_boot` |
| User sends text via GUI | `BrainWorker.process()` emits `responded(text, meta)` → `SpeakWorker.speak()` | `main_window.py` |
| Mic capture while SLEEPING | Wake-word check only — no commands processed | `voice_engine.py` |
| `open_app` skill executed | `subprocess` launches app; `taskkill` for `close_app` | `executor.py` |
| `take_screenshot` skill | PIL captures screen → timestamp-named JSON in `data/` | `executor.py` |
| `create_note` skill | JSON file written to `data/notes/` | `executor.py` |
| Per-turn conversation append | Oldest turn evicted if buffer full (max 16 messages = 8 turns) | `conversation.py` |

---

## 6. Built-in Intents & Skills

### 21 Intents Supported

| # | Intent | Example Trigger (Hinglish) | Required Entity |
|---|--------|---------------------------|-----------------|
| 1 | `open_app` | `chrome kholo`, `launch brave` | `app_name` |
| 2 | `close_app` | `chrome band karo`, `close notepad` | `app_name` |
| 3 | `get_weather` | `mausam kya hai`, `what's the weather` | — |
| 4 | `play_music` | `music chala`, `song bajao` | — |
| 5 | `stop_music` | `music band karo`, `stop song` | — |
| 6 | `set_reminder` | `reminder set karo 5 baje ke liye` | `message`, `time` |
| 7 | `get_time` | `time kya hai`, `what time is it` | — |
| 8 | `take_screenshot` | `screenshot lo`, `screen capture karo` | — |
| 9 | `search_web` | `google karo machine learning` | `query` |
| 10 | `system_info` | `system info dikha`, `CPU kitna hai` | — |
| 11 | `volume_up` | `volume badhao`, `louder` | — |
| 12 | `volume_down` | `volume kam karo`, `quieter` | — |
| 13 | `volume_mute` | `mute karo`, `sound band karo` | — |
| 14 | `lock_screen` | `screen lock karo`, `lock kar do` | — |
| 15 | `shutdown_system` | `computer band karo`, `shutdown karo` | — |
| 16 | `calculate` | `5 + 3 kya hai`, `calculate 20 percent of 500` | `expression` |
| 17 | `create_note` | `note likho meeting at 3pm` | `content` |
| 18 | `greet` | `hello`, `namaste`, `hi jarvis` | — |
| 19 | `schedule_meeting` | `meeting schedule karo Raj ke saath` | `person` |
| 20 | `play_youtube` | `youtube pe songs chala`, `play lofi on youtube` | `query` |
| 21 | `open_website` | `open github.com`, `ye website kholo` | `url` |

### App Gazetteer (25+ Recognized Apps)

| App | Recognized Aliases |
|-----|-------------------|
| Chrome | `chrome`, `google chrome`, `browser`, `web browser`, `google` |
| Edge | `edge`, `microsoft edge`, `ms edge` |
| Brave | `brave`, `brave browser` |
| VS Code | `vs code`, `vscode`, `code editor`, `visual studio code` |
| Notepad | `notepad`, `text editor` |
| Calculator | `calculator`, `calc` |
| VLC | `vlc`, `vlc player`, `media player` |
| Spotify | `spotify`, `music app` |
| Discord | `discord` |
| File Explorer | `file explorer`, `file manager`, `explorer`, `files` |
| Settings | `settings`, `control panel`, `system settings`, `windows settings` |
| Command Prompt | `cmd`, `command prompt`, `terminal`, `command line` |
| Task Manager | `task manager`, `process manager`, `processes` |
| Paint | `paint`, `ms paint` |
| Word | `word`, `microsoft word`, `document editor` |
| Excel | `excel`, `microsoft excel`, `spreadsheet` |
| PowerPoint | `powerpoint`, `microsoft powerpoint`, `presentation` |
| Zoom | `zoom`, `zoom meeting` |
| Teams | `teams`, `microsoft teams` |
| Telegram | `telegram` |
| OBS | `obs`, `obs studio`, `screen recorder` |
| Python | `python`, `python idle`, `python shell` |
| WhatsApp | `whatsapp`, `whatsapp web` |
| Steam | `steam` |
| Task Manager | `task manager` |

---

## 7. NLP Pipeline

### Step-by-Step Processing

```
Raw text
  │
  ▼
HinglishNormalizer.clean()
  │  Lowercase, strip non-essential punctuation, collapse whitespace
  │  Preserve: / : . - + % (URLs + math)
  ▼
UserMemory.detect_and_recall()
  │  Interrogative check → return fact immediately if match
  ▼
UserMemory.detect_and_store()
  │  Pattern check → save fact + return acknowledgement
  ▼
utterance_parser.split_into_segments()
  │  Split on: , | phir | then | baad mein | aur | and
  │  Verb reattachment: "brave aur chrome open karo"
  │                  → ["brave open karo", "chrome open karo"]
  ▼
Per segment:
  ├── SentimentAnalyzer.classify()       VADER + Hinglish lexicon (40+ words)
  ├── find_best_interpretation()         Subspan scanner — try up to 6 variants
  │     Filler stripping: bhai, please, jarvis, yaar, ek kam karo
  │     Min viable confidence: 0.45
  ├── Gazetteer override check           app_name verb → confident direct route
  ├── feedback.get_threshold(intent)     Per-intent EMA-learned threshold
  ├── Disambiguator.is_close_call()      Top1−Top2 < 0.05 AND Top1 < 0.85?
  │     YES → ask clarification, wait one turn
  ├── EntityExtractor.extract()
  │     Layer 1: Regex (time, URL, number, expression, person)
  │     Layer 2: Gazetteer (25+ app names)
  │     Layer 3: spaCy NER (optional: PERSON, DATE, LOC)
  │     Layer 4: Residual span (strip trigger words, return leftover)
  ├── StateManager.process_prediction()
  │     All required entities present? → SUCCESS_EXECUTE
  │     Missing entity? → Ask slot-fill question (wait one turn)
  └── ActionExecutor.execute(intent, slots) → response string
        ↓
    Fallback if no match + low confidence:
        LLMChat.reply() → Ollama phi3:mini (30s timeout)
        If Ollama down → queue to pending_patterns
```

### Intent Classification Detail

| Component | Value |
|-----------|-------|
| Encoder | `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) |
| Algorithm | Cosine k-NN, k=5 |
| Output | Top-3 intents with vote shares |
| Caching | MD5(intents.json) → auto-rebuild on change |
| Inference latency | ~10ms |
| Rebuild latency | ~5-10s for ~300 patterns |
| High-confidence floor | 0.85 (never disambiguate above) |
| Close-call delta | 0.05 (confidence gap to trigger disambig) |

### Per-Intent Threshold Learning

| Parameter | Value |
|-----------|-------|
| Algorithm | Exponential Moving Average |
| Alpha (smoothing) | 0.1 |
| Reward mapping | accepted=+1, corrected=−1, cancelled=−1, ignored=0 |
| Min threshold | 0.40 |
| Max threshold | 0.90 |
| Update trigger | 5+ samples AND reward gate |

---

## 8. GUI Components

### JARVIS v3.1 Layout

```
┌──────────────── TitleBar ─────────────────────────────────────┐
│  [AERIS]  ─────────────────────────────────  [─][□][✕]        │
├──────────────────────────────────────────────────────────────┤
│          │                                │                   │
│ Floating │    ParticleField (background)  │  GlassChatPanel  │
│  Dock    │                                │   ┌───────────┐  │
│          │    ┌─────────────────────┐     │   │  Header   │  │
│  [Chat]  │    │                     │     │   │  Status   │  │
│  [Auto]  │    │    ReactorRings     │     │   ├───────────┤  │
│  [Sets]  │    │   460×460 animated  │     │   │Automation │  │
│          │    │   rings + sphere    │     │   │  Chips    │  │
│          │    │                     │     │   ├───────────┤  │
│          │    └─────────────────────┘     │   │  Message  │  │
│          │                                │   │  Scroll   │  │
│          │    StateText  [IDLE]            │   ├───────────┤  │
│          │    StateSwitcher buttons        │   │   Input   │  │
│          │                                │   │  + Send   │  │
│          │                                │   └───────────┘  │
├──────────────────────────────────────────────────────────────┤
│                  LogsBar (collapsible)                        │
│  SYS ▪ NLU ▪ MEM ──────────────────────── [▼ collapse]       │
└──────────────────────────────────────────────────────────────┘
```

### Visual State Machine

| State | Reactor Color | Ring Behavior | Description |
|-------|--------------|---------------|-------------|
| IDLE | Cyan | Slow rotation | Waiting for input |
| THINKING | Magenta | Faster rotation + spinner | Processing command |
| PROCESSING | Magenta | Full spin + wavebars | Executing action |
| SLEEPING | Purple | Slow pulse | Wake-word only mode |

### Suggestion Chips (GlassChatPanel)
```
[Open Chrome]  [Check Weather]  [Play Music]
[System Stats]  [Schedule Meeting]
```

### Logs Bar Streams
| Stream | Color | Content |
|--------|-------|---------|
| SYS | System color | App events, errors, startup |
| NLU | NLU color | Intent predictions, confidence, entities |
| MEM | Memory color | Facts stored/recalled |

---

## 9. Data & Configuration

### `data/intents.json`
Each intent contains:
```json
{
  "open_app": {
    "patterns": ["open chrome", "chrome kholo", "launch browser"],
    "required_entities": ["app_name"],
    "prompts": {
      "app_name": "Kaunsa app kholna hai? Batao."
    }
  }
}
```

### `data/user_memory.json`
```json
{
  "facts": {
    "name": {"value": "Shivang", "set_at": "2024-04-29T10:00:00", "source": "user_said"},
    "location": {"value": "Delhi", "set_at": "...", "source": "user_said"}
  },
  "notes": [{"text": "buy milk on tuesdays", "set_at": "..."}],
  "preferences": {"language": "hinglish"}
}
```

### `data/models/intent_metadata.json`
```json
{
  "intents_hash": "abc123...",
  "encoder_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "num_patterns": 250,
  "num_classes": 21,
  "built_at": "2024-04-29T17:30:00"
}
```

### SQLite Schema (`feedback_log.sqlite`)
```sql
-- utterances: every processed input
id | timestamp | raw_text | normalized_text | predicted_intent
   | confidence | top3_json | sentiment_label | sentiment_score
   | action_taken | user_feedback | correct_intent | reward

-- intent_thresholds: per-intent EMA thresholds
intent (PK) | accept_threshold | sample_count | avg_reward | updated_at

-- pending_patterns: low-confidence queue for review
id | utterance_id (FK) | raw_text | top3_json | queued_at | status
```

---

## 10. Testing

```bash
pytest tests/               # Run full suite
pytest tests/ -v            # Verbose output
pytest tests/test_pipeline.py   # End-to-end only
```

| Test File | Module | Coverage Highlights |
|-----------|--------|---------------------|
| `test_normalizer.py` | HinglishNormalizer | Punctuation strip, whitespace, URL/math preservation |
| `test_sentiment.py` | SentimentAnalyzer | VADER + Hinglish lexicon, neutral band, fallback |
| `test_intent_classifier.py` | IntentClassifier | Encoder, k-NN, cache rebuild on hash mismatch |
| `test_entity_extractor.py` | EntityExtractor | All 4 layers: regex, gazetteer, NER, residual |
| `test_memory.py` | UserMemory | Pattern detection, fact storage, recall, JSON I/O |
| `test_disambiguator.py` | Disambiguator | Close-call detection, prompt gen, answer parsing |
| `test_conversation.py` | ConversationHistory | Turn append, FIFO overflow, OpenAI message format |
| `test_feedback.py` | FeedbackStore | Log utterance, threshold EMA, pending queue, approval |
| `test_pipeline.py` | JarvisMainEngine | End-to-end: input → intent → entities → execution |
| `test_stt.py` | STT | Mocked Google SR + Vosk fallback |
| `test_tts.py` | TTS | Mocked Edge-TTS + pyttsx3 fallback |
| `test_brain.py` | JarvisBrain | Intent prediction, fuzzy fallback |
| `conftest.py` | — | Shared fixtures and test setup |

---

## 11. Dependencies & Setup

### Install

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm      # optional: advanced NER
```

### Ollama (optional chit-chat fallback)

```bash
# Install Ollama from https://ollama.com
ollama pull phi3:mini        # ~2.4 GB — recommended
# OR
ollama pull llama3.2:3b     # ~2.0 GB — alternative
```

### requirements.txt overview

```
# Audio I/O
SpeechRecognition, vosk, pyaudio, edge-tts, pyttsx3, pygame

# NLP / Brain
sentence-transformers, scikit-learn, spacy, rapidfuzz, nltk, vaderSentiment

# LLM chit-chat
requests

# UI + System
PyQt5, psutil, keyboard, pyautogui

# Gesture
opencv-python, mediapipe

# Misc
pyyaml

# Dev / test
pytest
```

---

## 12. Project Stats

| Metric | Value |
|--------|-------|
| Core modules | 20 Python files, ~3,700 lines |
| UI modules | 53 Python files (jarvis_v31 + legacy) |
| Test files | 13 (full pytest suite) |
| Built-in intents | 21 |
| App aliases | 25+ |
| Memory patterns (regex) | 8 |
| Entity extraction layers | 4 |
| SQLite tables | 3 |
| Main classes | 23 |
| Encoder dimension | 384 (multilingual MiniLM-L12-v2) |
| k-NN neighbors | k=5, top-3 returned |
| EMA alpha | 0.1 |
| Close-call delta | 0.05 |
| High-confidence floor | 0.85 |
| Ollama timeout | 30 seconds |
| TTS voice | `en-IN-NeerjaNeural` (Hinglish) |
| STT pause threshold | 0.8 seconds |
| Max subspan variants | 6 |
| Conversation buffer | 8 turns (16 messages) |

---

## 13. Roadmap — Next 12 Months

### Phase 1 — May–June 2026: Performance & Audio Hardening

**Goal:** Eliminate dependency on cloud APIs; make AERIS fully offline-capable with no quality degradation.

| Task | Detail | Priority |
|------|--------|----------|
| Replace Google SR with `faster-whisper` | Local Whisper model (`medium.en` or multilingual), ~3× faster than Vosk, better Hinglish | Critical |
| Replace Edge-TTS with Piper TTS | Local neural TTS, offline, voice cloning support, low latency | Critical |
| Add optional Coqui TTS backend | Better Hindi synthesis; configurable voices | Medium |
| Voice calibration UI | Let user set mic sensitivity, TTS speed, voice from settings tab | High |
| Hotword detection via `openwakeword` | Replace keyword string-matching with neural wake word model | High |
| Audio device selection | Dropdown for input/output device in settings panel | Medium |
| Benchmark STT/TTS latency | Add timing to logs panel; surface P95 in GUI | Low |

**Deliverable:** Fully offline AERIS with sub-1s response latency from speech input to audio output.

---

### Phase 2 — July–August 2026: Skill Expansion & Real Integrations

**Goal:** Replace stub skills with real implementations; expand skill coverage to 40+ intents.

| Task | Detail | Priority |
|------|--------|----------|
| Weather API | OpenWeatherMap or WeatherAPI integration with location from memory | Critical |
| Reminder engine | Windows Task Scheduler bridge (`schtasks.exe`) for actual timed reminders | Critical |
| Calendar integration | Google Calendar API / Outlook COM automation | High |
| Contacts integration | Windows Contacts / Google Contacts for `schedule_meeting` | High |
| Email send/read | Outlook COM or Gmail API — "mail bhejo Raj ko…" | High |
| File search | Windows Search index (`everything` CLI or `os.walk`) — "find my resume" | Medium |
| Clipboard integration | Copy/paste text to/from clipboard | Medium |
| Screenshot annotation | After capture, allow "add label" slot | Low |
| New intents (10+) | set_alarm, send_email, read_emails, find_file, open_folder, minimize_window, maximize_window, close_tab, new_tab, translate_text | High |
| Skill registry pattern | Decouple executor.py; each skill is a separate module with metadata | High |

**Deliverable:** AERIS can handle a full morning routine: weather → email check → calendar → reminder — without stubs.

---

### Phase 3 — September–October 2026: Intelligence Upgrade

**Goal:** Upgrade NLP core to handle larger intent catalogs, multilingual sentiment, and multi-turn conversations.

| Task | Detail | Priority |
|------|--------|----------|
| FAISS HNSW index | Replace scikit-learn k-NN with FAISS for 10K+ pattern scale | High |
| Expand intent patterns | Grow from 250 → 1,000+ patterns using data augmentation (paraphrase + backtranslation) | High |
| Multilingual sentiment | Swap VADER → `twitter-xlm-roberta-base-sentiment` for true Hindi support | High |
| Contextual entity linking | Use conversation history to resolve pronouns ("usse band karo" after naming an app) | High |
| Multi-turn skills | Set_reminder → refine time → confirm flow (3-turn state machine) | Medium |
| spaCy fine-tuning | Fine-tune `en_core_web_sm` on AERIS-specific entities (app names, cities, contacts) | Medium |
| LLM upgrade | Support `llama3.1:8b` or `mistral:7b` for higher-quality chit-chat | Medium |
| Intent confidence analytics | Charts in GUI: per-intent avg confidence, correction rate, threshold drift over time | Low |

**Deliverable:** AERIS handles ambiguous, multi-turn Hinglish commands reliably at scale.

---

### Phase 4 — November–December 2026: GUI Polish & User Experience

**Goal:** Elevate the GUI to a consumer-quality desktop product; add onboarding, settings persistence, and profile management.

| Task | Detail | Priority |
|------|--------|----------|
| Onboarding flow | First-run wizard: name, language preference, mic test, TTS voice selection | Critical |
| Settings persistence | All user settings saved to `data/config.json`; applied on restart | Critical |
| Full settings panel | TTS speed, STT language, theme, wake word, notification sound, model select | High |
| Notification center | Desktop toast notifications for reminders, alarms, emails | High |
| Skill marketplace UI | List installed vs available skills; toggle on/off | Medium |
| Profile UI | Show user facts, notes, conversation stats in floating dock tab | Medium |
| System tray mode | Minimize to tray; mic icon in taskbar showing ACTIVE/SLEEPING/STOPPED | Medium |
| Dark/light theme toggle | Respect system theme preference; switchable from settings | Low |
| Multi-monitor support | Window snapping, correct screen detection for screenshot | Low |
| Keyboard shortcuts | `Ctrl+Space` → show/hide window; `Ctrl+M` → toggle mic | Medium |
| Animated onboarding | Splash screen with boot sequence matching reactor animation | Low |

**Deliverable:** AERIS ships as a polished desktop app a new user can set up in 5 minutes.

---

### Phase 5 — January–February 2027: Learning & Personalization

**Goal:** Close the feedback loop — AERIS improves automatically from user interactions without manual review sessions.

| Task | Detail | Priority |
|------|--------|----------|
| Auto-approval pipeline | High-confidence pending patterns (top-3 all agree) auto-approved nightly | High |
| Active learning queue | Surface 3–5 uncertain examples per session as inline "Did I get that right?" chips | High |
| User phrase learning | Save user's exact wording per intent; grow personal pattern library | High |
| Contact learning | When user says a new name, ask and save — "Aap kis Raj ki baat kar rahe ho?" | Medium |
| App launch frequency model | Rank app suggestions by usage frequency; show top 3 in automation chips | Medium |
| Conversation summarization | Nightly: summarize key facts learned in session → append to memory | Medium |
| Preference inference | Infer preferences from behavior ("you always open VS Code after Chrome") | Low |
| Personalized greetings | Time-aware, mood-aware greetings using sentiment history | Low |

**Deliverable:** AERIS gets measurably better over 30 days of regular use without any manual configuration.

---

### Phase 6 — March–April 2027: Platform Expansion

**Goal:** Package AERIS for distribution; add Android companion app and browser extension.

| Task | Detail | Priority |
|------|--------|----------|
| Installer packaging | PyInstaller or Nuitka → single-exe installer for Windows | High |
| Auto-update system | Check GitHub releases; notify user; one-click update | High |
| REST API server | Local HTTP API (`localhost:5000`) — exposes `POST /process` for external integrations | High |
| Browser extension | Chrome/Edge extension that forwards selected text to AERIS | Medium |
| Android companion app | Flutter app with mic button → sends text to local AERIS REST API over LAN | Medium |
| Home Assistant integration | AERIS as HA voice pipeline (via websocket) | Low |
| VS Code extension | `"Ask AERIS"` command palette entry; pastes AERIS response into editor | Low |
| Cross-device sync | Sync `user_memory.json` and `intents.json` via Google Drive or Dropbox | Low |

**Deliverable:** AERIS is a distributable product with a multi-surface ecosystem.

---

### Summary Timeline

```
May 2026     Jun 2026     Jul 2026     Aug 2026     Sep 2026     Oct 2026
│            │            │            │            │            │
│◄─── Phase 1: Audio ────►│◄────── Phase 2: Skills ───────────►│
│  Offline STT/TTS        │  Weather, Reminders, Calendar      │
│  Hotword model          │  Email, File search                 │
│                         │  40+ intents                        │
│
Nov 2026     Dec 2026     Jan 2027     Feb 2027     Mar 2027     Apr 2027
│            │            │            │            │            │
│◄─ Phase 3: NLP ────────►│◄─── Phase 4: GUI ──────►│◄─ Phase 5 ►│◄─ Phase 6 ►│
│  FAISS, 1K patterns     │  Onboarding, settings   │ Learning   │ Packaging  │
│  Multilingual sentiment │  Tray, themes, shortcuts│ Adaptation │ REST API   │
│  Multi-turn skills      │                         │            │ Android    │
```

---

### Quick Reference: Current Status vs. Roadmap

| Feature | Status |
|---------|--------|
| Hinglish intent classification (21 intents) | **Done** |
| 4-layer entity extraction | **Done** |
| VADER sentiment (Hinglish) | **Done** |
| Long-term memory (JSON) | **Done** |
| Short-term conversation context | **Done** |
| Ollama chit-chat fallback | **Done** |
| SQLite feedback + EMA threshold learning | **Done** |
| Disambiguator (close-call handling) | **Done** |
| Slot-filling state machine | **Done** |
| 19 executable skills | **Done** |
| 13-file pytest suite | **Done** |
| PyQt5 GUI (JARVIS v3.1) | **Done** |
| Wake/sleep voice engine | **Done** |
| Offline STT (faster-whisper) | Phase 1 |
| Offline TTS (Piper) | Phase 1 |
| Real weather API | Phase 2 |
| Real reminder engine | Phase 2 |
| Calendar / email integration | Phase 2 |
| FAISS index for 10K+ patterns | Phase 3 |
| Multilingual sentiment transformer | Phase 3 |
| Full settings panel + persistence | Phase 4 |
| System tray mode | Phase 4 |
| Auto-approval + active learning | Phase 5 |
| Windows installer packaging | Phase 6 |
| REST API + browser extension | Phase 6 |
