# AERIS / Jarvis 3.0 — Brain Architecture Review

**Author:** Opus 4.7 review pass
**Scope:** `New version- 3.0/core/*`, `data/intents.json`, `data/entities.json`, model metadata
**Goal of this doc:** honest audit of what you built, what is wrong (and why), and the correct, production-grade approach for a *fully local* Hinglish Jarvis brain that learns from use.

---

## 0. TL;DR — The Five Big Problems

| # | Problem | Severity | Where |
|---|---------|----------|-------|
| 1 | Encoder `all-MiniLM-L6-v2` is **English-only** — your Hinglish input is being mangled by a hand-written word map before it ever sees the model | 🔴 Critical | `core/neural_engine.py`, `core/normalizer.py` |
| 2 | Trainer reports **`accuracy: 1.0`** — this is **overfitting**, not skill. No validation split, no early stopping, 120 epochs on 301 patterns | 🔴 Critical | `core/trainer.py`, `data/models/model_metadata.json` |
| 3 | Entity extraction is a single hard-coded loop for `app_name` only. Time, date, numbers, URLs, queries, person names are never extracted — every other intent immediately falls into slot-filling, which is annoying UX | 🟠 High | `core/main_engine.py:_extract_entities` |
| 4 | STT uses **Google online** (`recognize_google`) and TTS uses **Edge-TTS online**. Both contradict your "completely local" requirement | 🟠 High | `core/stt.py`, `core/tts.py` |
| 5 | What you call "reinforcement learning" is actually **continual / online learning with user feedback**. RL needs reward signals + exploration; that's not what you want here. The right design is much simpler and more useful | 🟡 Medium | conceptual |

Everything else (multi-command splitter, threshold tuning, no disambiguation) is fixable once these five are addressed.

---

## 1. Component-by-Component Audit

### 1.1 The Brain (`neural_engine.py` + `trainer.py`)

**What you built**
- Frozen `all-MiniLM-L6-v2` SentenceTransformer → 384-dim embedding
- Trainable Keras Sequential head: `Dense(256) → Dropout(0.3) → Dense(128) → Dropout(0.2) → Softmax(num_classes)`
- Auto-retrain triggered by MD5 hash change of `intents.json`
- Confidence threshold 0.65, fuzzy fallback otherwise

**What is wrong**

**(a) The encoder cannot speak Hinglish.**
`all-MiniLM-L6-v2` is trained on English. When you feed it `"chrome kholo"`, it sees `"chrome kholo"` as two unrelated tokens; the embedding it produces is essentially garbage for the Hindi half. To work around this you wrote `HinglishNormalizer` which translates `kholo → open`, `band → close`, etc., before encoding. That bandage has three problems:

- **Coverage debt.** Every new Hinglish verb form (`kholna`, `kholunga`, `khol diya`) needs a new manual entry. You will be maintaining this map forever.
- **Information loss.** Filler-word stripping deletes context that real models would use (tone, politeness, urgency).
- **Fragility on code-mixed input.** `"chrome thoda jaldi khol bhai"` becomes `"chrome quickly open"` — passable; `"mujhe abhi YouTube pe Arijit ka latest gaana sunna hai"` becomes `"now play music"` — you've thrown away "Arijit", "latest", "YouTube". The query entity is gone before extraction even runs.

**(b) The trainer is overfitting and you cannot tell.**
Look at the metadata you saved:
```json
{ "num_classes": 21, "num_patterns": 301, "accuracy": 1.0 }
```
`accuracy: 1.0` on **training data with no validation split** means: the model memorized the 301 sentences. It says nothing about how it handles a new sentence. Worse, you trained 120 epochs at batch size 8 — that is absurd capacity for 301 samples. The dense head will brittle-fit and nuke any subtle generalization MiniLM was offering.

