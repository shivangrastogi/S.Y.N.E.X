# JARVIS / AERIS BRAIN — IMPLEMENTATION PLAN

> Living document. Every checkpoint is self-contained: goal, files touched,
> code-level guidance, definition of done. Future sessions resume by reading
> `BRAIN_CHECKPOINTS.md` first, then jumping to the relevant checkpoint here.

---

## 0. North Star

A **fully-local, Hinglish-native** personal assistant with:

1. **Strong intent routing** — multilingual semantic encoder + k-NN over labelled patterns. Adds new patterns instantly with no retraining.
2. **Layered entity extraction** — regex + gazetteer + NER + residual span. Almost no follow-up prompts needed.
3. **Sentiment awareness** — Jarvis adapts tone when user is frustrated, excited, or neutral.
4. **Long-term user memory** — persistent facts ("my name is Shivang", "I work at X", "remind me on weekdays"). Survives restarts.
5. **Short-term conversation context** — last N turns inform follow-ups and pronoun resolution.
6. **Chit-chat fallback via local LLM** (Ollama + Phi-3 or Llama-3.2) — anything not routed to a skill becomes a conversational reply.
7. **Reward-shaped continual learning** — every utterance + outcome logged; per-intent confidence thresholds learn from acceptance rate; low-confidence utterances queued for user labelling.
8. **Disambiguation** — when top-1 and top-2 are close, ask "did you mean A or B?".
9. **Production-grade STT/TTS** (deferred to last checkpoint) — `faster-whisper` (hi+en) + Piper / Coqui / Edge-TTS hybrid.

This document is the contract. Code lives in the actual `core/*.py` files as each checkpoint completes.

---

## 1. Architecture Diagram

```
┌──────────────────────── Audio In ────────────────────────┐
│  Mic → STT (Whisper local / Google fallback) → text       │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────── Brain Pipeline ─────────────────────┐
│                                                            │
│  text                                                       │
│    │                                                        │
│    ├─► normalizer (light: lowercase, strip punct only)     │
│    │                                                        │
│    ├─► sentiment.classify(text)  ──► (label, score)        │
│    │                                                        │
│    ├─► memory.detect_memory_command(text)                  │
│    │      │                                                 │
│    │      ├─ matched ─► save fact, return ack              │
│    │      └─ no match ─► continue                          │
│    │                                                        │
│    ├─► intent_classifier.predict(text)                     │
│    │      → list of {intent, confidence, distance}         │
│    │                                                        │
│    ├─► If top-1 ≥ accept_threshold[intent]:                │
│    │      entity_extractor.extract(text, intent)           │
│    │      state_manager.process(intent, entities)          │
│    │      executor.execute(intent, slots) ─► response      │
│    │                                                        │
│    ├─► Elif top-1 close to top-2 within 0.05:              │
│    │      disambiguator.ask("Did you mean A or B?")        │
│    │                                                        │
│    └─► Else (low confidence):                              │
│           conversation.append(user=text)                   │
│           feedback.log_low_confidence(text, top3)          │
│           llm_chat.reply(text, conversation, memory)       │
│                                                            │
│  Every step logged to feedback.sqlite for later review.    │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────── Audio Out ────────────────────────┐
│  response → TTS (Piper local / Edge-TTS) → speaker        │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Module Map

| File | Status | Purpose |
|------|--------|---------|
| `core/brain.py` | NEW (C1) | Orchestrator. Owns the pipeline above. Replaces `neural_engine.py`. |
| `core/intent_classifier.py` | NEW (C1) | Multilingual encoder + k-NN over labelled patterns. Replaces Keras dense head + `trainer.py`. |
| `core/normalizer.py` | REPLACE (C1) | Strip to lowercase + punctuation only. Translation map deleted. |
| `core/entity_extractor.py` | NEW (C2) | Regex + gazetteer + spaCy NER + residual span. |
| `core/sentiment.py` | NEW (C3) | Sentiment label + score. VADER for v1, multilingual upgrade noted. |
| `core/memory.py` | NEW (C4) | Persistent user facts. JSON-backed; key/value with provenance. |
| `core/conversation.py` | NEW (C5) | Rolling window of last N turns. |
| `core/llm_chat.py` | NEW (C6) | Ollama HTTP client; chat with system prompt + memory + recent turns. |
| `core/feedback.py` | NEW (C7) | SQLite log; reward update for per-intent thresholds; pending-pattern queue. |
| `core/disambiguator.py` | NEW (C8) | Top-K disambiguation prompt + answer routing. |
| `core/state_manager.py` | KEEP (minor edits in C9) | Slot-filling state machine. Add `cancel` + timeout. |
| `core/executor.py` | EXTEND (C10) | Add `remember_fact`, `recall_fact`, `chat_reply`, `cancel` actions. |
| `core/main_engine.py` | REWIRE (C9) | Glue. Uses `JarvisBrain` instead of old `AdvancedNeuralEngine`. |
| `core/intent_engine.py` | KEEP | Fuzzy fallback (rarely hit once k-NN is in). |
| `core/stt.py` | DEFERRED (C12) | Swap to `faster-whisper`. |
| `core/tts.py` | DEFERRED (C12) | Add Piper/Coqui local backend. |
| `core/neural_engine.py` | DELETE (C1) | Superseded by `brain.py` + `intent_classifier.py`. |
| `core/trainer.py` | DELETE (C1) | k-NN needs no training step. |
| `data/intents.json` | KEEP | Same shape, k-NN reads it. |
| `data/entities.json` | KEEP | Used by entity_extractor and gazetteer. |
| `data/user_memory.json` | NEW (C4) | Long-term facts. |
| `data/feedback_log.sqlite` | NEW (C7) | Continual learning store. |
| `data/pending_patterns.jsonl` | NEW (C7) | Low-conf utterances awaiting review. |
| `data/models/intent_index.pkl` | NEW (C1) | Cached k-NN index + label array + intents-hash. |
| `data/models/intent_metadata.json` | UPDATED (C1) | Schema: hash, num_patterns, num_classes, encoder_name, built_at. |
| `data/models/jarvis_advanced_brain.h5` | DELETE (C1) | Old Keras model. |
| `data/models/label_encoder.pkl` | DELETE (C1) | Old sklearn label encoder. |
| `requirements.txt` | UPDATED per checkpoint | See `Dependencies` section. |

---

## 3. Dependencies

Final `requirements.txt` after all checkpoints (current ones marked with status):

```
# Audio I/O
SpeechRecognition          # STT online wrapper (kept for fallback)
faster-whisper             # STT local                          [C12]
vosk                       # STT offline fallback               [keep]
pyaudio                    # mic input
edge-tts                   # TTS online (best quality Hindi)
piper-tts                  # TTS local                          [C12]
pyttsx3                    # TTS offline final fallback
pygame                     # audio playback

