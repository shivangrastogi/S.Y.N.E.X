# A.E.R.I.S / JARVIS v3.2

**Adaptive Emotional Reasoning & Intelligent System** — a production-grade,
Hinglish-native personal AI assistant for Windows, written in Python with
a PyQt5 GUI.

This README is written so that another person — or a language model — can
read it once and have an accurate, complete mental model of the project:
what each piece is, **why it was designed that way**, and how the pieces
interact at runtime. If you are pasting this into ChatGPT or another LLM
to get help, this is everything you need.

---

## Table of Contents

1. [Briefing — the project in one page](#1-briefing--the-project-in-one-page)
2. [Design principles — the *why*](#2-design-principles--the-why)
3. [Quick start](#3-quick-start)
4. [Repository layout](#4-repository-layout)
5. [Pipeline at a glance](#5-pipeline-at-a-glance)
6. [The Brain — how it "learns" and why there is no training step](#6-the-brain--how-it-learns-and-why-there-is-no-training-step)
7. [Core module reference](#7-core-module-reference)
8. [Skills, intents, and the action executor](#8-skills-intents-and-the-action-executor)
9. [GUI architecture (jarvis_v31)](#9-gui-architecture-jarvis_v31)
10. [Threading model](#10-threading-model)
11. [Boot smoothness — keeping the GUI silky during heavy ML loads](#11-boot-smoothness--keeping-the-gui-silky-during-heavy-ml-loads)
12. [Data files — schemas and ground-truth assets](#12-data-files--schemas-and-ground-truth-assets)
13. [Testing strategy](#13-testing-strategy)
14. [Dependencies and setup](#14-dependencies-and-setup)
15. [Common workflows](#15-common-workflows)
16. [Roadmap](#16-roadmap)
17. [Glossary](#17-glossary)

---

## 1. Briefing — the project in one page

**Who it is for.** A single power user (Shivang) on Windows. AERIS is a
personal voice assistant that runs locally, understands mixed
Hindi-English (Hinglish) commands, executes desktop automations
(opening apps, search, screenshots, system info, notes, reminders, etc.),
remembers facts about the user, and falls back to a local LLM (Ollama)
for free-form chat when the intent classifier doesn't recognize a command.

**What runs locally.** Everything except optional cloud TTS and Google
SR speech recognition. The intent classifier, entity extractor, sentiment
analyzer, memory store, feedback database, and LLM (Ollama) all run on
the user's machine.

**Languages.** Hinglish is first-class. The encoder is multilingual; the
sentiment lexicon is augmented with ~40 Romanized-Hindi words; the
entity extractor recognizes Hinglish trigger words; the LLM prompt
tells the model to respond in whatever mix the user used.

**Surfaces.**
- `python main.py` — voice REPL (mic in → text out → speaker)
- `python main.py --text` — text REPL (no audio dependencies needed)
- `python run_gui.py` — full PyQt5 desktop app (this is the primary surface)

**Brain stack at a glance.**

```
text in → normalize → memory check → split into sub-commands
       → per segment: sentiment → intent classify → disambiguate?
       → extract entities → run state machine → execute skill
       → if low confidence: LLM chit-chat or queue for review
       → reply text → TTS out
```

There is **no training step in the traditional sense**. The intent
classifier embeds a few hundred labeled patterns from `data/intents.json`
through a frozen multilingual transformer and stores them in a k-NN
index. New utterances are routed by nearest-neighbor cosine vote. See
§6 for the full rationale.

**Memory and feedback.**
- Long-term facts live in `data/user_memory.json`.
- Every utterance plus its outcome is logged to `data/feedback_log.sqlite`.
- A per-intent acceptance threshold floats with an exponential-moving
  average over user reward (+1 accepted, -1 corrected, 0 ignored).
  Low-confidence utterances queue for an interactive review CLI
  (`python -m core.review_cli`).

**Recent work (April-May 2026).**
The brain stack takes 5-10 s to initialize on cold boot — sentence-
transformers, spaCy, SQLite, etc. — which used to freeze the GUI at
"15 %" during boot. The current code splits init into 7 chunks, runs
the brain worker at QThread.LowestPriority, and pauses the heaviest
60 fps animations while loading so the UI stays smooth. See §11.

---

## 2. Design principles — the *why*

Every architectural choice in AERIS came from one of these guard rails.
When you read the codebase and see a quirk, it almost always traces
back to one of these:

1. **No cloud dependency for inference.** Speech recognition can use
   Google SR online, but the *brain* (intent classification, entity
   extraction, sentiment, memory, LLM) is fully local. The user owns
   their own utterances. Cloud calls fail open: when offline, AERIS
   falls back to Vosk for STT, pyttsx3 for TTS, and an "I didn't
   understand" message if Ollama is also down.

2. **Hinglish is first-class, not bolted-on.** The encoder is multilingual.
   The sentiment lexicon includes Romanized Hindi. The entity extractor
   strips Hinglish filler words ("bhai", "yaar", "ek kam karo") before
   classification. The LLM system prompt tells the model to match the
   user's language mix instead of normalizing to English.

3. **No backprop, no GPUs.** Adding new commands should not require
   training a model. New patterns are added to a JSON file; the index
   rebuilds in seconds via embed-and-cache. The user can review queued
   low-confidence patterns and approve them, growing the catalog over
   time without ever touching a learning rate.

4. **Graceful degradation.** spaCy missing → entity extractor still
   works without NER. Ollama down → low-confidence utterances queue
   for review instead of crashing. Vosk missing → falls back to Google
   SR. PyTorch DLL broken → window still opens; brain reports a clean
   error in the chat panel. Nothing in this codebase fails by exception
   when a soft fallback would do.

5. **Single user, single machine.** No auth, no multi-tenancy, no
   horizontal scaling concerns. SQLite is fine because there is exactly
   one writer. Memory lives in a JSON file because it is a few KB.
   Decisions that would be wrong at scale (e.g., string-keyed dicts
   for app aliases) are correct for n=1.

6. **GUI smoothness is non-negotiable.** Backend can take time to load.
   The GUI must not stutter, freeze, or block while it does. The
   threading model and boot-smoothness work in §10 and §11 exist
   entirely to honor this principle.

7. **Tests are at the brain layer, not the GUI layer.** PyQt is
   awkward to test in CI; the brain is pure Python and can be exercised
   end-to-end via `JarvisMainEngine.process_text(text)`. The pytest
   suite goes deep on the brain modules and stubs out audio I/O.

---

## 3. Quick start

```bash
# Install
pip install -r requirements.txt
python -m spacy download en_core_web_sm    # optional: nicer NER

# Optional: install Ollama (https://ollama.com), then
ollama pull phi3:mini                       # 3.8 B, ~2.4 GB

# Run
python run_gui.py        # PyQt5 desktop app — primary surface
python main.py           # voice REPL
python main.py --text    # text REPL (no microphone, no audio)
python -m pytest tests/  # ~3-4 minutes; full brain coverage
python -m core.review_cli   # interactive low-confidence pattern review
```

**Cold-boot expectations.**
- `run_gui.py`: torch + PyQt5 import takes ~3-5 s before window paints
  (Windows DLL ordering — see §11). Then the brain stack initializes
  on a worker thread for another 5-10 s while the boot bubble walks
  4 % → 100 %. The window itself is interactive throughout.
- `python main.py`: ~5-10 s before the prompt appears.

---

## 4. Repository layout

```
new version- 3.0/
│
├── main.py                          Terminal entry point (voice + text REPL)
├── run_gui.py                       PyQt5 GUI launcher (JARVIS v3.1 window)
├── requirements.txt                 Full dependency list
│
├── core/                            Brain pipeline — ~3,700 lines, the heart of AERIS
│   ├── __init__.py
│   ├── main_engine.py              Orchestrator. process_text() runs full pipeline
│   ├── brain.py                    Thin wrapper over IntentClassifier
│   ├── intent_classifier.py        Sentence encoder + k-NN; the "model"
│   ├── intent_engine.py            Optional fuzzy fallback (rapidfuzz)
│   ├── entity_extractor.py         4-layer extractor (regex + gazetteer + NER + residual)
│   ├── normalizer.py               Hinglish text cleaner (lowercase, punctuation, ws)
│   ├── sentiment.py                VADER + Hinglish lexicon extension
│   ├── memory.py                   Long-term JSON-backed user facts
│   ├── conversation.py             Rolling 8-turn context buffer
│   ├── llm_chat.py                 Ollama HTTP client for chit-chat fallback
│   ├── disambiguator.py            "Close-call" intent clarification prompts
│   ├── state_manager.py            Slot-fill / disambig multi-turn state machine
│   ├── feedback.py                 SQLite logger + EMA threshold learner (the "bandit")
│   ├── utterance_parser.py         Multi-command splitter ("X aur Y") + subspan scanner
│   ├── stt.py                      Speech-to-text (Google SR online → Vosk offline)
│   ├── tts.py                      Text-to-speech (Edge-TTS online → pyttsx3 offline)
│   ├── voice_engine.py             Continuous mic listener with wake/sleep states
│   ├── executor.py                 Skill dispatcher (21 intents, 25+ apps, Win32 calls)
│   └── review_cli.py               Interactive review of low-confidence pending patterns
│
├── ui/
│   ├── jarvis_v31/                  Current production UI
│   │   ├── main_window.py          Qt main window + BrainWorker / VoiceWorker / SpeakWorker
│   │   ├── glass_chat_panel.py     390 px right rail — header, automation chips, chat
│   │   ├── reactor.py              460 × 460 animated core + particles + state switcher
│   │   ├── floating_dock.py        Left sidebar dock (collapsing, with profile menu)
│   │   ├── tab_panels.py           Right-rail tabbed panel stack
│   │   ├── wiring_system.py        Background grid of interconnected node cards
│   │   ├── logs_bar.py             Bottom collapsible log feed
│   │   ├── title_bar.py            Frameless title bar with state pill + window buttons
│   │   └── tokens.py               Design tokens (J colors, JSTATES, font helpers)
│   ├── aeris_v4/                    Previous AERIS layout (preserved, not active)
│   ├── ui_laptop/                   Earlier desktop variant
│   └── ui_legacy/                   Archived earlier prototypes
│
├── data/
│   ├── intents.json                 21 intent definitions + Hinglish patterns + slot prompts
│   ├── entities.json                Gazetteer of app aliases (chrome → ["chrome", "google-chrome"])
│   ├── user_memory.json             Persistent user facts (created on first save)
│   ├── hinglish_dict.json           Vocabulary reference (not used at runtime)
│   ├── feedback_log.sqlite          Utterance log + per-intent thresholds + pending patterns
│   ├── models/
│   │   ├── intent_index.pkl         Cached k-NN embeddings (auto-rebuilt on intents.json change)
│   │   ├── intent_metadata.json     Hash, encoder name, build timestamp
│   │   └── hand_landmarker.task     MediaPipe gesture model (utils/gesture.py)
│   ├── audio_cache/                 TTS output (speech.mp3 — overwritten per call)
│   ├── logs/                        System logs (rotated externally)
│   └── notes/                       User-created notes (one JSON per note)
│
├── tests/                           pytest suite — 13 files, ~25 active tests
│   ├── conftest.py                  Shared fixtures (tmp_memory_path, tmp_feedback_db)
│   ├── test_brain.py                JarvisBrain end-to-end predict
│   ├── test_intent_classifier.py    Encoder load, k-NN, cache rebuild on hash change
│   ├── test_entity_extractor.py     All 4 extractor layers
│   ├── test_sentiment.py            VADER + Hinglish lexicon
│   ├── test_memory.py               Pattern detection, fact storage, recall
│   ├── test_conversation.py         Rolling buffer + OpenAI message format
│   ├── test_disambiguator.py        Close-call detection + answer parsing
│   ├── test_feedback.py             SQLite logger + EMA threshold drift
│   ├── test_normalizer.py           Punctuation strip + URL/math preservation
│   ├── test_pipeline.py             End-to-end JarvisMainEngine.process_text()
│   ├── test_stt.py                  Mocked STT
│   └── test_tts.py                  Mocked TTS
│
├── utils/
│   ├── gesture.py                   OpenCV + MediaPipe hand-tracking sandbox
│   ├── monitor.py                   System monitoring helpers
│   └── __init__.py
│
├── BRAIN_BUILD_PLAN.md              Original 9-checkpoint architecture plan
├── BRAIN_CHECKPOINTS.md             Implementation status tracker
├── BRAIN_REVIEW.md                  Code review notes
├── _aeris_smoke.py                  Standalone visual smoke test (older AERIS UI)
└── _jv31_smoke.py                   JARVIS v3.1 visual smoke test
```

---

## 5. Pipeline at a glance

A single utterance, end-to-end, in `JarvisMainEngine.process_text(text)`:

```
                    raw user text
                          │
                          ▼
            ┌─────────────────────────────┐
            │ Step 0a: state.is_waiting?  │  yes → fill slot, return
            ├─────────────────────────────┤
            │ Step 0b: state.is_disambig? │  yes → route to chosen intent
            ├─────────────────────────────┤
            │ Step 1: pending feedback?   │  yes → record accept/correct
            ├─────────────────────────────┤
            │ Step 2a: memory recall?     │  yes → return the fact
            ├─────────────────────────────┤
            │ Step 2b: memory store?      │  yes → save + acknowledge
            ├─────────────────────────────┤
            │ Step 3: cancel keyword?     │  yes → "kuch chal nahi raha"
            ├─────────────────────────────┤
            │ Step 4: split into segments │  utterance_parser.split_into_segments
            └────────────┬────────────────┘
                         │  for each segment:
                         ▼
            ┌─────────────────────────────┐
            │  sentiment.classify         │  VADER (with Hinglish boost)
            ├─────────────────────────────┤
            │  find_best_interpretation   │  try the segment + 5 trimmed variants
            │                             │  keep the one with highest confidence
            ├─────────────────────────────┤
            │  gazetteer override?        │  app_name + open/close verb seen?
            │                             │  yes → force the structural intent
            ├─────────────────────────────┤
            │  feedback.get_threshold     │  per-intent EMA-learned floor
            ├─────────────────────────────┤
            │  confidence ≥ threshold?    │
            │   ├─ no → LLM fallback or queue for review
            │   └─ yes → continue
            ├─────────────────────────────┤
            │  disambiguator.is_close?    │  top1-top2 < 0.05 and top1 < 0.85?
            │   ├─ yes → ask + wait one turn
            │   └─ no → continue
            ├─────────────────────────────┤
            │  entity_extractor.extract   │  regex → gazetteer → spaCy → residual
            ├─────────────────────────────┤
            │  state.process_prediction   │  all required slots present?
            │   ├─ no → ask + wait one turn
            │   └─ yes → SUCCESS_EXECUTE
            ├─────────────────────────────┤
            │  executor.execute           │  21 skill handlers
            ├─────────────────────────────┤
            │  feedback.log_utterance     │  row in SQLite for later analysis
            └─────────────────────────────┘
                         │
                         ▼
                   response text
```

The pipeline is purposefully linear and side-effect-light. Each step is
testable in isolation. The only stateful concerns are the multi-turn
state machine (`StateManager`) and the SQLite feedback log; everything
else is a function of (text, in-memory state) → (text, log entries).

---

## 6. The Brain — how it "learns" and why there is no training step

This is the most-asked question about the project, so it gets its own
section. **There is no gradient-based training in AERIS.** The intent
classifier is a *retrieval* system over a small, hand-curated catalog
of labeled phrases.

### 6.1 The encoder

```python
ENCODER_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

**What it is.** A 12-layer MiniLM transformer, pre-trained on parallel
text in 50+ languages with a paraphrase-detection objective. Output is
a 384-dimensional sentence embedding. ~120 MB on disk.

**Why this specific encoder.**

- **Multilingual.** It understands Hinglish natively. We do not have
  to translate "kholo" to "open" before embedding — the encoder
  already maps "open chrome" and "chrome kholo" to nearby points in
  embedding space.
- **Small.** 384 dims, ~120 MB. Loads in 2-3 s on cold boot, fits in
  user RAM. A larger model (e.g., 768-dim mBERT) would not move the
  needle on accuracy at this catalog size and would balloon load time.
- **Frozen.** We never fine-tune it. Adding a new intent does not
  require GPU training, just adding patterns to `intents.json`.
- **Pre-trained for similarity.** Paraphrase-detection objective means
  "open chrome" and "chrome launch karo" are already close in
  embedding space without any tuning on our part.

The encoder is loaded once per process (in `IntentClassifier.load_encoder`)
and shared across all queries.

### 6.2 The "training" step (which is just embed-and-cache)

`data/intents.json` looks like this:

```json
{
  "open_app": {
    "patterns": [
      "open chrome", "chrome kholo", "launch browser",
      "brave open karo", "vs code start kar"
    ],
    "required_entities": ["app_name"],
    "prompts": { "app_name": "Kaunsa app kholna hai?" }
  },
  "get_weather": {
    "patterns": ["weather batao", "mausam kya hai", "what's the weather"],
    "required_entities": [],
    "prompts": {}
  }
  // ...19 more intents
}
```

At boot time, `IntentClassifier` does this **once**:

1. Read every `(pattern, intent)` pair from intents.json (~250-300 pairs).
2. Run each pattern through `HinglishNormalizer.clean(text)` (lowercase,
   strip non-essential punctuation, collapse whitespace).
3. Embed every cleaned pattern via `SentenceTransformer.encode(...)` →
   one 384-dim vector per pattern.
4. Stack vectors into a numpy array; fit a `sklearn.NearestNeighbors`
   index with `metric="cosine"`, `k=5`.
5. Pickle the embeddings + labels into `data/models/intent_index.pkl`,
   and write `intent_metadata.json` with the MD5 hash of intents.json.

On subsequent boots, the metadata hash is checked against the current
intents.json hash. If they match, the pickle is loaded and step 1-4
are skipped. If they differ, the index rebuilds automatically. This is
the closest thing to a "training pipeline" AERIS has — and it costs
zero data scientist time.

**Why k-NN over a softmax classifier.**

- **No training.** Adding a new intent is a JSON edit + a few-second
  rebuild, not a gradient descent run.
- **Robust to small data.** With 5-15 patterns per intent, a softmax
  classifier on top of frozen embeddings would overfit. k-NN does not
  overfit — it just looks up nearest neighbors.
- **Top-K is free.** The disambiguator needs the top-3 candidate
  intents to decide whether to ask the user. k-NN gives this directly;
  a softmax would need a second-step calibration.
- **Easy to audit.** When prediction is wrong, we can inspect *which*
  patterns it matched against. With a softmax we'd be debugging
  weights.

### 6.3 The voting rule

```python
similarities = max(0, 1 - distances)        # cosine sims of top-5
weights      = exp(10 * similarities)       # exponential weighting
scores       = group-by-intent and sum(weights)
winner       = argmax(scores)
confidence   = top-1 cosine similarity (raw, not vote-share)
```

**Why exponential weighting.** A naive k-NN sums up the votes of the
top-5 neighbors equally. That can lose to a competitor when a single
near-perfect match for intent A is outvoted by 4 mediocre matches for
intent B. The exponential weight means a single similarity-0.95 neighbor
contributes ~e⁹·⁵ ≈ 13,360 weight, while a similarity-0.7 neighbor
contributes ~e⁷ ≈ 1,096. One excellent match dominates several mediocre
ones — which is the right behavior when intent boundaries are sharp.

**Why confidence is top-1 cosine similarity, not vote share.** Vote
share (e.g., "open_app: 0.6, close_app: 0.4") depends on how many
sibling intents share the neighborhood, which is unstable. Top-1
cosine similarity is the raw semantic match strength and is well-
calibrated across intents — it answers the question "how similar is
this utterance to my closest known phrasing of any intent?".

### 6.4 Per-intent threshold learning (the "bandit")

The brain does not have a single fixed acceptance threshold (e.g.,
"trust intent classification when confidence ≥ 0.5"). Instead, every
intent has its own threshold that drifts over time based on user
reward.

**Setup (`core/feedback.py`).**

```
ALPHA                       0.10    EMA smoothing factor
DEFAULT_THRESHOLD           0.50    starting point for any new intent
MIN_THRESHOLD               0.40    floor — never refuse this much
MAX_THRESHOLD               0.90    ceiling — never trust above this
DRIFT_DOWN_AFTER_SAMPLES    5       need this many samples before lowering
DRIFT_DOWN_REWARD_GATE      +0.5    avg reward must exceed this to lower
DRIFT_UP_REWARD_GATE        −0.2    avg reward below this raises threshold

reward map:
   accepted   → +1   (user did not correct in next turn)
   corrected  → -1   (user said "galat" / "wrong" within one turn)
   cancelled  → -1   (user aborted slot-fill or disambig)
   ignored    →  0   (no signal observed)
```

**Why this is a contextual bandit, not RL.**

- Each utterance is a one-shot decision — there is no sequential state.
- The reward arrives at most one turn later (the "did you say galat?"
  window).
- The action set is small: {execute, ask disambig, fall back to LLM}.

A full RL loop (Q-learning, policy gradients) would be wildly
overpowered here. A per-arm EMA over a +1/0/-1 reward is the well-
known correct tool for this shape.

**What the threshold actually controls.** When the brain emits a
prediction with confidence c for intent X, AERIS executes only if
c ≥ get_threshold(X). Below threshold, the utterance falls through
to the LLM chit-chat fallback (or, if Ollama is down, queues for
manual review).

Over time, an intent that the user reliably accepts will have its
threshold *drop* (accept earlier — the bandit has learned the user
trusts it). An intent the user keeps correcting will have its threshold
*rise* until either confidence is overwhelming or the brain refuses.

**Why this approach works for n=1.** A real ML system would A/B test
across users. Here we have one user; their feedback IS the training
signal. The EMA + sample-count gate prevents one bad feedback from
swinging the threshold wildly.

### 6.5 The disambiguator

When top-1 and top-2 vote shares are very close (delta < 0.05) AND
top-1 cosine is below 0.85, AERIS asks the user instead of guessing:

> "Aap chahte ho main app open karu, ya app close karu?"

The user's answer ("open" / "close" / "1" / "2" / "open_app") routes
to the chosen intent. If the user picked top-1, the bandit records
"accepted"; if they picked top-2 or further, "corrected" (and the
correct intent is logged). This is the highest-quality reward signal
in the system because the user has explicitly chosen.

### 6.6 Active learning queue

When the classifier rejects an utterance for low confidence and Ollama
is also unavailable (or even when Ollama replied), the raw text plus
its top-3 candidates are queued in `pending_patterns`. Run
`python -m core.review_cli` to walk through the queue and either:

- Approve as one of the top-3 candidates (1, 2, 3)
- Approve under a custom intent name
- Skip
- Reject

Approved patterns are appended to `intents.json`, which causes the
hash to change, which causes the index to rebuild on next boot. This
is how AERIS grows its catalog without anyone training a model.

---

## 7. Core module reference

Each entry: **what it does → why it exists → key public surface**.

### `main_engine.py` — the orchestrator
Contains `JarvisMainEngine`. Public methods: `process_text(text) → str`
(pure pipeline), `run()` (audio loop), and `setup_iter()` (chunked
init generator used by the GUI; see §11).

`__init__` accepts `lazy=True` to skip the heavy work and let the
caller drive `setup_iter()` chunk by chunk. The default `lazy=False`
behavior is identical to the historical eager path (used by main.py
and the test suite).

### `brain.py` — the intent shim
Thin wrapper around `IntentClassifier`. Exists so the rest of the code
imports `JarvisBrain` and we can swap the classifier internals (e.g.,
to FAISS for 10K+ patterns) without changing the import surface.
Exposes `load_encoder()` and `build_or_load_index()` so the boot can
yield between the two heavy steps.

### `intent_classifier.py` — the model
The encoder + k-NN core. Public surface:
- `predict(text, threshold=0.5) → Prediction(intent, confidence, top3, ...)`
- `rebuild()` — force re-embed and re-cache (use after hot-editing
  intents.json without restarting)
- `load_encoder()` and `build_or_load_index()` — the two split phases.

The `Prediction` dataclass carries everything downstream needs:
the chosen intent, raw confidence, top-3 with vote shares, and
raw + normalized text for logging.

### `entity_extractor.py` — slot filling in 4 layers
For a given (text, intent), returns `{slot_name: value}`. Layers
applied in order; first hit per slot wins:

1. **Regex layer.** Time, URL, number, math expression, "with X" / "X
   ke saath" person.
2. **Gazetteer layer.** App names from `data/entities.json` (25+ apps
   with Hinglish aliases).
3. **spaCy NER (optional).** PERSON, DATE, GPE, etc. Skipped silently
   if spaCy is not installed — the system still works.
4. **Residual span.** For free-form slots (search query, note content,
   reminder message), strip the intent's trigger words from the
   utterance and use whatever is left as the slot value.

**Why 4 layers instead of one ML model.** Each layer has different
strengths and failure modes. Regex is brittle but precise (a time is
a time). Gazetteer is exhaustive within its domain (we know our app
list). spaCy is general but optional. Residual is the catch-all. By
chaining them, we get good coverage with minimal training data.

`intent_hint(text)` is a separate helper that returns the most
probable intent based purely on structural evidence (a known app name
+ an open-ish verb). This is how we override the brain's prediction
when it disagrees with obvious structural cues — e.g., "brave open
karo" is unambiguously `open_app` even when the brain hesitates.

### `normalizer.py` — light text cleaner
Lowercase, replace non-essential punctuation with spaces, collapse
whitespace. Preserves URL-safe characters (`/`, `:`, `.`, `-`, `+`,
`%`) so the entity extractor can still find URLs and math expressions
in cleaned text. Used by both the classifier (on patterns at index
time AND on inputs at predict time) and the rest of the pipeline.

**Why not a translation layer.** An earlier version of AERIS had a
Hinglish-to-English translation step (kholo → open, etc.). It was
deleted because it was actively harmful — the multilingual encoder
understands Hinglish natively, and translation stripped useful
context (the user's specific phrasing is part of the signal).

### `sentiment.py` — VADER + Hinglish lexicon
Wraps VADER (pure-Python, lexicon-based) and extends its English
lexicon with ~40 Romanized Hindi words ("accha" +2.0, "bakwaas" -3.0,
etc.). Produces `Sentiment(label, score)` per segment.

Sentiment is per-segment, not per-utterance, so a "weather batao aur
tu bekaar hai" reply picks up the negative tone of the second clause.
The label is currently used by the LLM fallback to tell phi3 to be
gentle / direct / energetic.

Upgrade path: swap `_classify` to `cardiffnlp/twitter-xlm-roberta-base
-sentiment` (multilingual transformer) for true Hindi quality. VADER
is the v1 because it has zero load time and works decently on
Romanized Hindi.

### `memory.py` — long-term user facts
JSON-backed at `data/user_memory.json`. Three storage shapes:
- `facts`: single key-value pairs ("name", "location", "employer").
- `notes`: list of free-form note objects.
- `preferences`: assistant-level prefs (language, etc.).

Public API: `detect_and_store(text)` returns an ack string if the
text matches a "remember"-style pattern (and saves the fact); returns
None otherwise. `detect_and_recall(text)` returns the fact string if
text is an interrogative ("mera naam kya hai") matching a saved key.
`all_facts()` for the LLM prompt context.

**Why the recall check runs BEFORE the store check.** "mera naam kya
hai" superficially matches both "what is my name?" (recall) and
"my name is..." (store). Running recall first means interrogative
questions are answered, not accidentally treated as a name update to
the literal value "kya hai".

### `conversation.py` — short-term context
Rolling deque of the last 8 turns (= 16 messages). Used to give the
LLM fallback some context. Per-turn append; oldest evicted. Exposes
`as_messages()` in OpenAI message format because that's what Ollama
expects too.

### `disambiguator.py` — close-call routing
`is_close_call(prediction)` returns True when top-1 minus top-2 vote
share is below 0.05 AND top-1 cosine is below 0.85. `prompt(prediction)`
generates a Hinglish "do you want X or Y?" question. `parse_answer
(text, prediction)` maps the user's reply ("1", "open", "open_app")
back to the chosen intent.

The 0.05/0.85 thresholds are tuned conservatively — we'd rather ask
once and be sure than execute the wrong thing.

### `state_manager.py` — multi-turn state machine
Two parallel modes, mutually exclusive:
- **slot-fill** (`is_waiting_slot()`): asking the user for a missing
  required entity. The waiting intent + collected slots persist across
  turns. The user can cancel ("cancel", "ruko", "rok do", "rehne do",
  ...) to abort.
- **disambig** (`is_waiting_disambig()`): asking the user to choose
  between top-1 / top-2 candidates. The original utterance + prediction
  persist; the answer routes the original text to the chosen intent.

Both modes are aborted by `reset()`. The pipeline checks both modes
at the very top of each turn (steps 0a + 0b above).

### `executor.py` — the skill dispatcher
21 skill handlers. Each method takes a `slots` dict and returns a
response string. Side effects (subprocess.Popen for `open_app`, PIL
screenshot, JSON file write, etc.) happen here.

**Why all skills live in one file.** Single-user, single-machine; the
indirection of a plugin registry would not pay off yet. When the
catalog grows to 40+, splitting into per-skill modules with a registry
pattern is on the roadmap (Phase 2).

### `feedback.py` — SQLite logger + EMA bandit
Three tables (utterances, intent_thresholds, pending_patterns).
`log_utterance(...)` records every prediction outcome. `record_feedback
(utterance_id, label, correct_intent=None)` updates the row AND
drifts the threshold per the EMA rules. `queue_low_confidence(...)`
pushes a row into pending_patterns for the review CLI. `approve_pattern
(pending_id, intent)` promotes the pattern into intents.json.

This is the single piece of the brain stack with persistent state
across runs. Tests use a per-test tmp SQLite path so there's no
cross-test pollution.

### `llm_chat.py` — Ollama fallback
HTTP client for Ollama at `http://localhost:11434`. `is_available()`
pings `/api/tags` with a 1 s timeout. `reply(user_text, sentiment_label,
memory_facts, history)` POSTs to `/api/chat` with a system prompt
that:
- Tells phi3 it is AERIS, a personal Hinglish assistant.
- Lists the user's saved facts.
- Tells the model to match the user's language mix.
- Caps replies at 3 short sentences.

Default model is `phi3:mini` (3.8 B params, ~2.4 GB). The user can
edit `LLMConfig.model` to use llama3.2:3b or larger.

### `utterance_parser.py` — multi-command + subspan
Two pure functions used by `_process_segment`:

- `split_into_segments(text)`: splits on Hinglish/English connectors
  ("aur", "and", "phir", "then", commas) and reattaches verbs that
  apply across the split ("brave aur chrome open karo" →
  ["brave open karo", "chrome open karo"]).
- `find_best_interpretation(text, brain)`: tries the full segment plus
  up to 5 trimmed variants (filler-stripped, leading-particle-stripped,
  etc.), picks the one with highest brain confidence. Returns
  `(prediction, winning_span)`. The winning span is used only for
  intent classification — entity extraction still runs on the full
  segment so app names / queries living outside the trimmed span
  aren't lost.

This is what lets "ek kam karo notepad open karo" be recognized as
`open_app` with `app_name=notepad`. The "ek kam karo" prefix is filler
that confuses the brain; trimming it produces "notepad open karo"
which the brain handles correctly.

### `stt.py` / `tts.py` / `voice_engine.py` — audio I/O
- `stt.py`: `STT.listen()` blocks the current thread, returns a
  string. Tries Google SR (en-IN) first, falls back to Vosk if Vosk
  model is present at `data/models/vosk-model/`. Used by terminal mode.
- `tts.py`: `TTS.speak(text)` blocks the current thread until audio
  finishes. Tries Edge-TTS (`en-IN-NeerjaNeural` voice, network
  required), falls back to pyttsx3 (offline, OS-default voice). Audio
  goes through pygame.mixer.
- `voice_engine.py`: `ContinuousVoiceEngine` is the GUI's continuous
  listener. Manages STOPPED / ACTIVE / SLEEPING states. Inner capture
  loop runs on a daemon thread; events emit as Qt signals. Wake words:
  "jarvis wake up", "ok jarvis", "hey jarvis", "wake up", "activate".
  Sleep words: "jarvis sleep", "go to sleep", "sleep mode", "stand by".

---

## 8. Skills, intents, and the action executor

### The 21 intents

| # | Intent | Trigger examples | Required entity |
|---|---|---|---|
| 1 | `open_app` | `chrome kholo`, `launch brave` | `app_name` |
| 2 | `close_app` | `chrome band karo`, `close notepad` | `app_name` |
| 3 | `get_weather` | `mausam kya hai`, `what's the weather` | — |
| 4 | `play_music` | `music chala`, `song bajao` | — |
| 5 | `stop_music` | `music band karo`, `stop song` | — |
| 6 | `set_reminder` | `reminder set karo 5 baje` | `message`, `time` |
| 7 | `get_time` | `time kya hai`, `what time is it` | — |
| 8 | `take_screenshot` | `screenshot lo`, `screen capture karo` | — |
| 9 | `search_web` | `google karo machine learning` | `query` |
| 10 | `system_info` | `system info dikha`, `CPU kitna` | — |
| 11 | `volume_up` | `volume badhao`, `louder` | — |
| 12 | `volume_down` | `volume kam karo`, `quieter` | — |
| 13 | `volume_mute` | `mute karo`, `sound band karo` | — |
| 14 | `lock_screen` | `screen lock karo` | — |
| 15 | `shutdown_system` | `computer band karo`, `shutdown karo` | — |
| 16 | `calculate` | `5 + 3 kya hai`, `20 percent of 500` | `expression` |
| 17 | `create_note` | `note likho meeting at 3pm` | `content` |
| 18 | `greet` | `hello`, `namaste`, `hi jarvis` | — |
| 19 | `schedule_meeting` | `meeting Raj ke saath` | `person` |
| 20 | `play_youtube` | `youtube pe lofi chala` | `query` |
| 21 | `open_website` | `open github.com` | `url` |

### App gazetteer

25+ Windows apps recognized with Hinglish aliases. See
`data/entities.json` for the full mapping. Examples: `chrome` →
{chrome, google chrome, browser, web browser, google}; `vs code` →
{vs code, vscode, code editor, visual studio code}.

### How the executor implements skills

Most "skills" are 5-15 lines of subprocess.Popen, ctypes Windows API
calls, or PIL operations. The "real" parts of the integration (a
weather API, a real reminder engine, a calendar) are explicit roadmap
items (Phase 2). The current executor returns plausible-looking
strings for stubbed skills so the brain pipeline is fully testable
even when the underlying integrations are placeholders.

---

## 9. GUI architecture (jarvis_v31)

The current production UI lives in `ui/jarvis_v31/`. Layout:

```
┌────────────────────── TitleBar ──────────────────────────────┐
│  [AERIS]  state-pill  ─────────────────  [─][□][✕]            │
├──────────────────────────────────────────────────────────────┤
│          │                                │                   │
│ Floating │   ParticleField (background)   │  GlassChatPanel  │
│  Dock    │                                │   ┌───────────┐  │
│          │   ┌─────────────────────┐      │   │  Header   │  │
│  [Chat]  │   │                     │      │   │  pills    │  │
│  [Auto]  │   │    ReactorRings     │      │   ├───────────┤  │
│  [Sets]  │   │   460×460 animated  │      │   │ Auto chips│  │
│  [Brain] │   │   rings + sphere    │      │   ├───────────┤  │
│  [Mem]   │   │                     │      │   │  Messages │  │
│          │   └─────────────────────┘      │   │  scroll   │  │
│          │                                │   ├───────────┤  │
│          │   ReactorStateText [IDLE]      │   │   Input   │  │
│          │   StateSwitcher buttons        │   │  + Send   │  │
│          │                                │   └───────────┘  │
├──────────────────────────────────────────────────────────────┤
│              LogsBar (collapsible)                            │
│  SYS ▪ NLU ▪ MEM ──────────────────── [▼ collapse]           │
└──────────────────────────────────────────────────────────────┘
```

Window is 1440 × 900, frameless, draggable via the title bar.
Background is dark navy (`J.BG = #0a0e1a`). Accents are cyan, magenta,
purple, green, amber, red — defined in `ui/jarvis_v31/tokens.py`.

### Widgets and their roles

| Widget | What it does | File |
|---|---|---|
| `TitleBar` | App name, state pill, window buttons (min/max/close) | `title_bar.py` |
| `FloatingDock` | Left navigation; tabs for chat / automation / settings / brain / memory | `floating_dock.py` |
| `RightPanelStack` | Stacked panels on the right; chat panel is index 1 | `tab_panels.py` |
| `GlassChatPanel` | Conversation UI: header pills, automation chips, messages, input | `glass_chat_panel.py` |
| `ParticleField` | Drifting Lissajous particles in the center column background | `reactor.py` |
| `WiringSystem` | Background grid of "node cards" + traveling-packet animation | `wiring_system.py` |
| `ReactorRings` | 460×460 animated core (rings + 3D wireframe sphere) | `reactor.py` |
| `ReactorStateText` | "IDLE"/"PROCESSING"/etc. label below the reactor | `reactor.py` |
| `StateSwitcher` | Manual state-override row (debugging) | `reactor.py` |
| `LogsBar` | Bottom collapsible log feed (SYS/NLU/MEM/ACT/ERR/MIC/TTS) | `logs_bar.py` |

### Visual state machine

| State | Reactor color | Pill | What it means |
|---|---|---|---|
| IDLE | Cyan | LIVE | Waiting for input, mic may or may not be active |
| LISTENING | Green | LIVE + LISTENING | Voice engine is capturing |
| PROCESSING | Magenta | THINKING | Brain is running pipeline on user text |
| SPEAKING | Purple | GENERATING | TTS is playing the response |

State transitions are computed in `_refresh_display_state` from two
inputs: the current "system" state (driven by what the brain is
doing) and the voice engine state.

### Boot bubble

When the brain starts loading, a "SYSTEM BOOT" bubble appears in the
chat panel with a progress bar. It walks 4 % → 100 % across seven
phases driven by the chunked brain init (§11). Each phase posts a
log line to `LogsBar` and updates the bubble's progress + step list.

### Suggestion chips

`["Open Chrome", "Check Weather", "Play Music", "System Stats", "Schedule Meeting"]`
Shown only when the dock's "Automation" tab is active (so they don't
overlap the LIVE pill in the header). Clicking sends the chip text as
a chat message and snaps the dock back to "Chat".

---

## 10. Threading model

Three QThreads + the Qt main thread + at most one daemon thread for
voice capture.

```
┌───────────────────── Qt main thread ─────────────────────────┐
│  Builds the window, runs the event loop, owns all painting.   │
│  Receives queued signals from worker threads via Qt's signal- │
│  slot mechanism (thread-safe).                                │
└─┬───────────────────────────────────────────┬─────────────────┘
  │ request_brain_init / request_brain_proc   │ request_voice_*  / request_speak_*
  │                                           │
  ▼                                           ▼
┌─────────────── BrainWorker QThread ────────────────────────┐
│ Owns JarvisMainEngine. Runs setup_iter() chunk-by-chunk on │
│ initialize(). Runs process_text() per request. CPU/GIL-    │
│ heavy. Started with QThread.LowestPriority so the OS       │
│ scheduler always prefers the GUI thread when both want CPU.│
└────────────────────────────────────────────────────────────┘

┌─────────────── VoiceWorker QThread ────────────────────────┐
│ Owns ContinuousVoiceEngine. Spawns an inner *daemon Python │
│ thread* for the actual mic capture loop (PyAudio). The Qt  │
│ thread just routes start/stop signals. The daemon thread   │
│ emits captured() when speech is recognized.                │
└────────────────────────────────────────────────────────────┘

┌─────────────── SpeakWorker QThread ────────────────────────┐
│ Owns TTS. speak(text) is a one-shot slot — runs Edge-TTS   │
│ + pygame playback (or pyttsx3 fallback) and emits spoken().│
└────────────────────────────────────────────────────────────┘
```

**Why the brain runs on its own thread.** A single brain prediction is
~10-50 ms (intent classify + entity extract). A boot is 5-10 s
(sentence-transformers + spaCy load). Neither should ever happen on
the GUI thread, where they would freeze every animation, scroll, and
input event.

**Why voice has both a QThread AND a daemon thread.** The QThread is
for Qt signal/slot routing. The daemon thread is because PyAudio's
`recognize_listen` blocks for arbitrary durations and would not play
nicely with Qt's event loop. The daemon emits Qt signals (which are
thread-safe) when results are ready.

**Why TTS is on its own thread.** Edge-TTS is async; pyttsx3 blocks.
Either way, we don't want the brain thread to block on audio playback
(it should be ready to process the next utterance), and we don't want
the GUI thread to block at all.

---

## 11. Boot smoothness — keeping the GUI silky during heavy ML loads

This is the most-recently-iterated part of the project. The constraints
are real and contradictory; here is the full story.

### 11.1 The problem

A cold boot of `run_gui.py` does this on the user's machine:

1. ~3-5 s: `import torch` (must run before PyQt5 — see §11.4 below).
2. ~500 ms: PyQt5 + UI module imports.
3. ~50 ms: build the window + first paint.
4. ~5-10 s: brain stack init on the BrainWorker thread.

In a naive implementation, the user sees:
- Black screen for 3-5 s (torch loading, no GUI yet).
- Window appears but the boot bubble is stuck at 15 % for 5-10 s
  (brain init holding the GIL, GUI animations stuttering).

### 11.2 The fix — chunked init

`JarvisMainEngine.__init__` accepts `lazy=True`. In lazy mode, no
heavy work happens in the constructor; the caller drives `setup_iter()`,
a generator that yields `(log_type, msg, pct)` between **7 phases**:

| pct | phase | what happens |
|---|---|---|
| 4   | "Booting JarvisMainEngine…"          | first emit, before any chunk |
| 10  | "Loading sentence encoder"           | `JarvisBrain.load_encoder()` (slow) |
| 32  | "Loading intent index"               | `JarvisBrain.build_or_load_index()` |
| 50  | "Loading entity extractor + spaCy"   | `EntityExtractor(...)` |
| 68  | "Loading sentiment + memory"         | `SentimentAnalyzer`, `UserMemory`, `ConversationHistory`, `Disambiguator` |
| 82  | "Attaching feedback DB + LLM"        | `FeedbackStore`, `LLMChat` |
| 93  | "Wiring state machine + executor"    | `StateManager`, `ActionExecutor` |
| 100 | "All modules nominal"                | done |

Each yield is a Qt signal queued on the main thread. The boot bubble's
progress bar smoothly tweens toward the new percentage (1.2 px per 16 ms
tick), so the user perceives continuous motion instead of a frozen 15 %.

### 11.3 Thread priority + GIL

- `BrainWorker._brain_thread.start(QThread.LowestPriority)` — when the
  OS scheduler picks between the brain worker and the GUI thread, the
  GUI always wins.
- `sys.setswitchinterval(0.002)` in `run_gui.py` — Python's GIL
  switches to a different thread every 2 ms instead of the default
  5 ms. This gives the GUI more frequent windows to repaint while the
  brain is mid-import.

### 11.4 Animations paused during boot

`_wire_workers` in `JarvisV31Window` walks the heaviest paint widgets
(`ParticleField`, `ReactorRings`, `WiringSystem`) and stops every
active QTimer in their subtrees. Each timer's interval is saved on a
Qt dynamic property so it can be resumed exactly. On `_on_brain_ready`
(or `_on_brain_error`), the timers restart.

The boot bubble itself, the LIVE pill, and the chat panel keep
animating — those are user feedback, not background eye-candy.

### 11.5 Windows DLL ordering — torch before PyQt5

This is the single hardest constraint in the project.

**The bug.** On Windows, both PyQt5 and PyTorch ship their own MSVC
runtime DLLs (most notoriously `libiomp5md.dll`, but also `c10.dll`
and friends). If Qt's runtime is bound first, a later torch import —
**on any thread** — fails with:

> `WinError 1114: A dynamic link library (DLL) initialization
> routine failed`

while loading `c10.dll`.

**The fix.** In `run_gui.py`, `import torch` runs **before** any
PyQt5 import. The `from ui.jarvis_v31.main_window import launch` line
transitively pulls in PyQt5; torch must be in `sys.modules` before
that. The pre-import is wrapped in try/except so the GUI still launches
when torch is broken — the brain just reports a clean error in the
chat panel.

**`KMP_DUPLICATE_LIB_OK=TRUE`** is set in `os.environ` at the top of
`run_gui.py` to suppress the OpenMP duplicate-library check that
otherwise aborts on the same DLL collision.

We **cannot** show the Qt window before torch loads to give the user
faster feedback. The PyQt5 import has to come after torch. The
trade-off accepted (after several iterations) is:
- Print a stdout banner immediately so terminal-launched runs see
  `[AERIS] Booting...` within ~50 ms.
- Pay the 3-5 s torch import wait before the window appears.
- Make the post-window boot completely smooth (chunks + thread
  priority + paused animations).

### 11.6 Failure paths

- If torch import fails: warning to stderr, GUI launches anyway,
  BrainWorker errors when it tries to import `core.main_engine` (which
  pulls sentence-transformers → torch). The error surfaces in the
  chat panel and `LogsBar` with a remediation hint
  ("`pip install --upgrade --force-reinstall torch`").
- If spaCy is not installed: `EntityExtractor._init_spacy` catches
  the import error, logs an info message, sets `self.nlp = None`,
  and the NER layer is skipped at extract time.
- If Ollama is not running: `LLMChat.is_available()` returns False
  on a 1 s timeout; the brain falls back to "Ye samajh nahi paaya"
  and queues the utterance for review.

---

## 12. Data files — schemas and ground-truth assets

### `data/intents.json`

```json
{
  "open_app": {
    "patterns": [
      "open chrome", "chrome kholo", "launch browser",
      "...10-15 patterns total..."
    ],
    "required_entities": ["app_name"],
    "prompts": {
      "app_name": "Kaunsa app kholna hai? Batao."
    }
  }
}
```

`patterns` are the seed phrases that get embedded. `required_entities`
controls slot-filling; if any are missing after extraction, the
state machine asks the prompt and waits one turn. `prompts` is keyed
by entity name.

### `data/entities.json`

```json
{
  "app_name": {
    "chrome": ["chrome", "google chrome", "browser", "web browser", "google"],
    "vs code": ["vs code", "vscode", "visual studio code", "code editor"],
    "...25+ apps..."
  }
}
```

The first key in each pair is the canonical name passed to the executor.
Each value is the list of utterance-level aliases that should resolve
to that canonical name.

### `data/user_memory.json`

```json
{
  "facts": {
    "name":     {"value": "Shivang", "set_at": "2024-04-29T10:00:00", "source": "user_said"},
    "location": {"value": "Delhi",   "set_at": "...",                "source": "user_said"}
  },
  "notes": [
    {"text": "buy milk on tuesdays", "set_at": "..."}
  ],
  "preferences": {
    "language": "hinglish"
  }
}
```

### `data/models/intent_metadata.json`

```json
{
  "intents_hash": "abc123...md5 of intents.json...",
  "encoder_name": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "num_patterns": 250,
  "num_classes":  21,
  "built_at":     "2024-04-29T17:30:00"
}
```

The `intents_hash` is the cache invalidation key. If the current
intents.json hash differs, the index is rebuilt automatically.

### `data/feedback_log.sqlite` schema

```sql
-- Every utterance, with its predicted intent and outcome
CREATE TABLE utterances (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          TEXT NOT NULL,
    raw_text           TEXT NOT NULL,
    normalized_text    TEXT,
    predicted_intent   TEXT,
    confidence         REAL,
    top3_json          TEXT,           -- JSON array of [intent, score]
    sentiment_label    TEXT,
    sentiment_score    REAL,
    action_taken       TEXT,           -- executed | asked_disambig | asked_slot | chat_fallback | rejected
    user_feedback      TEXT,           -- accepted | corrected | cancelled | ignored
    correct_intent     TEXT,           -- only set on corrected
    reward             INTEGER         -- +1 / -1 / 0
);

-- Per-intent acceptance threshold (the bandit's policy)
CREATE TABLE intent_thresholds (
    intent             TEXT PRIMARY KEY,
    accept_threshold   REAL NOT NULL,
    sample_count       INTEGER NOT NULL DEFAULT 0,
    avg_reward         REAL NOT NULL DEFAULT 0,
    updated_at         TEXT NOT NULL
);

-- Low-confidence utterances queued for the review CLI
CREATE TABLE pending_patterns (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    utterance_id       INTEGER REFERENCES utterances(id),
    raw_text           TEXT NOT NULL,
    top3_json          TEXT NOT NULL,
    queued_at          TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'   -- pending | approved | rejected | skipped
);
```

---

## 13. Testing strategy

```bash
pytest tests/                    # full suite, ~3-4 min
pytest tests/test_pipeline.py    # end-to-end only, ~3 min
pytest tests/test_brain.py       # quick smoke test, ~30 s
```

| Test file | Coverage |
|---|---|
| `test_normalizer.py`        | Punctuation strip, whitespace, URL/math preservation |
| `test_sentiment.py`         | VADER + Hinglish lexicon, neutral band, fallback |
| `test_intent_classifier.py` | Encoder load, k-NN, cache rebuild on hash mismatch |
| `test_entity_extractor.py`  | All 4 layers (regex / gazetteer / NER / residual) |
| `test_memory.py`            | Pattern detection, fact storage, recall, JSON I/O |
| `test_disambiguator.py`     | Close-call detection, prompt gen, answer parsing |
| `test_conversation.py`      | Rolling buffer, OpenAI message format |
| `test_feedback.py`          | SQLite logger, EMA threshold drift, pending queue |
| `test_pipeline.py`          | End-to-end: input → intent → entities → execution |
| `test_stt.py`               | STT (mocked) |
| `test_tts.py`               | TTS (mocked) |
| `test_brain.py`             | JarvisBrain.predict end-to-end |

**Why no GUI tests.** PyQt is awkward to drive in CI. The brain layer
is a pure function (`process_text`) and is fully exercised by
`test_pipeline.py`. GUI changes are validated by running `run_gui.py`
and `_jv31_smoke.py` (a standalone visual smoke launcher).

**Test fixtures.** `tests/conftest.py` defines `tmp_memory_path` and
`tmp_feedback_db` fixtures that point at per-test temp files, so the
real `data/user_memory.json` and `data/feedback_log.sqlite` are never
touched by tests.

---

## 14. Dependencies and setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm    # optional: nicer NER

# Optional: Ollama for chit-chat fallback
ollama pull phi3:mini
```

`requirements.txt` (categorized):

```
# Audio I/O
SpeechRecognition vosk pyaudio edge-tts pyttsx3 pygame

# NLP / brain
sentence-transformers scikit-learn spacy rapidfuzz nltk vaderSentiment

# LLM chit-chat
requests

# UI + system
PyQt5 psutil keyboard pyautogui

# Gesture (optional sandbox)
opencv-python mediapipe

# Misc
pyyaml

# Dev / test
pytest
```

**Windows-specific gotchas.**
- `KMP_DUPLICATE_LIB_OK=TRUE` (set automatically by `run_gui.py`) is
  required because torch and Qt both bundle `libiomp5md.dll`.
- `pyaudio` may need `pipwin install pyaudio` instead of plain pip on
  some Windows + Python combos.
- `pyttsx3` uses SAPI5 on Windows (so the offline TTS voice depends
  on the system's installed voices).

---

## 15. Common workflows

### Adding a new intent

1. Open `data/intents.json` and add an entry:
   ```json
   "lock_workstation": {
     "patterns": ["lock my pc", "pc lock kar do", "windows lock", "..."],
     "required_entities": [],
     "prompts": {}
   }
   ```
2. (If needed) Add a handler in `core/executor.py`:
   ```python
   def lock_workstation(self, slots):
       ctypes.windll.user32.LockWorkStation()
       return "Done sir."
   ```
3. (If needed) Add an entry in the dispatch table in
   `ActionExecutor.execute(...)`.
4. Restart AERIS — the index rebuilds automatically because
   `intents.json` changed and the cached MD5 no longer matches.
5. Test from the REPL: `python main.py --text` then `pc lock kar do`.

### Reviewing pending patterns

```bash
python -m core.review_cli
```

Walks every row in `pending_patterns` where `status = 'pending'`. For
each, you see the raw text + top-3 candidates and choose:
- `1` / `2` / `3` — approve as that candidate intent.
- `<intent_name>` — approve as a custom intent name.
- `s` — skip (re-asked next session).
- `r` — reject (discarded, never re-surfaced).
- `l` — list all pending.
- `q` — quit.

Approved patterns are appended to `intents.json`. Restart AERIS to
pick them up.

### Debugging an utterance

```bash
python main.py --text --verbose
```

The `--verbose` flag turns on INFO-level logging from every core
module. You'll see:
- `[Brain] Initialising...` → encoder load progress
- `[IntentClassifier] Loading cached index.`
- Per-utterance: predicted intent, confidence, top3
- Per-utterance: extracted entities, action taken, executor result

You can also poke at the feedback log directly:

```bash
sqlite3 data/feedback_log.sqlite "SELECT * FROM utterances ORDER BY id DESC LIMIT 10"
sqlite3 data/feedback_log.sqlite "SELECT * FROM intent_thresholds ORDER BY updated_at DESC"
```

### Rebuilding the intent index manually

```python
from core.intent_classifier import IntentClassifier
clf = IntentClassifier(intents_path="data/intents.json", models_dir="data/models")
clf.rebuild()
```

This is rarely needed because the cache auto-invalidates on hash
change. Use it if you've corrupted the pickle or want a fresh build.

### Switching the LLM model

Edit `core/llm_chat.py`:

```python
@dataclass
class LLMConfig:
    model: str = "llama3.2:3b"   # or any model you've pulled with `ollama pull`
```

Restart. The brain's chit-chat fallback now uses the new model.

---

## 16. Roadmap

(Preserved from earlier planning — adjust dates as the calendar moves.)

**Phase 1 — Audio hardening.** Replace Google SR with `faster-whisper`
(local Whisper) and Edge-TTS with Piper (local neural TTS). Add
hotword detection via openwakeword. Goal: fully offline, sub-1 s
speech-to-audio response latency.

**Phase 2 — Skill expansion.** Replace stub skills with real
integrations: OpenWeatherMap, Windows Task Scheduler reminders,
Google Calendar / Outlook COM, Outlook / Gmail API, file search via
Windows Search index. Grow to 40+ intents.

**Phase 3 — Intelligence upgrade.** FAISS HNSW for 10K+ pattern scale.
Multilingual sentiment via XLM-RoBERTa. Conversation-aware entity
linking ("usse band karo" resolves "usse" from history). Multi-turn
skills (3-step set_reminder → confirm flow).

**Phase 4 — GUI polish.** First-run onboarding wizard, full settings
panel + persistence, system tray mode, dark/light theme toggle,
desktop notifications, multi-monitor handling.

**Phase 5 — Learning + personalization.** Auto-approval of high-
confidence pending patterns. Active learning queue surfaced in the
GUI. App-launch frequency model. Conversation summarization →
memory.

**Phase 6 — Platform expansion.** PyInstaller / Nuitka one-exe
installer, auto-update, REST API server (`localhost:5000`), Chrome
/ Edge extension, Android companion app talking to the local REST API.

---

## 17. Glossary

| Term | Meaning in this project |
|---|---|
| **AERIS** | Adaptive Emotional Reasoning & Intelligent System — the project name |
| **JARVIS v3.x** | Code name for the GUI iteration (v3.1 currently active) |
| **Brain stack** | Everything in `core/` that runs in `JarvisMainEngine.process_text()` |
| **Intent** | A class of user commands (e.g., `open_app`, `get_weather`) |
| **Pattern** | A labeled example utterance for an intent (one of N per intent in intents.json) |
| **Slot** | A required entity for an intent (e.g., `app_name` for `open_app`) |
| **k-NN** | k-nearest-neighbors over sentence embeddings — the routing algorithm |
| **MiniLM** | The frozen 384-dim multilingual encoder we use |
| **Disambiguator** | The "should I ask the user?" decision logic for close-call predictions |
| **Bandit** | The per-intent EMA threshold learner — formally a contextual bandit |
| **Top-3** | The three highest-scoring intents from the k-NN vote |
| **Threshold** | Per-intent acceptance floor: confidence below this routes to LLM fallback |
| **Hinglish** | Mixed Hindi-English written in Roman script ("chrome kholo bhai") |
| **Gazetteer** | A static dictionary of canonical names + aliases (we have one for apps) |
| **Slot-fill** | Multi-turn flow where AERIS asks for missing entities one at a time |
| **Boot bubble** | The "SYSTEM BOOT" chat bubble that shows brain init progress |
| **BrainWorker / VoiceWorker / SpeakWorker** | The three QThreads (see §10) |
| **WinError 1114** | The Windows DLL collision that forces torch-before-Qt import order |
| **GIL** | Python's global interpreter lock — only one thread runs Python bytecode at a time |
| **`lazy=True`** | The flag that puts `JarvisMainEngine.__init__` into chunked-init mode |
| **`setup_iter()`** | The generator that yields progress between brain init phases |

---

*End of README. If you are an LLM reading this for context, the
single-most-important things to remember are: (1) this is a single-
user Windows project where simplicity beats scalability, (2) the
"brain" is a retrieval system, not a trained classifier, (3) the
threading and DLL ordering rules in §10–§11 are load-bearing — do
not refactor them without understanding why they're shaped that way.*