**(c) Auto-retrain is the wrong abstraction.**
Hashing `intents.json` and re-running full training on every change *feels* automatic but it:
- blocks app startup for 30–90s once the dataset grows;
- never adds **negative examples** (the model has no idea what *isn't* an intent);
- is incompatible with the "learns from use" goal — there is no path for a corrected misclassification to become training data.

**(d) Below-threshold = silent refusal.**
If confidence < 0.65, you say *"samajh nahi aaya"* and drop the user. A real assistant should:
1. Show top-2 / top-3 candidates and ask **"Did you mean A or B?"**
2. Log the rejected utterance to a `low_confidence.jsonl` file
3. On next boot (or on demand), let the user label them — that is your real training data feedstock

---

### 1.2 The Normalizer (`normalizer.py`)

**What you built**
A two-pass Hinglish→English string rewriter with a phrase map, word map, and filler-word blacklist.

**What is wrong**
This component should not exist in a 2026 system. It exists only because the encoder above is English-only. Once you swap to a multilingual encoder, **the normalizer goes away entirely** — the model handles `"chrome kholo"` natively, and you get the `"Arijit ka latest gaana"` query intact for entity extraction.

Keeping the normalizer as a *shallow* preprocessor (lowercase, strip punctuation) is fine. The translation map and filler list should be deleted.

---

### 1.3 STT (`stt.py`)

**What you built**
Google Web Speech (`recognize_google`, `language="en-IN"`) with Vosk offline fallback.

**What is wrong**
- `recognize_google` is the **unofficial, free, undocumented** Google Web Speech endpoint. It is rate-limited, can be blocked at any time, and every utterance leaves your machine. That is the opposite of "fully local."
- `language="en-IN"` is Indian-English, not Hinglish. It transcribes Devanagari-sounding words into mangled English ("kholo" → "kolo" / "kola"). You cannot build reliable Hinglish on this.
- Vosk offline is OK for English but its small Indic models are weak on code-mixed input.

**The right choice** is `faster-whisper` (CTranslate2 build of Whisper) with `small` or `medium` model and `language="hi"` or auto-detect. Whisper is genuinely multilingual and handles Hindi-English code-mixed audio well. It runs locally, on CPU at acceptable latency for a desktop assistant, and on GPU very fast.

---

### 1.4 TTS (`tts.py`)

**What you built**
Edge-TTS (`en-IN-NeerjaNeural`) with `pyttsx3` fallback.

**What is wrong**
- Edge-TTS is a **Microsoft cloud service**. Same problem as Google STT — not local, can be revoked any day, requires internet.
- `pyttsx3` fallback is offline but uses the OS SAPI voices, which on Windows sound robotic and have no real Hindi voice.

**The right choice** depends on tolerance for setup:
- **Easiest local:** `piper-tts` — small, fast, English voice quality is good. No real Hindi voice.
- **Best Hindi quality local:** AI4Bharat **IndicParler-TTS** or **Coqui XTTS-v2** (multilingual, voice cloning supported).
- **Acceptable hybrid:** keep Edge-TTS as the *default* online voice but fail over to Piper or Coqui when offline. Clearly document that the assistant is "local-first" not "local-only."

---

### 1.5 Entity Extraction (`main_engine.py:_extract_entities`)

**What you built**
A single nested loop that scans the user text for any alias of any app in `entities.json` and sets `entities["app_name"]` if found.

**What is wrong**
- It only handles **one entity type**: `app_name`. The other 6 entity types your intents declare (`message`, `time`, `query`, `expression`, `content`, `url`, `person`) are **never extracted from the original utterance**. Every single non-app intent immediately drops into the slot-filling prompt loop.
- That means: user says *"YouTube pe Arijit ka latest gaana chala do"*, intent classifier correctly returns `play_youtube`, then Jarvis asks **"Kya dekhna hai YouTube pe?"** because no `query` entity was extracted. That's broken UX.

**The right design** is a layered extractor:
1. **Regex layer** for deterministic patterns: time (`5 baje`, `5pm`, `subah 6 baje`), numbers, URLs (`https?://...`), simple math expressions (`12 + 7 * 3`).
2. **Gazetteer layer** for lookup-style entities: app names (you already have this), contact names, app-specific keywords.
3. **NER model layer** for free-form: `spaCy en_core_web_sm` for English NER (PERSON, ORG, GPE, DATE, TIME), or a lightweight transformer NER for multilingual.
4. **"Rest of sentence after intent verb" heuristic** as a last resort for `query`, `content`, `expression` slots — strip the intent trigger words and the remainder *is* the query. (Your normalizer already kind of does this destructively; do it constructively in the extractor.)

Slot filling then only asks for entities that *all four layers* failed to fill — much rarer.

---

### 1.6 Slot Filling (`state_manager.py`)

**What you built**
A linear loop: for each `required_entity` of the predicted intent, if not present in slots, ask the configured prompt and wait.

**What is right**
The shape is correct. Storing `is_waiting` + `waiting_for`, re-entering `process_prediction` after the answer comes in, returning the `SUCCESS_EXECUTE|intent|json` sentinel — all sound.

**What is wrong / weak**
- `handle_follow_up` stores the user's raw input as the entity value with no validation or extraction. If user says *"5 baje shaam ko"* for a `time` slot, you store the literal string, not a parsed datetime. The executor then has to deal with raw Hinglish.
- No way to **abort** a half-filled command. If user says *"meeting schedule karo"*, then changes their mind, there is no `cancel` intent that resets state.
- No timeout — if the user wanders off mid-prompt, state stays `is_waiting` forever.
- Single conversation only — no support for multi-step composite commands ("open chrome aur 5 minute baad close kar dena").

These are all medium-priority once the bigger items are fixed.

---

### 1.7 Multi-command splitting (`main_engine.py:_split_commands`)

Splits on `" and "`, `" aur "`, `" then "`, `" phir "`, `" also "`. This will break:
- `"search for tom and jerry on YouTube"` → splits into two halves
- `"calculate 2 and 3"` → same
- `"set reminder for milk and bread at 7pm"` → same

A safer approach: **split only after a recognised intent boundary**. Run the classifier on the full sentence; if confidence is below threshold, *try* splitting on conjunctions and re-classify each half. Only commit to the split if both halves classify confidently.

---

### 1.8 The "reinforcement learning" goal

You wrote:

> *what I want is, instead of any ml model, deep learning is good option ... my jarvis brain should be using reinforcement learning like it should learn with use*

This conflates three different things. Let me separate them clearly:

| Term | What it actually is | Right for Jarvis? |
|------|---------------------|-------------------|
| **Supervised learning** | Train on labeled (sentence → intent) pairs. What `trainer.py` does today. | ✅ Yes — this is the core |
| **Reinforcement learning** | Agent takes actions in an environment, gets a numeric reward, learns a policy that maximises long-term reward. Used for games (AlphaGo), robotics, RLHF on LLMs. | ❌ No — there is no "environment" or "reward" for intent classification |
| **Continual / online learning with human feedback** | When the model gets something wrong (or low-confidence), the user corrects it; that correction becomes new training data; model updates incrementally. | ✅ **This is what you actually want.** |

The right "learns from use" loop for Jarvis is:

1. **Log every utterance** with: raw text, predicted intent, confidence, top-3 alternatives, user reaction (executed, cancelled, corrected).
2. **Below threshold** → ask user *"Did you mean A or B? Or teach me a new command."* If they pick one, that utterance becomes a new pattern for that intent.
3. **Wrong execution** → user can say *"galat"* / *"undo"* / *"that wasn't what I meant"* — the last utterance gets flagged for review.
4. **Periodically** (nightly, or on user trigger) → re-train the dense head incrementally on the new patterns. Or, better, use a **k-nearest-neighbours head** instead of a dense head — see §2.

This is **simpler, faster to build, and more debuggable** than RL. And it actually does what you want: the assistant gets better the more you use it.

---

## 2. The Right Architecture (Production-Grade Local Jarvis)

Here is the target architecture. It keeps the spirit of what you built (semantic embeddings + slot filling) but replaces the parts that are causing pain.

```
┌──────────────────────────────────────────────────────────┐
│  Mic → faster-whisper (small, hi+en) → text              │
│                                                           │
│  text → light preprocess (lowercase, strip punct)         │
│                                                           │
│  text → multilingual sentence encoder                     │
│         (paraphrase-multilingual-MiniLM-L12-v2)           │
│                                                           │
│  embedding → k-NN over labeled pattern bank               │
│              (FAISS or sklearn NearestNeighbors)          │
│              ↓                                             │
│              top-K patterns + their intents + distances   │
│              ↓                                             │
│              vote → (intent, confidence, top-3 alt)       │
│                                                           │
│  text → entity extractor (regex + gazetteer + NER)        │
│                                                           │
│  intent + entities → state manager (slot filling)         │
│                                                           │
│  filled command → executor                                │
│                                                           │
│  response → Piper or IndicParler TTS → speaker            │
│                                                           │
│  ──────── Feedback loop ────────                          │
│  every utterance + outcome → SQLite log                   │
│  low-confidence + corrections → pending_patterns.jsonl    │
│  user reviews & accepts → appended to intents.json        │
│  k-NN index rebuilds in <1 second (no training)           │
└──────────────────────────────────────────────────────────┘
```

### Why this is better than what you have

**(1) Multilingual encoder = no more normalizer.**
`paraphrase-multilingual-MiniLM-L12-v2` (also 384 dims, similar speed to your current encoder) understands Hindi, Hinglish, English, and ~50 other languages out of the box. `"chrome kholo"`, `"open chrome"`, and `"chrome खोलो"` all produce nearby embeddings. You delete `normalizer.py`'s translation map, drop the 100+ lines of word mappings, and gain accuracy.

**Pros:** zero maintenance, handles unseen Hinglish verbs, preserves entity text intact.
**Cons:** slightly larger model (~120 MB vs 90 MB), ~10–20 ms slower per encode (still <50 ms on CPU).
**Alternative:** `LaBSE` (Google, very strong cross-lingual but 470 MB) or `intfloat/multilingual-e5-small` (newer, slightly better on retrieval tasks).

**(2) k-NN head = true incremental learning.**
Instead of a Keras dense classifier you have to retrain, store all labelled patterns as `(embedding, intent_label)` rows in a FAISS / sklearn index. To predict, embed the input, find the K closest patterns, vote.

**Pros:**
- Adding a new pattern = `index.add(embedding)` + append to label array. **No training step.** Sub-second.
- Confidence is interpretable (cosine distance, not a softmax).
- Top-K naturally gives you the disambiguation candidates you need for "Did you mean A or B?"
- No overfitting — the model literally cannot overfit, it's a lookup.

**Cons:**
- Memory grows linearly with pattern count (fine: 10k patterns × 384 floats × 4 bytes = 15 MB).
- Slightly less powerful than a well-trained dense head when training data is large and clean — but you don't have that situation; you have small, hand-curated data.

**Alternative:** keep the dense head but add proper **train/val split, early stopping on val loss, and class-weighted loss**. This still requires periodic retraining and still overfits more easily than k-NN. For your scale, k-NN wins.

**(3) Layered entity extraction = fewer slot-filling prompts.**
Add `core/entity_extractor.py`:
- Regex extractors registered per entity type (`time`, `url`, `number`, `expression`).
- Gazetteer extractor reuses your existing `entities.json`.
- spaCy NER for `person`, `org`, free-form names.
- Residual extractor: after stripping recognised intent trigger words, the remainder fills `query` / `content` slots.

**Pros:** *"Arijit ka latest gaana YouTube pe chala do"* now extracts `query="Arijit ka latest gaana"` directly — no follow-up prompt needed.
**Cons:** more code; spaCy NER adds ~50 MB and ~20 ms latency. Worth it.

**(4) Continual learning loop = the "RL" feeling, done right.**
- New file `data/feedback_log.sqlite` with table `(utterance, predicted_intent, confidence, top3_json, action_taken, user_feedback, timestamp)`.
- New file `data/pending_patterns.jsonl` for low-confidence utterances awaiting your review.
- New CLI / UI command: `jarvis review` — shows you the pending list, you approve/correct, and they get appended to `intents.json` and the k-NN index.
- Nightly (or on demand) the index rebuilds from `intents.json`.

**Pros:** assistant genuinely improves with use; you control quality (no garbage gets auto-added); review takes 2 minutes a day.
**Cons:** requires UI (CLI is fine for v1) and discipline to actually do the reviews.

**(5) Local-only STT/TTS — non-negotiable for your stated goal.**
- STT: `faster-whisper` `small` model (~480 MB), `language="hi"` or auto-detect, runs CPU at 1–2× realtime.
- TTS: Start with `piper-tts` (English-only but instant + 50 MB). If Hindi quality matters more than disk/RAM, swap to AI4Bharat IndicParler or Coqui XTTS-v2.

**Pros:** zero network calls, no rate limits, no privacy leak, works on a plane.
**Cons:** download size; first-load latency; Hindi TTS quality from local models is good but not Edge-TTS-Neerja good (yet).

**(6) Local LLM as fallback brain.**
For utterances the k-NN router rejects (confidence too low across all candidates), don't just say *"samajh nahi aaya."* Pass them to a small local LLM:
- `Phi-3-mini-4k-instruct` (3.8B, ~2.4 GB quantized) or
- `Llama-3.2-3B-Instruct` (3B, ~2 GB quantized) via `ollama`.

Prompt it with: *"You are Jarvis. The user said: <text>. Respond conversationally, and if they asked you to do something not in your skills, say so."* This handles the "what is the meaning of life" / chit-chat / unknown commands gracefully without bloating your intent list.

**Pros:** handles the long tail; makes Jarvis feel intelligent, not scripted; runs locally on Ollama.
**Cons:** another 2–4 GB of disk; 200–500 ms latency on CPU (much faster on GPU); requires Ollama installed.

---

## 3. Phased Upgrade Plan

Don't rewrite everything at once. Here is the order I'd do it in, with what changes per phase.

### Phase A — Brain Surgery (highest value, ~1 day)
1. Swap encoder: `all-MiniLM-L6-v2` → `paraphrase-multilingual-MiniLM-L12-v2` in both `trainer.py` and `neural_engine.py`.
2. Replace dense Keras head with `sklearn.neighbors.NearestNeighbors` (cosine metric, K=5).
3. Delete the translation/filler logic from `normalizer.py`; keep only lowercase + punctuation strip.
4. Update `model_metadata.json` schema to record train **and** val accuracy separately.
5. Add disambiguation: if top-1 and top-2 confidence are within 0.05, return both and prompt the user.

After Phase A you should be able to drop `normalizer.py`'s translation map entirely and *still* see equal or better accuracy on a held-out set of Hinglish sentences.

### Phase B — Entity extraction (~half day)
1. Create `core/entity_extractor.py` with regex + gazetteer + residual layers.
2. Move app_name extraction out of `main_engine.py` into the new module.
3. Add regex for time, date, number, URL, math expression.
4. Wire into `main_engine.py:run` so extracted entities are passed to `state_manager.process_prediction` *before* slot filling kicks in.

### Phase C — Local STT + TTS (~half day each)
1. Replace `recognize_google` with `faster-whisper` (small or medium, hi+en).
2. Keep Edge-TTS as the *default* (it sounds best) but make Piper or Coqui the fallback for offline.

### Phase D — Continual learning (~1 day)
1. Add `data/feedback_log.sqlite` + the schema above.
2. Log every utterance + outcome.
3. Build `python -m core.review` CLI to walk pending patterns.
4. Approved patterns get appended to `intents.json`; k-NN index rebuilds on next boot (or hot-reloads).

### Phase E — LLM fallback (~half day)
1. Install Ollama + pull `phi3:mini` or `llama3.2:3b`.
2. Add `core/llm_fallback.py` that calls Ollama HTTP API.
3. Wire into `main_engine.py`: if `predict_intent` returns empty, route to LLM with a system prompt describing Jarvis's persona.

### Phase F — Polish (anytime)
- Wake word (OpenWakeWord, custom "Jarvis" model).
- Voice activity detection (Silero VAD) to replace `pause_threshold` heuristic.
- Cancel intent + slot-filling timeout.
- Smarter multi-command splitter (intent-aware).
- Per-user profiles.

---

## 4. Specific Files To Change (concrete diff list)

When you're ready to implement, here is the file-by-file scope:

| File | Change |
|------|--------|
| `core/trainer.py` | Swap encoder; replace dense Keras with k-NN persistence; add train/val split + early stopping if you keep a classifier; record both accuracies |
| `core/neural_engine.py` | Swap encoder; load k-NN index instead of Keras model; return top-K with disambiguation |
| `core/normalizer.py` | Delete `translation_map`, `phrase_map`, `fillers`. Keep only `text.lower().strip()` and punctuation strip. Or delete the file and inline a `clean_text()` helper |
| `core/main_engine.py` | Move entity extraction out; handle disambiguation prompts; route empty predictions to LLM fallback |
| `core/state_manager.py` | Add `cancel` handling; add timeout on `is_waiting`; pass through entity validation |
| `core/entity_extractor.py` | **NEW** — regex + gazetteer + spaCy NER + residual layers |
| `core/feedback.py` | **NEW** — SQLite logging, pending pattern queue |
| `core/llm_fallback.py` | **NEW** — Ollama client wrapper |
| `core/stt.py` | Swap `recognize_google` → `faster-whisper` |
| `core/tts.py` | Add Piper / Coqui local backend; keep Edge as preferred online voice |
| `data/intents.json` | (no schema change needed — k-NN reads same shape) |
| `data/models/model_metadata.json` | Schema: `train_accuracy`, `val_accuracy`, `num_patterns_per_class`, `last_review_at` |
| `requirements.txt` | Add: `faster-whisper`, `spacy`, `faiss-cpu` (or stay on `sklearn`), `ollama` (HTTP client). Remove `tensorflow` if you commit to k-NN |

---

## 5. What NOT to Change

These parts are well-designed; leave them alone:

- **Slot-filling state machine shape** in `state_manager.py` — the `is_waiting` / `waiting_for` / `SUCCESS_EXECUTE|...` protocol is clean.
- **Executor dispatch table** in `executor.py` — the lambda map is the right pattern. Just add new actions as you add intents.
- **Intents file shape** (`patterns` / `required_entities` / `prompts`) — clean, declarative, easy to extend.
- **STT/TTS as separate classes** with `listen()` / `speak()` — clean interface; only the *backend* needs to change.

---

## 6. Honest Trade-offs

You said you want this Jarvis "for the entire life, in production." Be aware:

- **Local Hindi TTS is not at Edge-Neerja quality yet.** If you go fully local, voice quality drops noticeably. The hybrid (Edge online, Piper offline) is probably the right pragmatic call.
- **Whisper is amazing but not free of latency.** On CPU, expect ~1–2 seconds for a 5-second utterance. With a small CUDA-capable GPU it's near-instant. If your laptop has no GPU, consider `faster-whisper` `tiny` or `base` for snappier response, accepting some accuracy loss.
- **Ollama needs ~4–8 GB free RAM** while running. If your laptop is constrained, the LLM fallback is optional.
- **k-NN scales linearly.** At 10,000 patterns it is still milliseconds. At 1,000,000 patterns you'd want FAISS HNSW. You will not hit that.
- **The continual-learning loop is only as good as your discipline to review pending patterns.** If you never run `jarvis review`, the pending file just grows and the assistant doesn't improve. Schedule it.

---

## 7. One-Sentence Summary

> Replace the English-only encoder + Keras head + manual normalizer with a multilingual encoder + k-NN index + proper entity extractor; replace cloud STT/TTS with local Whisper + Piper; add a feedback log and review CLI for true continual learning; add a small local LLM as fallback for unknown commands.

That gets you a fully local, learns-from-use, Hinglish-native Jarvis brain that you can actually run forever.