# NLP / Brain
sentence-transformers      # multilingual encoder               [C1]
scikit-learn               # k-NN, label arrays                 [C1]
spacy                      # NER + tokenisation                 [C2]
vaderSentiment             # sentiment v1                       [C3]
# transformers             # multilingual sentiment upgrade     [C3 optional]

# LLM
requests                   # Ollama HTTP                        [C6]

# UI / system
PyQt5
psutil
keyboard
pyautogui
opencv-python              # gesture (existing utils)
mediapipe                  # gesture (existing utils)

# Utility
rapidfuzz                  # fuzzy fallback
pyyaml
nltk

# REMOVED:
# tensorflow               # replaced by k-NN
```

After Phase A (C1), run:
```bash
pip uninstall tensorflow
pip install --upgrade sentence-transformers scikit-learn
```

After C2:
```bash
pip install spacy
python -m spacy download en_core_web_sm
```

After C3:
```bash
pip install vaderSentiment
```

After C6 (assumes Ollama installed separately):
```bash
ollama pull phi3:mini      # ~2.4 GB; or
ollama pull llama3.2:3b    # ~2.0 GB
```

After C12:
```bash
pip install faster-whisper piper-tts
```

---

## 4. Checkpoint Catalog

Each checkpoint = one resumable unit of work. Order matters when noted; otherwise independent.

---

### **C1 — Multilingual Brain Core** *(Phase A, foundational)*

**Goal**
Replace the English-only MiniLM + Keras dense head with a **multilingual sentence encoder + k-NN classifier**. Delete the manual Hinglish translation map. Cache the k-NN index keyed by `intents.json` hash so rebuild is instant.

**Why**
- Multilingual encoder eliminates the normalizer translation hack.
- k-NN can grow with one append; no retraining when patterns are added.
- Top-K naturally exposes alternatives for disambiguation (C8).
- Cannot overfit by construction.

**Files**
- CREATE `core/brain.py`
- CREATE `core/intent_classifier.py`
- REPLACE `core/normalizer.py` (minimal version)
- UPDATE `core/main_engine.py` (import + use new brain class)
- UPDATE `requirements.txt`
- DELETE `core/neural_engine.py`
- DELETE `core/trainer.py`
- DELETE `data/models/jarvis_advanced_brain.h5` (after first run rebuilds new index)
- DELETE `data/models/label_encoder.pkl`

**Encoder choice**
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — 384 dims, 50+ languages including Hindi, ~120 MB, ~30 ms encode on CPU.

**k-NN choice**
`sklearn.neighbors.NearestNeighbors(n_neighbors=5, metric="cosine")`. No external FAISS dependency. Sub-millisecond lookup for our pattern volume.

**Voting rule**
For top-K nearest patterns, accumulate `weight = 1 - distance` per intent label. Intent with max accumulated weight wins. `confidence = winner_weight / sum_all_weights`. Returns `[(intent, confidence, top3_alternatives)]`.

**Index cache**
Saved as `data/models/intent_index.pkl` containing `{embeddings: np.ndarray, labels: list[str], encoder_name: str, intents_hash: str}`. On boot, if hash matches current `intents.json`, load from disk; else rebuild (takes 5–10 s for 300 patterns, 30 s for 3000).

**Public API for `JarvisBrain`** (used by main_engine):
```python
class JarvisBrain:
    def __init__(self): ...
    def predict(self, text: str) -> Prediction:
        """Returns Prediction(intent, confidence, top3) or
        Prediction(None, 0.0, top3) when below dynamic threshold."""

