# JARVIS v3.1 (A.E.R.I.S) — Complete Technical Documentation

> **Purpose of this document:** This is a single-source-of-truth file that explains *every detail* of the JARVIS v3.1 project — its architecture, file structure, component internals, performance pathology, pros/cons, and a complete improvement plan. Any AI or developer who reads this should be able to fully understand the system and know exactly what to fix or rebuild.

---

## Table of Contents

1. [Project Identity](#1-project-identity)
2. [Folder and File Structure](#2-folder-and-file-structure)
3. [What the Application Actually Does](#3-what-the-application-actually-does)
4. [Full Architecture — Every Layer Explained](#4-full-architecture--every-layer-explained)
   - 4.1 Entry Point
   - 4.2 Main Window (JarvisV31Window)
   - 4.3 Threading Model
   - 4.4 UI Component Tree
   - 4.5 Brain / NLU Pipeline
   - 4.6 Voice (STT)
   - 4.7 Text-to-Speech (TTS)
   - 4.8 Skills / Executor
5. [Performance Crisis — Root Cause Analysis](#5-performance-crisis--root-cause-analysis)
   - 5.1 The "Not Responding" Problem Explained
   - 5.2 QTimer Explosion
   - 5.3 Pure-Python Rendering Hell
   - 5.4 Object Allocation Pressure
   - 5.5 GIL Contention
   - 5.6 Why GTA Runs Fine But Jarvis Doesn't
6. [Pros of Current Implementation](#6-pros-of-current-implementation)
7. [Cons and Problems of Current Implementation](#7-cons-and-problems-of-current-implementation)
8. [Improvement Plan — Complete Overhaul Strategy](#8-improvement-plan--complete-overhaul-strategy)
   - 8.1 Immediate Fixes (Keep PyQt5, Fix Performance)
   - 8.2 Medium-Term Improvements
   - 8.3 Full Architectural Overhaul (Recommended)
9. [Component-by-Component Reference](#9-component-by-component-reference)
10. [Data Files Reference](#10-data-files-reference)
11. [Dependency List and Their Roles](#11-dependency-list-and-their-roles)

---

## 1. Project Identity

| Property | Value |
|---|---|
| Project Name | JARVIS v3.1 / A.E.R.I.S |
| Owner | Shivang |
| Language | Python 3.13 |
| UI Framework | PyQt5 |
| Working Directory | `New version- 3.0/` inside `D:\New folder (2)\1. LATEST 23 April\` |
| Entry Point | `run_gui.py` |
| Main Window File | `ui/jarvis_v31/main_window.py` |
| Brain Entry | `core/main_engine.py → JarvisMainEngine` |
| Intent Classification | `core/intent_classifier.py → IntentClassifier` (sentence-transformers + k-NN) |
| STT Engine | `core/voice_engine.py → ContinuousVoiceEngine` (Google Speech Recognition + Vosk offline fallback) |
| TTS Engine | `core/tts.py → TTS` (Edge-TTS online + pyttsx3 offline fallback) |
| Target Platform | Windows 11 desktop |
| Design Theme | Iron Man / JARVIS — dark background `#0A0F1C`, cyan/magenta/purple/green glows |

---

## 2. Folder and File Structure

```
New version- 3.0/
│
├── run_gui.py                         # ENTRY POINT — pre-imports torch, launches GUI
│
├── core/                              # All AI/brain logic
│   ├── main_engine.py                 # JarvisMainEngine — top-level orchestrator
│   ├── brain.py                       # JarvisBrain — thin wrapper around IntentClassifier
│   ├── intent_classifier.py           # SentenceTransformer + k-NN intent classification
│   ├── intent_engine.py               # Older rapidfuzz-based intent engine (legacy, unused in main path)
│   ├── entity_extractor.py            # Named entity extraction (app names, times, etc.)
│   ├── normalizer.py                  # HinglishNormalizer — text cleaning/normalization
│   ├── sentiment.py                   # SentimentAnalyzer — positive/negative/neutral
│   ├── conversation.py                # ConversationHistory — last 8 turns memory
│   ├── feedback.py                    # FeedbackStore — SQLite DB for per-intent learning
│   ├── disambiguator.py               # Disambiguator — asks user when top-3 are close
│   ├── state_manager.py               # StateManager — slot-filling state machine
│   ├── utterance_parser.py            # Split multi-commands; find best interpretation subspan
│   ├── memory.py                      # UserMemory — JSON store for user facts
│   ├── llm_chat.py                    # LLMChat — Ollama local LLM fallback (chit-chat)
│   ├── executor.py                    # ActionExecutor — executes intents (open app, search, etc.)
│   ├── skill_registry.py              # Plugin skill discovery + @skill decorator
│   ├── tool_router.py                 # ToolRouter — routes LLM tool calls to skills/executor
│   ├── voice_engine.py                # ContinuousVoiceEngine — continuous STT with sleep/wake
│   ├── tts.py                         # TTS — Edge-TTS (online) + pyttsx3 (offline)
│   ├── stt.py                         # STT — one-shot listen (legacy, not used in GUI path)
│   ├── wake_word.py                   # Wake word detection (Vosk-based)
│   ├── scheduler.py                   # ReminderScheduler — APScheduler wrapper
│   ├── time_parser.py                 # Parse time strings ("5 baje", "tomorrow 3pm")
│   ├── knowledge_cache.py             # Knowledge cache for quick fact lookups
│   ├── summarizer.py                  # Text summarizer
│   ├── vision_engine.py               # Vision / screenshot analysis
│   ├── object_detector.py             # YOLO object detection
│   ├── gesture_engine.py              # Gesture control (MediaPipe)
│   ├── browser_launcher.py            # Browser launch helper
│   ├── vault.py                       # Encrypted storage
│   ├── settings.py                    # App settings loader
│   └── review_cli.py                  # CLI for reviewing low-confidence utterances
│
├── ui/
│   ├── jarvis_v31/                    # CURRENT ACTIVE UI (v3.1)
│   │   ├── main_window.py             # JarvisV31Window + BrainWorker + VoiceWorker + SpeakWorker
│   │   ├── tokens.py                  # Design tokens (colors, state specs, font helpers)
│   │   ├── reactor.py                 # ReactorRings + ParticleField + ReactorStateText + StateSwitcher
│   │   ├── wiring_system.py           # WiringSystem + _WireLayer + _NodeBox × 4
│   │   ├── glass_chat_panel.py        # GlassChatPanel — 390px right rail chat UI
│   │   ├── title_bar.py               # TitleBar — frameless window drag + controls
│   │   ├── logs_bar.py                # LogsBar — collapsible bottom log strip
│   │   ├── floating_dock.py           # FloatingDock — left nav rail overlay
│   │   ├── tab_panels.py              # RightPanelStack — tabs over chat panel
│   │   └── __init__.py
│   │
│   ├── aeris_v4/                      # PREVIOUS UI (AERIS v4) — kept as reference
│   │   ├── main_window.py
│   │   ├── arc_reactor.py
│   │   ├── chat_panel.py
│   │   ├── sidebar.py
│   │   ├── title_bar.py
│   │   ├── logs_panel.py
│   │   └── theme.py
│   │
│   ├── ui_laptop/                     # Even older laptop UI — kept as reference
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── center_content.py
│   │   ├── profile_ui.py
│   │   ├── splash_screen.py
│   │   ├── title_bar.py
│   │   ├── voice_input.py
│   │   └── widgets/
│   │       ├── automation_page.py
│   │       ├── call_popup.py
│   │       ├── notification_center.py
│   │       ├── settings_page.py
│   │       ├── storage_modal.py
│   │       └── toggle_switch.py
│   │
│   ├── ui_legacy/                     # Legacy v1 UI — kept as reference
│   │   ├── main_window.py
│   │   ├── chat_panel.py
│   │   ├── event_bridge.py
│   │   ├── system_tray.py
│   │   ├── settings_manager.py
│   │   ├── status_indicator.py
│   │   ├── images_tab.py
│   │   └── dashboard/
│   │       ├── main_dashboard.py
│   │       ├── tabs/ (home, automation, gallery, settings)
│   │       └── widgets/ (sidebar)
│   │
│   ├── dashboard.py                   # Legacy dashboard (very old)
│   └── animations.py                  # Old animation helpers
│
├── skills/                            # Plugin skills (@skill-decorated functions)
│   ├── clipboard.py                   # Clipboard read/write
│   ├── file_ops.py                    # File operations (open, delete, move)
│   ├── news.py                        # News fetcher
│   ├── weather.py                     # Weather via API
│   ├── translate.py                   # Text translation
│   ├── whatsapp.py                    # WhatsApp automation (pywhatkit)
│   ├── vision.py                      # Vision-based skills
│   ├── spotify_control.py             # Spotify control
│   └── __init__.py
│
├── utils/
│   ├── monitor.py                     # System monitor utility
│   └── gesture.py                     # Gesture utilities
│
├── data/
│   ├── intents.json                   # Intent definitions: name → patterns + required_entities
│   ├── entities.json                  # Entity gazetteer (app names, city names, etc.)
│   ├── user_memory.json               # Persistent user facts ("mera naam Shivang hai")
│   ├── settings.json                  # App configuration (theme, assistant name, etc.)
│   ├── hinglish_dict.json             # Hinglish → English normalization map
│   ├── clipboard_history.json         # Clipboard history log
│   └── models/
│       ├── intent_index.pkl           # Cached k-NN NearestNeighbors + embeddings
│       ├── intent_metadata.json       # Cache metadata (hash, num_patterns, built_at)
│       └── vosk-model/               # Offline Vosk STT model directory (if present)
│
├── tests/
│   ├── conftest.py
│   ├── test_brain.py
│   ├── test_tts.py
│   ├── test_stt.py
│   ├── test_intent_classifier.py
│   ├── test_intent.py (if present)
│   ├── test_entity_extractor.py
│   ├── test_sentiment.py
│   ├── test_memory.py
│   ├── test_conversation.py
│   ├── test_disambiguator.py
│   ├── test_feedback.py
│   ├── test_pipeline.py
│   └── test_normalizer.py
│
├── _aeris_smoke.py                    # Quick smoke-test launcher for AERIS v4 UI
├── _jv31_smoke.py                     # Quick smoke-test launcher for JarvisV31 UI
├── test_brain_accuracy.py             # Standalone brain accuracy test
└── .git/                              # Git repository
```

---

## 3. What the Application Actually Does

JARVIS is a personal AI desktop assistant for Windows 11 that mimics the Iron Man JARVIS system. It:

1. **Accepts voice input** continuously via microphone using Google Speech Recognition (online) or Vosk (offline). The user can say "jarvis sleep" to pause voice detection and "wake up" to resume.

2. **Accepts text input** via a chat panel (390px right column).

3. **Understands commands in Hinglish** (Hindi-English mixed language). Examples: "chrome kholo", "weather batao", "volume badhao", "screenshot lo zara".

4. **Classifies intent** using a sentence-transformer model (`paraphrase-multilingual-MiniLM-L12-v2`) + k-NN over ~300+ patterns spread across 21+ intent classes.

5. **Executes actions**: Opens apps, closes apps, searches the web, plays YouTube, takes screenshots, checks battery, controls volume, sets reminders, saves notes, controls Spotify, etc.

6. **Falls back to LLM** (Ollama local model) for general chit-chat when intent confidence is low.

7. **Speaks the response** via Edge-TTS (Microsoft neural voices, online) or pyttsx3 (offline).

8. **Displays a sci-fi UI**: animated reactor rings, wiring system with PCB traces connecting 4 system stat cards (CPU/RAM/BATTERY/NETWORK), particle field background, glass chat panel, collapsible logs bar, floating nav dock.

9. **Learns from feedback**: Every executed command is logged in SQLite. If the user says "galat" (wrong), it records a correction. Per-intent confidence thresholds adjust over time via a bandit approach.

10. **Remembers user facts**: "mera naam Shivang hai" → stored. "mera naam kya hai?" → recalled.

---

## 4. Full Architecture — Every Layer Explained

### 4.1 Entry Point — `run_gui.py`

```python
# 1. Sets KMP_DUPLICATE_LIB_OK=TRUE to prevent OpenMP DLL conflict
#    (torch and Qt both ship libiomp5md.dll on Windows)
# 2. Sets sys.setswitchinterval(0.002) — halves Python GIL switch interval
#    from 5ms to 2ms, giving UI thread more frequent windows during boot
# 3. Pre-imports torch BEFORE Qt to fix Windows WinError 1114 DLL load order
# 4. Calls ui.jarvis_v31.main_window.launch()
```

**Key issue here**: Pre-importing `torch` alone takes 2–5 seconds on a cold start. This blocks the process before the window even appears.

---

### 4.2 Main Window — `ui/jarvis_v31/main_window.py → JarvisV31Window`

**Window spec**: Frameless, 1440×900 (minimum 1200×720), dark background `#0A0F1C`.

**Layout tree** (widget hierarchy):

```
QMainWindow
└── centralWidget (QWidget, dark bg)
    └── root (QVBoxLayout)
        ├── TitleBar (fixed height, drag area, min/max/close buttons)
        ├── body (QWidget)
        │   ├── body_lay (QHBoxLayout)
        │   │   ├── _center_col (QWidget, stretch=1)   ← particles + wiring + reactor
        │   │   │   ├── ParticleField (overlay, transparent for mouse)
        │   │   │   ├── WiringSystem (1080×820 overlay, centered)
        │   │   │   ├── ReactorRings (460×460 overlay, centered on wiring)
        │   │   │   ├── ReactorStateText (below reactor)
        │   │   │   └── StateSwitcher (4 buttons below state text)
        │   │   └── RightPanelStack (fixed width ~390px)
        │   │       ├── GlassChatPanel (tab index 1 — default visible)
        │   │       └── (other panels for different dock tabs)
        │   └── FloatingDock (overlay on body, 12px from left, vertically centered)
        └── LogsBar (collapsible bottom strip)
```

---

### 4.3 Threading Model

This is the most critical architectural piece. The app runs **4 threads**:

```
┌─────────────────────────────────────────────────────────────┐
│ MAIN THREAD (Qt event loop + GUI)                           │
│   - All widget painting (paintEvent)                        │
│   - All QTimer callbacks                                     │
│   - User input events (mouse clicks, keyboard)              │
│   - Layout and resize events                                │
│   - Signal/slot delivery for Qt.AutoConnection              │
└─────────────────────────────────────────────────────────────┘
         ↕ queued signals
┌─────────────────────────────────────────────────────────────┐
│ BRAIN THREAD (_brain_thread — QThread.LowestPriority)       │
│   BrainWorker owns JarvisMainEngine                         │
│   - On initialize(): imports sentence_transformers, spaCy,  │
│     sklearn, etc. Loads 420MB MiniLM model from disk.       │
│   - On process(text): runs full NLU pipeline + executor.    │
│     Can take 50ms–500ms depending on model cache state.     │
└─────────────────────────────────────────────────────────────┘
         ↕ queued signals
┌─────────────────────────────────────────────────────────────┐
│ VOICE THREAD (_voice_thread — default priority)             │
│   VoiceWorker owns ContinuousVoiceEngine                    │
│   - Inner daemon capture thread (separate Python thread,    │
│     NOT a QThread) runs the PyAudio mic capture loop.       │
│   - Calls Google Speech Recognition (blocking network call) │
│     or Vosk offline (CPU-bound transcription).              │
└─────────────────────────────────────────────────────────────┘
         ↕ queued signals
┌─────────────────────────────────────────────────────────────┐
│ SPEAK THREAD (_speak_thread — default priority)             │
│   SpeakWorker owns TTS                                      │
│   - On speak(text): creates asyncio event loop, calls       │
│     Edge-TTS, downloads audio, plays via pygame.            │
│     Blocks the speak thread until audio finishes.           │
└─────────────────────────────────────────────────────────────┘
```

**GIL (Global Interpreter Lock) reality**: Python only runs one thread at a time. All 4 threads share the GIL. Even though brain/voice/speak are on separate QThreads, whenever they execute Python code they compete with the GUI thread for the GIL. The GUI thread must hold the GIL to run every `paintEvent`, `QTimer.timeout` handler, and signal receiver.

---

### 4.4 UI Component Tree — Detailed

#### `tokens.py` — Design System
- Color palette: `J.BG = #0A0F1C`, `J.CYAN = #00D4FF`, `J.MAGENTA = #FF2D95`, `J.PURPLE = #A855F7`, `J.GREEN = #10B981`, `J.AMBER = #FBBF24`, `J.RED = #F87171`
- State specs: `JSTATES` dict maps `IDLE/LISTENING/PROCESSING/SPEAKING` → `StateSpec` (label, color, ring speeds, pulse speed, glow opacity)
- Font helpers: `inter(size, weight)` → Inter/Segoe UI, `mono(size, weight)` → JetBrains Mono/Consolas/Courier New

#### `reactor.py` — The 460px Animated Core

**ParticleField** (full center-column overlay, transparent for mouse events):
- 22 floating colored dots
- Each dot: Lissajous drift path computed via `sin()/cos()` every frame
- QTimer: 60ms (≈16 FPS)
- Per frame: 22 particles × 2 ellipse draws = 44 QPainter ellipse calls

**ReactorRings** (fixed 460×460):
- The main animated reactor. State-driven colors + speeds.
- QTimer: **16ms (60 FPS)** — the most expensive timer in the app
- Per frame paints: 
  - Ambient radial gradient (QRadialGradient + drawEllipse)
  - Ring 1: dashed outer ring rotating (QPen dash pattern + drawEllipse + satellite dot)
  - Secondary inner glow ring: 3 glow passes + solid ring
  - Ring 2: middle ring counter-rotating + 3 glow passes + 2 dot ornaments
  - Ring 3: inner ring + 3 glow passes + 2 dot ornaments
  - 12 tick marks (every 30°)
  - Core glow (QRadialGradient)
  - Core disk (QRadialGradient)
  - Wireframe sphere: 6 latitude ellipses + 6 longitude ellipses + 7 blinking nodes + center dot
  - If SPEAKING: 6 animated wave bars

**ReactorStateText** (below reactor):
- Contains `_BlinkDot` (60ms timer), `QLabel`s, `_JTag` (60ms timer)
- `_JTag`: draws rounded pill + blinking dot + text — 60ms timer

**StateSwitcher**: 4 `_PickButton` widgets — each does custom paintEvent (no timer, repaint on state change only — OK)

---

#### `wiring_system.py` — PCB Traces + 4 Stat Cards

**WiringSystem** (fixed 1080×820):
- Contains `_WireLayer` (full overlay) + 4 `_NodeBox` cards

**_WireLayer** (1080×820 transparent overlay):
- QTimer: **16ms (60 FPS)** — second most expensive timer
- Per frame:
  - For each of 4 wires: 2 base strokes (QPen drawPath) + 2 packet segments (up to 6 drawPath calls each with glow + core layers)
  - 6 junction dots (2 ellipses each)
  - 1 dashed origin ring
  - Ripples: 3–4 expanding rings computed via `time.monotonic()`
  - Total: easily 30–50+ QPainter operations per frame

**_NodeBox** (4 instances — CPU, RAM, BATTERY, NETWORK — each 168px wide):
- Each has a QTimer: **60ms** (for blink dot animation)
- Each `paintEvent` (called by 60ms timer AND on hover):
  - Card body with scale transform on hover
  - Accent gradient line
  - Header row with icon (custom QPainterPath per node type)
  - Blink dot (sin() alpha)
  - Value text (18pt mono)
  - Sub label
  - 8-bar sparkline (8 QLinearGradient + drawRoundedRect calls)
  - Detail card slide animation (QVariantAnimation, 300ms)
  - If expanded: detail text + NOMINAL pill

**Live values**: `_live_timer` fires every 2800ms → calls `psutil.cpu_percent()`, `psutil.virtual_memory()`, `psutil.net_io_counters()`, `psutil.sensors_battery()` — all blocking calls on the GUI thread.

---

#### `glass_chat_panel.py` — 390px Right Chat Panel

Key sub-widgets with their own timers:
- `_Pill` (THINKING / LIVE): 60ms timer for blink dot — 2 instances in header
- `_SmallDot`: 60ms timer — one per message bubble (accumulates!)
- `_DotsBubble` (typing indicator): 60ms timer for 3-dot animation
- `_ListeningWave`: 60ms timer for 20-bar animated waveform
- `_SleepPill`: 60ms timer for slow-blink dot
- `_ScrollToBottomBtn`: 60ms timer for pulsing border
- `_ProgressBar` (boot): 16ms timer (smooth fill animation during boot only)
- `_BubbleBody` streaming cursor: 280ms blink timer per active stream

**Streaming text** (`stream_message`): QTimer fires every `speed_ms=18ms` — character by character. Each tick calls `set_text()` → `QLabel.setText()` → forces relayout of the scroll area → causes scroll area repaint.

---

#### `floating_dock.py` — Left Nav Rail

- 56px collapsed, 240px expanded on hover
- QVariantAnimation (320ms, OutCubic) for width animation
- Contains `_BrandMark` (animated), profile avatar, 8+ nav items
- Likely has its own 60ms timers for animated elements (brand mark glow, etc.)

---

#### `logs_bar.py` — Bottom Log Strip

- Collapsible (click to expand/collapse)
- Time-stamped log entries with color-coded type badges (SYS/NLU/MIC/ERR/TTS/ACT)
- Scroll area for log history

---

### 4.5 Brain / NLU Pipeline

This is the entire pipeline that processes text input:

```
User text
    │
    ▼
UserMemory.detect_and_recall(text)      ← Check if asking for stored fact
    │ (if match) → return stored fact
    ▼
UserMemory.detect_and_store(text)       ← Check if saving a new fact
    │ (if match) → store + return ack
    ▼
split_into_segments(text)               ← Split "X aur Y" into ["X", "Y"]
    │
    ▼ (per segment)
SentimentAnalyzer.classify(text)        ← positive/negative/neutral
    │
    ▼
find_best_interpretation(text, brain)   ← Try full text + trimmed variants
    │                                      Pick highest-confidence interpretation
    ▼
EntityExtractor.intent_hint(text)       ← Gazetteer override (known app names + open/close verbs)
    │
    ▼
JarvisBrain.predict(text)               ← SentenceTransformer encode + k-NN query
    │                                      Returns: intent, confidence, top3
    ▼
FeedbackStore.get_threshold(intent)     ← Per-intent learned threshold (default 0.5)
    │
    ├─ confidence >= threshold:
    │   ├─ Disambiguator.is_close_call(pred)?  → Ask user to clarify
    │   └─ EntityExtractor.extract(text, intent)  → Extract slots
    │       └─ StateManager.process_prediction(...)
    │           ├─ All slots filled? → ActionExecutor.execute(intent, slots)
    │           └─ Missing slots?    → Ask user for missing slot
    │
    └─ confidence < threshold:
        ├─ LLM available (Ollama)?
        │   ├─ Tool-calling mode → LLMChat.reply_with_tools() → ToolRouter.execute()
        │   └─ Chat mode → LLMChat.reply()
        └─ No LLM → "Ye samajh nahi paaya, sir. Aap thoda clear bolenge?"
```

**IntentClassifier internals**:
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (420MB, supports Hinglish)
- Index: scikit-learn `NearestNeighbors(metric='cosine')` over all pattern embeddings
- k=5 nearest neighbors, exp-weighted voting (temperature=10)
- Confidence = cosine similarity of top-1 neighbor (range 0–1)
- Cache: pickled index at `data/models/intent_index.pkl`, keyed by MD5 of intents.json content
- First boot (cold): ~10–30s to load encoder + embed all patterns
- Subsequent boots (warm cache): ~2–5s to load encoder + load cached index

---

### 4.6 Voice (STT) — `core/voice_engine.py`

**ContinuousVoiceEngine** runs on `_voice_thread` (a QThread). Inside it, a daemon `threading.Thread` runs the actual capture loop.

States: `STOPPED → ACTIVE → SLEEPING → ACTIVE` (wake word cycle)

Capture loop:
1. Opens mic via `speech_recognition.Microphone`
2. `rec.listen(source, timeout=1.0, phrase_time_limit=8)` — blocks up to 1s waiting for speech
3. Transcribes: `rec.recognize_google(audio, language="en-IN")` (online, blocking network call) or Vosk (offline, CPU-bound)
4. Checks for sleep/wake keywords
5. If active: emits `captured(text)` signal → goes to `_on_voice_captured` in main window → `_on_user_send(text)`

**Sleep/Wake keywords**:
- Sleep: "jarvis sleep", "go to sleep", "sleep mode", "sleep now", "jarvis go to sleep", "stand by", "standby"
- Wake: "jarvis wake up", "wake up jarvis", "wake up", "ok jarvis", "hey jarvis", "jarvis wake", "activate", "jarvis activate"

---

### 4.7 Text-to-Speech (TTS) — `core/tts.py`

**TTS.speak(text)** — runs on `_speak_thread`:

1. Creates a new `asyncio` event loop per call (`asyncio.new_event_loop()`)
2. Calls `edge_tts.Communicate(text, voice, rate, pitch).save(temp_file)` — async, downloads MP3
3. Plays via `pygame.mixer.music.load()` + `play()` + busy-wait loop (`while get_busy(): sleep(0.1)`)
4. If online fails: falls back to `pyttsx3.say(text) + runAndWait()` (blocking, synchronous)

**Voice**: `en-IN-NeerjaNeural` (Indian English, female neural voice)

**Problem**: Creating a new asyncio event loop per call is wasteful but since TTS runs on its own thread, the main issue is that pygame busy-waits with `time.sleep(0.1)` — fine since it's on a separate thread.

---

### 4.8 Skills / Executor — `core/executor.py` + `skills/`

**ActionExecutor.execute(intent, slots)** handles:

| Intent | Action |
|---|---|
| `open_app` | `subprocess.Popen` or `os.startfile` for known app aliases + fixed paths |
| `close_app` | `psutil.process_iter()` to find and `kill()` process |
| `get_weather` | Stub or real weather API call |
| `get_time` | `datetime.now().strftime(...)` |
| `take_screenshot` | `pyautogui.screenshot()` + save to file |
| `search_web` | `webbrowser.open(f"https://google.com/search?q={query}")` |
| `play_youtube` | `webbrowser.open(f"https://youtube.com/results?search_query={query}")` |
| `system_info` | `psutil.cpu_percent()` + `virtual_memory()` + `sensors_battery()` |
| `volume_up/down/mute` | `ctypes` Windows API calls |
| `lock_screen` | `ctypes.windll.user32.LockWorkStation()` |
| `calculate` | `eval(expression)` via safe evaluator |
| `create_note` | Write timestamped text file to `data/notes/` |
| `set_reminder` | `ReminderScheduler.add(message, time)` via APScheduler |

**Plugin skills** (`skills/` folder) use `@skill` decorator from `core/skill_registry.py`. Each skill file registers itself. The `tools_manifest()` function returns all registered skills as tool descriptors for LLM tool calling.

---

## 5. Performance Crisis — Root Cause Analysis

### 5.1 The "Not Responding" Problem Explained

Windows shows the "Application Not Responding" (ANR) dialog when a window's **message queue** is not processed for approximately **5 seconds**. A window's message queue is processed on the **main (GUI) thread**. 

In PyQt5, this means: if the Qt event loop (which runs on the main thread) is blocked for ~5 seconds — whether blocked painting, blocked in Python code, or blocked waiting on the GIL — Windows will show the freeze prompt.

Even **single clicks** triggering this means the GUI thread is spending so much time doing paint work that clicking introduces perceived freezes.

---

### 5.2 QTimer Explosion — Exact Count

Here is every active QTimer in the application and how often it fires:

| Widget | Timer Interval | FPS | Purpose |
|---|---|---|---|
| `ReactorRings` | 16ms | **~60 FPS** | Full reactor paintEvent — most expensive |
| `_WireLayer` | 16ms | **~60 FPS** | Full wiring layer paintEvent — second most expensive |
| `_ProgressBar` | 16ms | **~60 FPS** | Boot progress bar fill animation (only during boot) |
| `ParticleField` | 60ms | ~16 FPS | 22-particle drift animation |
| `_NodeBox` × 4 | 60ms | ~16 FPS | Blink dot on each stat card = 4 timers |
| `_JTag` | 60ms | ~16 FPS | Blinking dot pill |
| `_BlinkDot` | 60ms | ~16 FPS | State text dot |
| `_Pill` (THINKING) | 60ms | ~16 FPS | Chat header busy pill |
| `_Pill` (LIVE) | 60ms | ~16 FPS | Chat header LIVE pill — always active |
| `_SmallDot` per bubble | 60ms | ~16 FPS | One per message bubble — **accumulates** |
| `_DotsBubble` | 60ms | ~16 FPS | Typing dots indicator |
| `_ListeningWave` | 60ms | ~16 FPS | 20-bar voice waveform |
| `_SleepPill` | 60ms | ~16 FPS | Sleep mode indicator |
| `_ScrollToBottomBtn` | 60ms | ~16 FPS | Pulsing scroll button |
| `_BubbleBody` (streaming) | 280ms | ~3.5 FPS | Cursor blink per streaming bubble |
| `stream_timer` | 18ms | ~55 FPS | Character-by-character text streaming |
| `_WiringSystem._live_timer` | 2800ms | ~0.35 FPS | psutil system stats update |

**Total 60ms timers: ~10–15 always active** (not counting per-message-bubble ones)  
**Total 16ms timers: 2–3 always active**

When the application has been running for a while and accumulated, say, 20 message bubbles, there are **20 additional `_SmallDot` timers at 60ms each** all firing and calling their `paintEvent` on the GUI thread.

At startup with 0 messages: minimum ~15 timers are active simultaneously.

---

### 5.3 Pure-Python Rendering Hell

Every `paintEvent` is **pure Python**. There is no GPU acceleration happening here — QPainter does use some system-level drawing primitives, but the Python-to-QPainter overhead (function calls, argument marshalling, GIL acquisition) is enormous when multiplied across many timers.

**What `ReactorRings.paintEvent` does every 16ms**:
```
1 radial gradient object creation + 1 drawEllipse
1 setPen + 1 dashed ring drawEllipse + 1 satellite dot drawEllipse
1 drawRoundedRect (inner glow ring) + 3 glow passes
1 middle ring + 3 glow passes + 2 dot ornament pairs (save/restore × 2)
1 inner ring + 3 glow passes + 2 dot ornament pairs
12 tick mark drawLine calls (one per 30°, each with rotate/save/restore)
1 radial gradient (outer halo) + 1 drawEllipse
1 radial gradient (core disk) + 1 drawEllipse + 1 drawEllipse outline
Wireframe sphere: 6 latitude ellipses + 6 longitude drawEllipse calls + 7 node pairs + 1 core dot
```
That is **70+ QPainter function calls per paintEvent**, called **62 times per second**.

**What `_WireLayer.paintEvent` does every 16ms**:
```
4 wires × (2 drawPath base + 2 packet segments × 3 draw calls each) = ~32 drawPath calls
6 junction dots × 2 drawEllipse = 12 ellipse draws
1 dashed ring draw
3–4 ripple ring draws (state-dependent)
```
That is **~50 QPainter calls per paintEvent**, called **62 times per second**.

Combined just from these two timers: **~120 QPainter calls × 62 = ~7,440 QPainter invocations per second**, all on the GUI thread, all requiring Python to be running, all holding the GIL.

---

### 5.4 Object Allocation Pressure

Every single `paintEvent` creates new Python objects:

**ReactorRings per frame creates**:
- `QRadialGradient` × 3
- `QLinearGradient` × 0 (rings use QPen color, not gradient)
- `QColor` copies via `rgba()` → ~20+ times (every `rgba(col, alpha)` call creates a new `QColor`)
- `QPointF` × ~10
- `QPen` × ~15
- `QRectF` × ~5
- `list` + `zip` in sphere node loop

**In Python, object allocation is relatively expensive** compared to stack-allocated structs in C++. Each `QColor`, `QPointF`, `QPen` etc. must be heap-allocated, reference-counted, and eventually garbage-collected. At 60 FPS, this creates heavy GC pressure.

---

### 5.5 GIL Contention

The GIL switch interval is set to 2ms in `run_gui.py`. This means every 2ms, Python checks whether another thread wants the GIL and potentially switches. With the brain thread starting up and loading sentence_transformers/spaCy, it periodically holds the GIL for 50–200ms windows during module import — causing the GUI thread to stall even if it needs the GIL to process a repaint or click event.

The `QThread.LowestPriority` setting for the brain thread tells the **OS scheduler** to prefer the GUI thread, but it does **not** affect GIL priority. Python's GIL is not OS-scheduler-aware. So even at LowestPriority, the brain thread can hold the GIL while importing, blocking the GUI.

---

### 5.6 Why GTA Runs Fine But Jarvis Doesn't

This is the fundamental misconception that needs to be addressed:

**GTA V (and all AAA games)**:
- Written in C++. No Python. No GIL.
- **All rendering runs on the GPU** via DirectX 12 / Vulkan. The CPU prepares draw calls; the GPU executes them asynchronously. The CPU thread that submits draw calls almost never blocks.
- Memory is pre-allocated. No garbage collection. No heap allocation per frame.
- Object lifetime is managed manually. No reference counting per object.
- The game engine runs its physics, AI, audio, and rendering on separate OS threads that are truly parallel (C++ threads have no GIL equivalent).
- The Windows message loop (handling clicks, window movement) gets serviced in < 1ms because the game's main thread only runs it once per frame at 16ms.

**JARVIS (PyQt5 + Python)**:
- All rendering is in **Python bytecode** on a single Python interpreter thread at a time (GIL).
- QPainter calls cross from Python into C++ Qt, but the Python-side overhead (argument packing, GIL acquisition, return value handling) is non-trivial when called thousands of times per second.
- Every new `QColor`, `QPen`, `QPointF` is a Python heap object — allocated, tracked, and eventually collected.
- The GUI thread holds the GIL almost continuously (painting 60 FPS × multiple widgets simultaneously).
- There is no GPU rendering path. Everything is rendered by the CPU via software rasterization or OS compositor. QPainter uses Qt's native paint engine which can use OpenGL, but **only if explicitly opted into** via `QOpenGLWidget` — none of the JARVIS widgets use `QOpenGLWidget`.
- Python's asyncio (used in TTS) and threading model are not true parallelism for CPU-bound work.

**The single-line summary**: GTA runs on the GPU via C++. Jarvis runs on the CPU via Python. A Python process doing 7,000+ QPainter function calls per second will always fight the GUI event loop.

---

## 6. Pros of Current Implementation

1. **Beautiful, cohesive sci-fi design** — The reactor, wiring system, particle field, and glass panels together create a genuinely impressive Iron Man–aesthetic UI. The design tokens are well-organized and consistent.

2. **Proper threading model** — Brain, voice, and TTS are all on separate QThreads. The worker architecture is correct: signals/slots for cross-thread communication, proper cleanup in `closeEvent`. The boot animation pausing/resuming heavy timers during brain load is a clever mitigation.

3. **State machine for multi-turn conversations** — Slot-filling (asking for missing info), disambiguation (clarifying close-call intents), correction handling ("galat" within one turn) — these are non-trivial NLU features that work correctly.

4. **Multilingual Hinglish support** — The `paraphrase-multilingual-MiniLM-L12-v2` encoder genuinely handles Hindi-English mixed text. This is better than any simple regex/keyword approach.

5. **Continuous STT with sleep/wake** — The voice engine correctly handles sleep/wake modes, prevents concurrent mic access (join() before re-open), and uses offline Vosk as a fallback.

6. **Feedback learning** — Per-intent confidence thresholds adjust based on accept/correct signals. SQLite-backed, persistent across sessions.

7. **Plugin skill system** — `@skill` decorator makes adding new skills clean. Skills auto-register at startup and participate in the k-NN index.

8. **LLM fallback** — When intent confidence is low, falls back to Ollama for genuine chit-chat. Supports tool-calling via the LLM so even new intents can be handled without retraining.

9. **Memory persistence** — User facts ("mera naam Shivang hai") survive across sessions.

10. **Good test coverage** — Tests exist for brain, TTS, STT, intent classifier, entity extractor, sentiment, memory, conversation, disambiguator, feedback, pipeline, normalizer.

---

## 7. Cons and Problems of Current Implementation

### Performance Problems (Critical)

**P1 — Timer explosion on the GUI thread**  
15+ simultaneous QTimers all firing paintEvent callbacks on the GUI thread. Two of them (ReactorRings + _WireLayer) fire at 60 FPS with ~50–70 QPainter calls each. This means the GUI thread is essentially always in Python-level painting code, leaving almost no headroom for user input events.

**P2 — No GPU acceleration**  
All rendering is pure CPU QPainter. QPainter with the default raster paint engine is entirely CPU-bound. No `QOpenGLWidget`, no Metal, no DirectX. The animated effects (ripples, glows, rotating rings) that feel natural on a GPU are extremely expensive on the CPU.

**P3 — Per-frame object allocation**  
Every `paintEvent` creates dozens of `QColor`, `QPen`, `QPointF`, `QRadialGradient`, `QLinearGradient` Python objects. These must be allocated, reference-tracked, and garbage-collected. At 60 FPS this is ~1200+ object allocations per second just for reactor painting alone.

**P4 — _SmallDot timer accumulation**  
Each message bubble adds a `_SmallDot` with a 60ms QTimer. After 20 messages (a normal conversation), there are 20 additional timers firing on the GUI thread. After a long session: 50+ timers.

**P5 — psutil blocking calls on GUI thread**  
`WiringSystem._tick_live_values` runs `psutil.cpu_percent()`, `psutil.virtual_memory()`, `psutil.net_io_counters()`, `psutil.sensors_battery()` every 2.8s on the GUI thread (via a QTimer on the WiringSystem widget, which is owned by the GUI thread). These are blocking system calls.

**P6 — Streaming text causes scroll area relayout each character**  
`stream_timer` fires every 18ms. Each tick calls `QLabel.setText()` which forces a layout pass on the scroll area. At 18ms intervals during a 200-char response, this is ~11 forced layout passes per second.

**P7 — TTS asyncio loop creation per speak**  
`asyncio.new_event_loop()` + `asyncio.set_event_loop()` per TTS call is wasteful. A persistent event loop with a persistent coroutine would be cleaner.

### Architecture Problems (Important)

**A1 — Legacy UI code left in repo** 
`ui/ui_legacy/`, `ui/ui_laptop/`, `ui/aeris_v4/`, `ui/dashboard.py` — all old UI versions are still in the tree. They're not loaded but they bloat the repo, confuse navigation, and risk accidental import.

**A2 — `core/intent_engine.py` (RapidFuzz) is dead code**  
The old `IntentEngine` using RapidFuzz is still in `core/intent_engine.py` but `main_engine.py` uses `IntentClassifier` (sentence-transformers). The old engine is never called. Confusing.

**A3 — Hardcoded system stats in WiringSystem NodeBoxes**  
`_NODES` in `wiring_system.py` shows hardcoded values for "Intel i9-13900K", "16 GB DDR5-6000", "68Wh", "WiFi 6 · Online" with fixed detail strings. These don't match Shivang's actual machine. The live values (percentage) update via psutil, but the hardware descriptions are fake.

**A4 — `eval()` in calculator intent**  
`ActionExecutor.execute("calculate", ...)` calls `eval(expression)`. Even with a "safe evaluator" wrapper, this is a security risk if the expression comes from voice input.

**A5 — TTS `temp_file` race condition**  
`core/tts.py` always writes to `data/audio_cache/speech.mp3`. If two speak() calls happen concurrently (not currently possible since SpeakWorker serializes them, but could become an issue), they'd overwrite each other.

**A6 — Edge-TTS requires internet**  
If the user is offline and pyttsx3 fallback fails, there is no voice output. The fallback pyttsx3 voice quality is notably worse.

**A7 — No crash recovery**  
If the brain crashes mid-process, there's no auto-restart. The user must close and reopen the app.

**A8 — `data/notes/` and `data/audio_cache/` grow unboundedly**  
No cleanup mechanism for old notes or cached audio files.

---

## 8. Improvement Plan — Complete Overhaul Strategy

### 8.1 Immediate Fixes (Keep PyQt5, Fix Performance)

These can be done without rebuilding anything. They address the worst performance offenders.

---

**FIX 1: Consolidate all timers into one master animation timer**

Instead of 15+ individual QTimers, have a single 16ms `QTimer` on the main window. On each tick, it calls a render-dirty-flag approach:

```python
class AnimationBus(QObject):
    tick = pyqtSignal(float)   # current time in ms
    
    def __init__(self):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(16)
    
    def _on_tick(self):
        self.tick.emit(time.monotonic() * 1000)

# Global singleton
animation_bus = AnimationBus()
```

Every animated widget connects to `animation_bus.tick` and calls `self.update()` from there. This ensures all paintEvents are batched in the same "frame" rather than staggered — reducing the number of times Python re-enters the paint path per 16ms window from ~10 separate events down to 1–2 batched repaints (Qt batches `update()` calls within the same event loop iteration).

**Impact**: Reduces GUI thread re-entry from painting by ~60–70%.

---

**FIX 2: Pre-compute static geometry in `__init__`, cache colors**

Currently `ReactorRings.paintEvent` creates `QColor`, `QPen`, `QRadialGradient` objects every call. Pre-compute everything that doesn't change per frame:

```python
def __init__(self):
    # Pre-build pens
    self._tick_pens = {
        90: QPen(rgba(J.CYAN, 0.55), 1.2),
        30: QPen(rgba(J.CYAN, 0.20), 1.2),
    }
    # Pre-build sphere geometry (lat/lon points as QPointF arrays)
    self._sphere_lat_pts = [...]
    self._sphere_lon_paths = [...]
```

**Impact**: Eliminates ~40% of per-frame object allocations in ReactorRings.

---

**FIX 3: Reduce _WireLayer to 30 FPS (33ms timer)**

The wiring traces move slowly. 30 FPS is visually indistinguishable from 60 FPS for slow linear animations. Packet dash motion at 30 FPS looks identical to 60 FPS.

```python
t = QTimer(self); t.timeout.connect(self.update); t.start(33)  # was 16
```

**Impact**: Cuts _WireLayer paint calls in half (62/s → 30/s).

---

**FIX 4: Remove per-bubble `_SmallDot` timer — use shared animation bus**

Instead of each `_SmallDot` having its own 60ms QTimer, all dots connect to a shared `AnimationBus`. When the bus ticks, they call `update()`. No additional timers.

**Impact**: Stops timer count from growing with conversation length.

---

**FIX 5: Move psutil calls to a background thread**

```python
class SystemMonitor(QObject):
    stats_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._timer = QTimer()
        self._timer.moveToThread(self._thread)
        self._timer.timeout.connect(self._poll)
        self._timer.start(2800)
        self._thread.start()
    
    def _poll(self):
        # This runs on the background thread
        data = {
            "cpu": psutil.cpu_percent(interval=None),
            "ram_gb": psutil.virtual_memory().used / (1024**3),
            ...
        }
        self.stats_updated.emit(data)
```

**Impact**: Eliminates 4 blocking system calls from the GUI thread every 2.8s.

---

**FIX 6: Use `QPixmap` caching for static parts of ReactorRings**

The tick marks and outer dashed ring don't change between frames (only rotate). Pre-render them to a `QPixmap` and blit instead of re-drawing 12 tick lines per frame:

```python
def _build_tick_cache(self):
    self._tick_cache = QPixmap(self.SIZE, self.SIZE)
    self._tick_cache.fill(Qt.transparent)
    p = QPainter(self._tick_cache)
    # draw all 12 ticks once
    p.end()

def paintEvent(self, _):
    p = QPainter(self)
    p.drawPixmap(0, 0, self._tick_cache)  # blit cached ticks
    # only paint the rotating elements
```

**Impact**: Reduces paintEvent time by ~15–20% (tick marks are cheap but eliminating them is still measurable at 60 FPS).

---

**FIX 7: Cap streaming text update rate to 50ms minimum**

Currently `stream_timer` fires every 18ms per character. For long responses this means ~55 layout passes per second. Change to batch 3–4 characters per tick:

```python
# Instead of speed_ms=18 (1 char/18ms)
# Use speed_ms=50 (3 chars/50ms via _stream_chunk_size=3)
def _stream_tick(self):
    chunk = self._stream_full[self._stream_idx : self._stream_idx + 3]
    self._stream_idx += 3
    self._stream_bubble.set_text(self._stream_full[:self._stream_idx])
```

**Impact**: Reduces scroll-area relayout from 55/s to ~18/s during streaming.

---

**FIX 8: Reduce `_NodeBox` sparkline complexity**

Currently each sparkline bar uses a `QLinearGradient` + `setOpacity()`. Opacity changes are expensive (they create implicit graphics effect layers in Qt). Replace with a flat color at varying alpha:

```python
# Instead of grad + setOpacity:
bar_color = QColor(col)
bar_color.setAlphaF(0.45 + (i / bar_count) * 0.25)
p.setBrush(bar_color)
p.drawRoundedRect(...)
```

**Impact**: Eliminates 8 QLinearGradient objects + 8 setOpacity calls per NodeBox per repaint.

---

### 8.2 Medium-Term Improvements

**M1: Refactor TTS to persistent asyncio loop**

```python
class TTS:
    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        
    def speak(self, text):
        future = asyncio.run_coroutine_threadsafe(self._speak_async(text), self._loop)
        future.result()  # block speak thread until done
        
    async def _speak_async(self, text):
        await edge_tts.Communicate(text, self.voice).save(self.temp_file)
        # play via pygame (must be on main thread for pygame... or use another approach)
```

**M2: Replace `_SmallDot` timers entirely with CSS animation**

PyQt5's `QLabel` supports some CSS animations. Or better: use a single shared `QGraphicsEffect` pulse driven by the animation bus.

**M3: Add health-check + auto-restart for brain crash**

If `BrainWorker.process()` throws, emit `error` signal. Main window shows error bubble and offers a "Retry" button that re-emits `request_brain_init`.

**M4: Implement LRU note and audio cache cleanup**

Keep only last 50 notes and last 10 audio files. Add cleanup on startup.

**M5: Replace `eval()` in calculator with `ast.literal_eval` + safe math**

```python
import ast, operator
_SAFE_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ...}
def safe_eval(expr): ...
```

**M6: Retire legacy UI code**

Move `ui/ui_legacy/`, `ui/ui_laptop/`, `ui/aeris_v4/` to a `_archive/` folder and exclude from imports. This cleans up the codebase significantly.

---

### 8.3 Full Architectural Overhaul (Recommended Path)

The fundamental problem is **Python doing animated CPU rendering 60 times per second**. The only real fix is to move rendering off the CPU or off Python entirely.

**Option A: PyQt5 + QOpenGLWidget for animated elements**

Replace `ReactorRings`, `_WireLayer`, `ParticleField` with `QOpenGLWidget` subclasses. Paint via OpenGL shaders. The ring rotations, glows, and particle drifts would run entirely on the GPU and the Python code would only need to update uniform variables (angle, state color, time) — not draw anything.

- Pros: Keeps Python/PyQt5. Dramatic performance improvement. GPU handles all animation.
- Cons: Requires writing GLSL shaders. More complex code. OpenGL widget compositing with regular Qt widgets can be finicky.
- Complexity: Medium-High.

**Option B: Electron + React/Three.js frontend, Python backend**

- Frontend: Electron browser window running a React app. The animated UI (reactor, wiring, particles) is implemented in Three.js (WebGL) or CSS animations + Canvas. This is exactly what the JSX design files (`jv3-reactor.jsx`, `jv3-wiring.jsx`) suggest — the UI was originally designed as a React app.
- Backend: Python process (FastAPI or simple WebSocket server) handles STT, brain, TTS, skills. Communicates with the frontend via WebSocket.
- Pros: The React/Three.js version of this UI would run buttery smooth at 60+ FPS on any hardware. Electron is what Spotify, VS Code, Discord all use. GPU-accelerated rendering. No GIL issues for UI.
- Cons: Requires Node.js + npm + Electron. Frontend/backend split means IPC overhead. Larger final package size.
- Complexity: High (but already partially done — the JSX files exist).

**Option C: Python + Tauri (Rust) + WebView**

- Similar to Option B but uses Tauri (Rust-based) instead of Electron. Smaller binary, better performance, native Rust backend.
- More complex than Electron because requires learning Rust for the native layer.

**Option D: PySide6 + QML + OpenGL (Full Rewrite of UI)**

- Replace PyQt5 with PySide6 (newer, officially supported by Qt Company).
- Rewrite all animated widgets as QML components. QML has built-in hardware-accelerated animations (`PropertyAnimation`, `NumberAnimation`, `SequentialAnimation`) that run on the Qt Scene Graph (GPU).
- The reactor rings, particle field, wiring traces — all trivially animated in QML with no Python involvement.
- Python stays for brain/voice/TTS. PySide6 has excellent Python-QML integration.
- Pros: Hardware-accelerated QML. Clean separation of UI (QML) and logic (Python). Better than PyQt5's QPainter for complex animations.
- Cons: Full UI rewrite. PySide6 QML has a learning curve.
- Complexity: High (full rewrite).

**Recommended path for maximum impact with minimum disruption**:

1. **First**: Apply all 8 immediate fixes — this should make the app usable without the "not responding" prompt.
2. **Then**: Apply medium-term improvements M1–M6.
3. **Long term**: Migrate to PySide6 + QML (Option D) or Electron + React/Three.js (Option B, since the JSX files already exist for the design).

---

## 9. Component-by-Component Reference

### `core/normalizer.py — HinglishNormalizer`
Cleans text for the intent classifier:
- Lowercases
- Strips extra whitespace
- Applies `data/hinglish_dict.json` substitutions (e.g., "kholo" → "open", "band karo" → "close")
- Removes filler words

### `core/sentiment.py — SentimentAnalyzer`
Classifies text as positive/negative/neutral. Likely uses VADER or a simple word list. Result influences the LLM fallback prompt (to acknowledge user mood).

### `core/conversation.py — ConversationHistory`
In-memory circular buffer of last 8 turns (user + assistant pairs). Passed to LLM fallback as context. Resets on session start.

### `core/disambiguator.py — Disambiguator`
When the top-3 intent predictions are too close (e.g., `open_app=0.42` vs `close_app=0.37`), asks the user: "Did you mean X or Y?" Parses the answer ("pehla" = first, "doosra" = second, etc.).

### `core/state_manager.py — StateManager`
Tracks multi-turn state:
- `IDLE` — normal, process each utterance fresh
- `SLOT_FILLING` — waiting for a specific slot value (e.g., "Kaunsa app kholna hai?")
- `AWAITING_DISAMBIG` — waiting for the user to pick between two intents

### `core/entity_extractor.py — EntityExtractor`
Extracts named entities from the utterance:
- App names from `data/entities.json` gazetteer
- Time expressions parsed by `core/time_parser.py`
- Person names, URLs, quantities
- `intent_hint()`: if text contains a known app name + open/close verb, override brain prediction

### `core/memory.py — UserMemory`
JSON-backed store in `data/user_memory.json`. Regex-pattern matching for:
- Save: "mera naam Shivang hai" → `{"naam": "Shivang"}`
- Recall: "mera naam kya hai?" → "Aapka naam Shivang hai."

### `core/feedback.py — FeedbackStore`
SQLite database at `data/feedback_log.sqlite`. Stores every utterance with:
- `raw_text`, `normalized_text`, `predicted_intent`, `confidence`, `top3`
- `sentiment_label`, `sentiment_score`
- `action_taken` (executed / asked_slot / asked_disambig / chat_fallback / rejected)
- `feedback` (None / accepted / corrected / cancelled)
- `correct_intent` (if corrected)

Per-intent confidence threshold = max(0.3, mean_confidence of accepted utterances for that intent).

### `core/llm_chat.py — LLMChat`
Connects to Ollama (local LLM server, typically running on `localhost:11434`). 
- `is_available()` → HEAD request to check if Ollama is running
- `reply(user_text, sentiment_label, memory_facts, history)` → chat completion
- `reply_with_tools(...)` → structured tool-calling (lets LLM invoke skill functions by name)

### `core/scheduler.py — ReminderScheduler`
Wraps APScheduler. `add(message, time_string)` → schedules a one-shot job that calls the callback at the specified time. Callback calls `TTS.speak()` with the reminder message.

### `core/utterance_parser.py`
- `split_into_segments(text)`: splits "X aur Y" and "X phir Y" into ["X", "Y"]
- `find_best_interpretation(text, brain)`: tries the full text, then progressively trims common filler prefixes ("ek kaam karo", "zara", etc.) and picks the highest-confidence prediction

### `ui/jarvis_v31/title_bar.py — TitleBar`
- Frameless window custom title bar: brand "A.E.R.I.S" text, state pill, minimize/maximize/close buttons
- Emits `drag_start` and `drag_move` signals for window dragging
- `pill.set_state(key)` — updates the state indicator color

### `ui/jarvis_v31/logs_bar.py — LogsBar`
- Collapsible bottom strip (~48px collapsed, ~180px expanded)
- Color-coded log entries: SYS=cyan, NLU=magenta, MIC=green, ERR=red, TTS=purple, ACT=amber
- Scroll area for history

---

## 10. Data Files Reference

### `data/intents.json`
Structure:
```json
{
    "open_app": {
        "patterns": ["open chrome", "chrome kholo", ...],
        "required_entities": ["app_name"],
        "prompts": {"app_name": "Kaunsa app kholna hai?"}
    },
    "close_app": { ... },
    "get_weather": { ... },
    ...
}
```
~21+ intent classes, ~300+ total patterns. Every time this file changes (detected via MD5 hash), the k-NN index is automatically rebuilt on next boot.

### `data/entities.json`
Gazetteer: maps entity types to lists of known values.
```json
{
    "app_name": ["chrome", "notepad", "spotify", "discord", ...],
    "city_name": ["mumbai", "delhi", "bangalore", ...],
    ...
}
```

### `data/user_memory.json`
Free-form JSON dict of user facts. Example:
```json
{
    "naam": "Shivang",
    "favorite_color": "blue",
    "city": "delhi"
}
```

### `data/settings.json`
App config. Example fields:
```json
{
    "assistant_name": "JARVIS",
    "theme": "dark",
    "tts_voice": "en-IN-NeerjaNeural",
    "wake_word": "jarvis"
}
```

### `data/models/intent_index.pkl`
Pickled dict: `{"embeddings": np.ndarray, "labels": list[str], "encoder_name": str}`

### `data/models/intent_metadata.json`
```json
{
    "intents_hash": "abc123...",
    "encoder_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "num_patterns": 301,
    "num_classes": 21,
    "built_at": "2025-04-23T14:32:00"
}
```

### `data/models/vosk-model/`
Optional offline STT model directory. If present, used as fallback when Google Speech Recognition fails or when voice is in SLEEPING mode (wake-word detection only needs offline model).

---

## 11. Dependency List and Their Roles

| Package | Role | Heavy? |
|---|---|---|
| `PyQt5` | GUI framework — widgets, signals, timers, threading | No (C++ library) |
| `torch` | Required by sentence-transformers. Pre-imported in run_gui.py to fix DLL load order. | Yes — 800MB+ install, ~2–5s import |
| `sentence-transformers` | Loads `paraphrase-multilingual-MiniLM-L12-v2` (420MB). Core of intent classification. | Yes — multi-second cold load |
| `scikit-learn` | `NearestNeighbors` for k-NN intent index | Moderate |
| `numpy` | Array operations for embeddings | Moderate |
| `spaCy` | NER entity extraction in `EntityExtractor` | Yes — model download + load |
| `speech_recognition` | Google STT (online) + audio capture wrapper | Moderate |
| `pyaudio` | Microphone audio capture (dependency of speech_recognition) | No |
| `vosk` | Offline STT (keyword detection, wake word) | Moderate (model-dependent) |
| `edge_tts` | Microsoft Edge TTS (online, free, high quality) | No (network) |
| `pyttsx3` | Offline TTS fallback (Windows SAPI5 voices) | No |
| `pygame` | Audio playback for Edge-TTS MP3 output | No |
| `psutil` | CPU/RAM/battery/network stats | No |
| `rapidfuzz` | Used in legacy `IntentEngine` only (now dead code in main path) | No |
| `APScheduler` | Reminder scheduling (`core/scheduler.py`) | No |
| `requests` / `httpx` | Ollama LLM API calls (`core/llm_chat.py`) | No |
| `pyautogui` | Screenshot + GUI automation | No |
| `pywhatkit` | WhatsApp automation (`skills/whatsapp.py`) | No |
| `mediapipe` | Gesture detection (`core/gesture_engine.py`) | Yes |
| `ultralytics` (YOLO) | Object detection (`core/object_detector.py`) | Yes |
| `cryptography` | Vault encrypted storage (`core/vault.py`) | No |

**Total cold-boot import time estimate** (brain thread, background):
- torch: 2–5s
- sentence-transformers + model load: 5–15s  
- spaCy (with model): 2–4s
- Index load (warm cache) or rebuild (cold): 2–30s

**Total cold-boot import time** from user's perspective: **10–45 seconds** until "Brain ready" appears. During this time the GUI is responsive (animations were paused, brain is at LowestPriority), but there's visible variance.

---

## Summary — The One-Page Version

**What is it**: A Python/PyQt5 Iron Man–themed desktop AI assistant with Hinglish voice/text support, NLU pipeline, and a heavily animated sci-fi UI.

**Why it freezes on click**: The GUI thread runs 15+ QTimers simultaneously, two of which fire every 16ms and execute 50–70 QPainter operations per frame in pure Python. This leaves virtually no headroom for input event processing. Python has no GPU rendering path here — everything is CPU software rasterization.

**Why GTA doesn't freeze**: GTA uses C++ and DirectX (GPU). JARVIS uses Python and QPainter (CPU). These are not comparable. GTA's rendering doesn't touch the CPU message loop at all.

**Quickest fix**: Consolidate all timers into one shared animation bus, pre-cache static geometry, move psutil off the GUI thread, and reduce _WireLayer from 60 FPS to 30 FPS. These 8 fixes together should eliminate the "not responding" prompt.

**Long-term fix**: Migrate the animated UI to QML (PySide6) or React/Three.js (Electron), where hardware-accelerated animation is native and Python handles only the AI brain logic.

---

*Document created: 2026-05-17. Working directory: `New version- 3.0/`. All file paths are relative to the project root.*