@dataclass
class Prediction:
    intent: Optional[str]
    confidence: float
    top3: List[Tuple[str, float]]   # [(intent, confidence), ...]
    raw_text: str
    normalized_text: str
```

**Definition of Done**
- Running `python -m core.brain` from project root prints predictions for 6 test Hinglish sentences with confidence ≥ 0.5 each.
- Adding a new pattern to `intents.json` and re-running picks up the new pattern within 10 s without manual training.
- `from core.brain import JarvisBrain` succeeds; `main_engine.py` runs to "AERIS systems online" without import errors.
- Old files (`neural_engine.py`, `trainer.py`, `*.h5`, `label_encoder.pkl`) gone.

---

### **C2 — Layered Entity Extractor**

**Goal**
Extract `app_name`, `time`, `date`, `number`, `url`, `query`, `expression`, `content`, `person` from the raw utterance **before** slot-filling kicks in.

**Files**
- CREATE `core/entity_extractor.py`
- UPDATE `core/main_engine.py` to call extractor with intent context
- UPDATE `core/state_manager.py` so `process_prediction` skips slots that are already filled

**Layers (in order; first hit wins per slot)**
1. **Regex** for `time` (`\b(\d{1,2})(:\d{2})?\s*(am|pm|baje)\b`, plus Hinglish forms `subah`, `shaam`), `url` (URL regex), `number`, `expression` (math chars).
2. **Gazetteer** for `app_name` from `entities.json` (lifted from current main_engine implementation).
3. **spaCy NER** (`en_core_web_sm`) for `PERSON`, `ORG`, `DATE`, `TIME`, `GPE`. Map `PERSON` → `person` slot, `DATE/TIME` → `time` slot if regex missed.
4. **Residual span**: per intent, drop known trigger words and assign the remainder to the canonical free-form slot for that intent (`query` for search/youtube, `content` for note, `expression` for calculate). Defined in `intent_residual_slot` map inside extractor.

**Public API**:
```python
class EntityExtractor:
    def __init__(self, entities_path, intents_path): ...
    def extract(self, text: str, intent: str) -> dict[str, str]:
        """Returns {slot_name: extracted_value}. Only includes slots
        relevant to the intent's required_entities."""
```

**Definition of Done**
- `"YouTube pe Arijit ka latest gaana chala do"` → `{query: "Arijit ka latest gaana"}`
- `"5 baje shaam ko milk lena yaad dilana"` → `{message: "milk lena", time: "5 baje shaam ko"}`
- `"chrome kholo"` → `{app_name: "chrome"}`
- `"https://github.com kholo"` → `{url: "https://github.com"}`

---

### **C3 — Sentiment Analysis**

**Goal**
Tag each utterance with sentiment (`positive | neutral | negative`) + score in `[-1, 1]`. Brain passes this to LLM and TTS for tone adaptation.

**Files**
- CREATE `core/sentiment.py`

**Implementation**
- v1: VADER (`vaderSentiment.vaderSentiment.SentimentIntensityAnalyzer`). English-only but works decently on Romanized Hinglish.
- v2 (documented, optional): swap to `cardiffnlp/twitter-xlm-roberta-base-sentiment` via `transformers` for true multilingual.

**Public API**:
```python
class SentimentAnalyzer:
    def classify(self, text: str) -> Sentiment

@dataclass
class Sentiment:
    label: str   # "positive" | "neutral" | "negative"
    score: float # -1.0 to 1.0
```

**Brain wire-up**
- LLM-fallback prompt includes `"User sentiment: {label}"` so chit-chat replies are tonally appropriate.
- (Optional later) TTS rate adjusted: faster for excited, slower for sad.

**Definition of Done**
- `"thank you yaar bahut accha kaam kiya"` → positive, score > 0.3
- `"yeh kya bakwaas hai"` → negative, score < -0.2
- `"chrome kholo"` → neutral, |score| < 0.2

---

### **C4 — User Memory (long-term facts)**

**Goal**
Persistent key/value store of things the user told Jarvis about themselves. Survives restart. Detects natural-language "remember" patterns and writes automatically.

**Files**
- CREATE `core/memory.py`
- CREATE `data/user_memory.json` (created on first write)

**Storage shape** (`data/user_memory.json`):
```json
{
  "facts": {
    "name": {"value": "Shivang", "set_at": "2026-04-25T15:30:00", "source": "user_said"},
    "favorite_browser": {"value": "chrome", "set_at": "...", "source": "inferred"}
  },
  "preferences": {
    "language": "hinglish",
    "wake_word": "jarvis"
  }
}
```

**Detection patterns** (regex with capture groups, returned as `(slot, value)` for `set_fact`):
- `(?:my name is|mera naam|main hoon|i am)\s+([A-Z][a-z]+)` → `name`
- `(?:i live in|main rehta hoon|i'm from)\s+(.+)` → `location`
- `(?:i work at|main kaam karta hoon at|i'm employed at)\s+(.+)` → `employer`
- `(?:remember (?:that|ki))\s+(.+)` → free-form, stored under `notes` list
- `(?:my (?:favorite|favourite|fav)\s+(\w+) is)\s+(.+)` → `favorite_<word>`

**Public API**:
```python
class UserMemory:
    def __init__(self, path: str): ...
    def detect_and_store(self, text: str) -> Optional[str]:
        """If text contains a memory-setting pattern, save it and return
        an acknowledgement string. Else None."""
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str, source: str = "user_said"): ...
    def all_facts(self) -> dict[str, str]:
        """Flat {key: value} for prompt injection."""
```

**Brain wire-up**
- Pipeline calls `memory.detect_and_store(text)` BEFORE intent classification. If hit, return ack and skip the rest. (Memory commands are a higher-priority "intent" than skill calls.)
- Memory facts injected into LLM system prompt for chit-chat continuity.

**Definition of Done**
- `"hello my name is shivang"` → `data/user_memory.json` contains `name: "Shivang"`; ack returned: *"Got it, Shivang. Nice to meet you."*
- After restart, `"what's my name"` → LLM (or a `recall_fact` skill) answers *"Your name is Shivang."*

---

### **C5 — Conversation Context (short-term)**

**Goal**
Rolling window of last N turns (user+assistant) so chit-chat and follow-ups have context.

**Files**
- CREATE `core/conversation.py`

**Public API**:
```python
class ConversationHistory:
    def __init__(self, max_turns: int = 8): ...
    def add_user(self, text: str, sentiment: Sentiment): ...
    def add_assistant(self, text: str): ...
    def as_messages(self) -> list[dict]:
        """Returns [{role: 'user'|'assistant', content: str}, ...]
        formatted for LLM consumption."""
    def clear(self): ...
```

**Brain wire-up**
- Every utterance/response added.
- LLM call passes `as_messages()` as conversation history.
- (Optional) Used to resolve pronouns: "close it" → "it" = last opened app from history.

**Definition of Done**
- After 3 turns, `as_messages()` returns 6 entries (3 user + 3 assistant), oldest dropped if > 8 total.

---

### **C6 — Chit-chat via Local LLM (Ollama)**

**Goal**
For utterances the intent classifier cannot route (low confidence, no skill match), pass to a local LLM with system prompt + user memory + conversation history. Response goes through TTS like any other reply.

**Files**
- CREATE `core/llm_chat.py`

**Ollama prerequisites**
User installs Ollama (`https://ollama.com`) and pulls `phi3:mini` or `llama3.2:3b`. Document in plan; do not auto-install.

**System prompt template**:
```
You are AERIS, a personal Hinglish assistant for {user_name}.
Personality: warm, witty, concise. Reply in the same language mix as the user (English / Hindi / Hinglish).
You have skills (open apps, weather, time, etc.) but right now you're chatting freely.
Known facts about user:
{user_facts}
Current user sentiment: {sentiment_label}
Keep replies under 3 sentences unless asked for detail.
```

**Public API**:
```python
class LLMChat:
    def __init__(self, model: str = "phi3:mini",
                 host: str = "http://localhost:11434"): ...
    def is_available(self) -> bool:
        """Pings Ollama. Returns False if not running."""
    def reply(self, user_text: str, sentiment: Sentiment,
              memory_facts: dict, history: list[dict]) -> str: ...
```

**Brain wire-up**
- When `intent_classifier.predict()` returns `intent=None`:
  - If `LLMChat.is_available()`: route to chit-chat.
  - Else: friendly fallback message + log to `pending_patterns.jsonl`.
- All chit-chat responses still appended to conversation history.

**Definition of Done**
- With Ollama running and `phi3:mini` pulled, sending `"what's the meaning of life"` returns a multi-word LLM-generated string in <3 s on a typical laptop.
- Without Ollama, brain returns *"Ye samajh nahi paaya, sir. Aap clear karenge?"* and logs the utterance to `pending_patterns.jsonl`.

---

### **C7 — Reward-Shaped Continual Learning** *(your "RL" piece, done right)*

**Goal**
Every utterance + outcome logged. Per-intent **acceptance rate** drives a learned **confidence threshold** per intent (the "policy"). Low-confidence utterances queued for review; approved ones get added to `intents.json` and the k-NN index instantly.

**Files**
- CREATE `core/feedback.py`
- CREATE `data/feedback_log.sqlite` (auto-created on first write)
- CREATE `data/pending_patterns.jsonl`
- CREATE `core/review_cli.py` — interactive labelling tool

**Why this is the right RL framing**
- **State**: the utterance + predicted intent + confidence
- **Action**: one of {execute, ask_disambig, ask_chat_fallback}
- **Reward**: +1 if user accepted, -1 if user corrected/cancelled, 0 if ignored
- **Policy**: per-intent acceptance threshold, updated by exponential moving average of reward
- **Exploration**: when threshold is uncertain (few samples), bias toward asking before executing

This is a contextual bandit, not full RL, which is exactly the right tool — you don't have a sequential decision problem, you have a per-utterance accept/reject one.

**SQLite schema**:
```sql
CREATE TABLE utterances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT,
    predicted_intent TEXT,
    confidence REAL,
    top3_json TEXT,
    sentiment_label TEXT,
    sentiment_score REAL,
    action_taken TEXT,           -- 'executed' | 'asked_disambig' | 'asked_slot' | 'chat_fallback' | 'rejected'
    user_feedback TEXT,          -- 'accepted' | 'corrected' | 'cancelled' | 'ignored' | NULL
    correct_intent TEXT,         -- set when user_feedback = 'corrected'
    reward INTEGER               -- +1 / 0 / -1
);

CREATE TABLE intent_thresholds (
    intent TEXT PRIMARY KEY,
    accept_threshold REAL NOT NULL DEFAULT 0.65,
    sample_count INTEGER DEFAULT 0,
    avg_reward REAL DEFAULT 0.0,
    updated_at TEXT
);
```

**Threshold update rule (exponential moving average)**:
```
α = 0.1
new_avg_reward = (1 - α) * old_avg_reward + α * latest_reward
sample_count += 1

if avg_reward < 0:
    accept_threshold += 0.02  # more cautious
elif avg_reward > 0.5 and sample_count > 20:
    accept_threshold = max(0.55, accept_threshold - 0.01)  # more confident
```

Result: an intent that keeps getting accepted will have its threshold drift down (faster acceptance); an intent that keeps getting rejected will rise (more disambiguation prompts).

**Public API**:
```python
class FeedbackStore:
    def __init__(self, db_path: str): ...
    def log_utterance(self, ...) -> int: ...   # returns row id
    def record_feedback(self, utterance_id: int,
                        feedback: str, correct_intent: str = None): ...
    def get_threshold(self, intent: str) -> float: ...
    def update_threshold(self, intent: str, reward: int): ...
    def queue_low_confidence(self, text: str, top3: list, prediction_id: int): ...
    def pending_patterns(self) -> list[dict]: ...
    def approve_pattern(self, text: str, intent: str): ...
```

**Review CLI** (`python -m core.review_cli`):
- Walks each pending pattern.
- Shows top-3 predictions.
- Asks user: number for correct intent / "n" for new intent / "s" for skip / "d" for delete.
- Approved patterns appended to `intents.json`; brain hot-rebuilds k-NN index next boot (or on `:reload` command).

**Brain wire-up**
- Brain reads per-intent threshold at predict time instead of hard-coded 0.65.
- After every executor return, brain calls `feedback.record_feedback(...)`. Default `accepted` if no negative signal; user can say "galat" / "wrong" / "cancel" within 10 s to flip to `corrected`.
- Cancel intent (added in C9) sets the feedback to `cancelled` and reward to -1.

**Definition of Done**
- After 10 successful "chrome kholo" → executions, `intent_thresholds.accept_threshold` for `open_app` has drifted down from 0.65.
- After saying "wrong" twice in a row to a `play_music` execution, threshold drifts up.
- `python -m core.review_cli` shows the pending list and lets you approve patterns interactively.

---

### **C8 — Disambiguation**

**Goal**
When top-1 and top-2 confidences are within 0.05 of each other, ask the user instead of guessing.

**Files**
- CREATE `core/disambiguator.py`
- UPDATE `core/state_manager.py` to handle a new "awaiting_disambig" state
- UPDATE `core/main_engine.py` to detect and route close calls

**Logic**:
```python
top1, top2 = predictions[0], predictions[1]
if top1.confidence - top2.confidence < 0.05 and top1.confidence < 0.85:
    return ask_disambig([top1, top2])
```

**Prompt format**:
> *"Aap '{intent_human_name(top1)}' karna chahte hain ya '{intent_human_name(top2)}'? Ek bolo."*

User says "first" / "pehla" / "1" / `<intent_name>` → state_manager advances. Default to top-1 after 8 s timeout.

**Definition of Done**
- For an intentionally ambiguous input, brain prompts disambig. After user picks, normal flow resumes. Both branches log the disambig in feedback (the picked one is +1 reward).

---

### **C9 — Main Engine Rewire**

**Goal**
Stitch all modules into the new pipeline shown in §1.

**Files**
- UPDATE `core/main_engine.py` — full rewrite of the `run()` loop
- UPDATE `core/state_manager.py` — add `cancel`, `awaiting_disambig`, slot timeout

**`MainEngine.run()` shape (pseudocode)**:
```python
while self.is_running:
    text = self.stt.listen()
    if not text: continue

    # 0. State first — slot-filling or disambiguation in progress?
    if self.state.is_waiting_slot():
        result = self.state.handle_slot_answer(text)
        self._handle_result(result); continue
    if self.state.is_waiting_disambig():
        chosen = self.state.handle_disambig_answer(text)
        if chosen: self._execute(chosen, ...); continue

    # 1. Memory commands have highest priority
    ack = self.memory.detect_and_store(text)
    if ack: self._respond(ack); continue

    # 2. Cancel keyword
    if self._is_cancel(text):
        self.state.reset(); self._respond("Theek hai, cancel kar diya."); continue

    # 3. Sentiment
    sentiment = self.sentiment.classify(text)

    # 4. Brain
    pred = self.brain.predict(text)

    # 5. Route
    if pred.intent and pred.confidence >= self.feedback.get_threshold(pred.intent):
        if self.disambiguator.is_close_call(pred):
            self._respond(self.disambiguator.prompt(pred))
            self.state.set_awaiting_disambig(pred); continue

        entities = self.entity_extractor.extract(text, pred.intent)
        result = self.state.process_prediction(pred, entities)
        utterance_id = self.feedback.log_utterance(text, pred, sentiment, action="executed")
        self._handle_result(result, utterance_id)
    else:
        # 6. LLM chit-chat fallback
        utterance_id = self.feedback.log_utterance(text, pred, sentiment, action="chat_fallback")
        if self.llm.is_available():
            reply = self.llm.reply(text, sentiment, self.memory.all_facts(), self.history.as_messages())
            self._respond(reply)
            self.history.add_assistant(reply)
        else:
            self._respond("Ye samajh nahi paaya. Aap clear karenge?")
            self.feedback.queue_low_confidence(text, pred.top3, utterance_id)

    self.history.add_user(text, sentiment)
```

**Definition of Done**
- All previous skills still work end-to-end.
- New paths (memory, sentiment, chit-chat, disambig, cancel) all exercised by manual smoke test.

---

### **C10 — Executor Extensions**

**Goal**
Add new built-in actions for memory recall and explicit chat invocation.

**Files**
- UPDATE `core/executor.py` — add `recall_fact`, `chat_reply`, `cancel`, `set_preference`
- UPDATE `data/intents.json` — add new intents:
  - `recall_fact` patterns: "what's my name", "mera naam kya hai", "tumne mujhe yaad rakha tha kya"
  - `set_preference` patterns: "tone friendly karo", "louder bolo always"
  - `cancel` patterns: "cancel", "ruko", "rok do", "nahi karna"

**Definition of Done**
- "what's my name" returns the stored name; if not stored, returns *"Aapne mujhe naam batayaa nahi hai abhi tak."*

---

### **C11 — Tests**

**Goal**
Smoke + unit tests covering the new pipeline.

**Files**
- UPDATE `tests/test_brain.py` — k-NN predictions for canonical Hinglish set
- CREATE `tests/test_entity_extractor.py`
- CREATE `tests/test_sentiment.py`
- CREATE `tests/test_memory.py`
- CREATE `tests/test_feedback.py`
- CREATE `tests/test_pipeline_smoke.py` — end-to-end without mic/speaker (mocks STT/TTS)

**Definition of Done**
- `pytest tests/` exits 0.

---

### **C12 — STT/TTS Local Upgrade** *(deferred to last)*

**Goal**
Replace cloud STT/TTS with `faster-whisper` + Piper / Coqui.

**Files**
- UPDATE `core/stt.py`
- UPDATE `core/tts.py`

**STT change**
```python
from faster_whisper import WhisperModel
self.whisper = WhisperModel("small", device="cpu", compute_type="int8")
# fallback to recognize_google ONLY if user explicitly enables online mode
```

**TTS change**
```python
# Try local first (Piper or Coqui), fallback to Edge-TTS, then pyttsx3.
```

**Definition of Done**
- App works in airplane mode end-to-end (no network).

---

## 5. How to Resume (for future sessions)

1. **Read `BRAIN_CHECKPOINTS.md`** — find the next `⏳ Pending` checkpoint.
2. **Open this file** at the matching checkpoint section.
3. **Execute** the checkpoint per its definition of done.
4. **Update `BRAIN_CHECKPOINTS.md`**: mark previous checkpoint ✅ Done with date; mark next as 🔄 In Progress.
5. **Commit only the files listed under "Files"** for that checkpoint — don't drift.

If something in this plan turns out to be wrong mid-implementation, **update this plan first**, then implement. The plan is the source of truth.

---

## 6. Naming Conventions

- Class names: `PascalCase` (e.g., `JarvisBrain`, `EntityExtractor`).
- Module names: `snake_case` (e.g., `intent_classifier.py`).
- Public methods: `snake_case`.
- Private helpers: `_leading_underscore`.
- Constants: `UPPER_SNAKE`.
- Dataclasses for structured returns (`Prediction`, `Sentiment`, etc.) — no bare tuples in public API.

---

## 7. Logging

Every module logs through Python's `logging` (not `print`) once C9 lands. Until then, prints are fine. Logger name is the module name. Level configurable via `JARVIS_LOG_LEVEL` env var (default INFO).

---

## 8. Out of scope (for now)

- Wake-word detection (Porcupine / OpenWakeWord) — add after C12.
- Multi-user profiles.
- Cloud sync.
- Mobile companion app.
- Plugin marketplace.

These are valid future work but explicitly deferred.
