# JARVIS BRAIN — CHECKPOINT TRACKER

> Single source of truth for build progress. **Read this first** when resuming.
> Detailed spec for each checkpoint lives in `BRAIN_BUILD_PLAN.md`.

**Status legend:** ⏳ Pending  ·  🔄 In Progress  ·  ✅ Done  ·  ⚠️ Blocked

---

## Progress

| ID  | Checkpoint                              | Status | Date       | Notes |
|-----|-----------------------------------------|--------|------------|-------|
| C1  | Multilingual brain core (k-NN + encoder)| ✅ Done | 2026-04-25 | Index built, cached, 9-sample smoke passed. See "C1 Validation" below. |
| C2  | Layered entity extractor                | ✅ Done | 2026-04-25 | 11/11 standalone cases pass; 4/5 pipeline cases pass (5th is a classifier ambiguity, not extractor). |
| C3  | Sentiment analysis                      | ✅ Done | 2026-04-25 | VADER + ~30 Hinglish booster terms. All 10 smoke cases pass; DoD thresholds met. |
| C4  | User memory (long-term facts)           | ✅ Done | 2026-04-25 | 10/10 cases pass; round-trips through disk; "my name is X" / "main hoon X" / Hinglish-order favourites all detected. |
| C5  | Conversation context (short-term)       | ✅ Done | 2026-04-25 | Rolling deque of 6 messages, OpenAI-style export, sentiment tag per turn. |
| C6  | Chit-chat LLM via Ollama                | ✅ Done | 2026-04-25 | Code ready. Activates when user installs Ollama + pulls a model. Health check works. |
| C7  | Reward-shaped continual learning        | ✅ Done | 2026-04-25 | Bandit policy works: thresholds drift down on positives, up on corrections; review CLI mutates intents.json. |
| C8  | Disambiguation                          | ✅ Done | 2026-04-25 | Close-call detector + Hinglish prompt + answer parser; 5 answer formats parsed. |
| C9  | Main engine rewire                      | ✅ Done | 2026-04-26 | All 8 modules wired into `process_text()` (testable without mics). End-to-end smoke passed. |
| C10 | Executor extensions (memory recall)     | ✅ Done | 2026-04-26 | `detect_and_recall` + Hindi key aliases (naam/ghar/kaam/shahar/city/office). |
| C11 | Tests + terminal main.py                | ✅ Done | 2026-04-26 | 89 pytest tests pass; `main.py --text` REPL works. |
| C12 | STT/TTS local upgrade                   | ⏸ Skipped (per user) | | Deferred indefinitely. Online STT/TTS stays. |

---

## Currently Working On

**Nothing — build complete (per user scope: C12 skipped).**

## ✅ Build status

**11 of 12 checkpoints shipped. C12 explicitly deferred.**

The assistant is fully operational from the terminal:
```
python main.py             # voice mode (existing STT/TTS — Google + Edge)
python main.py --text      # text mode (no audio deps)
```

In-REPL slash commands (text mode):
- `:facts` — show stored user facts
- `:stats` — show feedback DB stats (utterances logged, pending patterns, learned thresholds)
- `:help` — list commands
- `quit` / `exit` — leave

Brain capabilities: Hinglish intent routing · regex+gazetteer+NER entities ·
VADER sentiment · persistent user memory + recall · conversation context ·
Ollama chit-chat (when installed) · contextual-bandit threshold learning ·
disambiguation prompts · cancel + correction handling.

## 📋 Deferred (not in current scope)

- C12 — local STT (`faster-whisper`) + local TTS (Piper). Online cloud STT/TTS stays.
- GUI rewire — `ui/dashboard.py` and friends still wire to pre-redesign code paths.
- Wake word, intent-aware multi-command splitter, slot-fill timeout — Phase F polish.

---

## C11 Validation Log (2026-04-26)

**Files created**
- `main.py` — full rewrite. Voice mode (`python main.py`) and text mode (`python main.py --text`). REPL with `:facts`, `:stats`, `:help`, `quit`.
- `tests/__init__.py` — empty, makes tests a proper package
- `tests/conftest.py` — fixtures: `tmp_memory_path`, `tmp_feedback_db`, `tmp_intents_copy`, session-scoped `shared_brain` / `shared_extractor` / `shared_sentiment`. Excludes legacy `test_stt.py`, `test_tts.py`, `test_brain.py` from collection.
- `tests/test_normalizer.py` — 8 tests
- `tests/test_intent_classifier.py` — 13 tests (parametrised across 10 canonical sentences)
- `tests/test_entity_extractor.py` — 13 tests (parametrised across 10 input/intent pairs)
- `tests/test_sentiment.py` — 8 tests
- `tests/test_memory.py` — 14 tests (store, recall, persistence round-trip, Hindi aliases)
- `tests/test_conversation.py` — 4 tests
- `tests/test_disambiguator.py` — 9 tests
- `tests/test_feedback.py` — 9 tests (default threshold, drift down/up, approve_pattern, clamps)
- `tests/test_pipeline.py` — 11 tests (end-to-end via `process_text()`, isolated tmp DBs)

**Files modified**
- `core/main_engine.py` — `__init__` now accepts `memory_path`, `feedback_db_path`, `verbose` for test isolation
- `requirements.txt` — added `pytest`

**Dependency installed**
- `pytest`

**Test results**

```
89 passed in 189.79s (0:03:09)
```

Coverage by module: normalizer (8) · brain/k-NN (13) · entity extractor (13) ·
sentiment (8) · memory (14) · conversation (4) · disambiguator (9) ·
feedback bandit (9) · end-to-end pipeline (11).

**Two test bugs caught and fixed during the run** (both test code, not module code):
- `test_threshold_gate_returns_none` — 0.99999 wasn't impossible since exact-match cosine is 1.0; raised to 1.5
- `test_preserves_math_chars` — `*` isn't actually preserved by normalizer (and shouldn't be — encoder doesn't need it); test split into `_safe_math_chars` and `_drops_multiplication_chars`

**main.py text-mode smoke** (driven via piped stdin):

```
You:   hello my name is shivang
AERIS: Got it, Shivang. Nice to meet you.
You:   weather batao
AERIS: Mausam filhaal suhana hai, around 25 degrees Celsius.
You:   mera naam kya hai
AERIS: Aapka naam Shivang hai.
You:   :facts
       facts: name: Shivang
You:   quit
       Goodbye.
```

---

## C8 + C9 + C10 Validation Log (2026-04-25 / 26)

**Files created**
- `core/disambiguator.py` — close-call detection + Hinglish prompt + multi-form answer parser

**Files modified**
- `core/state_manager.py` — added `is_waiting_disambig`, `set_awaiting_disambig`, `consume_disambig`, `reset()` public alias
- `core/main_engine.py` — full rewrite: `process_text()` pure pipeline + audio I/O isolation; wires C1–C8 + memory recall (C10)
- `core/brain.py` — dropped legacy `predict_intent()` shim
- `core/memory.py` — added `detect_and_recall` + Hindi key aliases (naam/ghar/kaam/shahar/city/office); replaced em-dash with ASCII hyphen for Windows console compat

**End-to-end pipeline smoke** (no audio I/O, all via `process_text()`)

| User input                                    | AERIS output                                              | Notes |
|-----------------------------------------------|-----------------------------------------------------------|-------|
| hello my name is shivang                      | Got it, Shivang. Nice to meet you.                        | C4 store |
| weather batao                                 | Mausam filhaal suhana hai, around 25 degrees Celsius.     | C1+executor |
| galat                                         | Sorry. Phir se batao kya karna hai?                       | C7 correction recorded |
| meeting schedule karo                         | Kiske saath meeting karni hai?                            | slot-fill |
| with raj                                      | Kis time pe meeting rakhni hai?                           | C2 entity-cleaned `person="raj"` |
| 5 pm                                          | raj ke saath meeting 5 pm pe schedule kar di.             | SUCCESS_EXECUTE |
| `i live in delhi`                             | Noted - aap rehte hain Delhi mein.                        | C4 store |
| `mera naam kya hai`                           | Aapka naam Shivang hai.                                   | C10 Hindi alias `naam→name` |
| `mera ghar kya hai`                           | Aapka ghar Delhi hai.                                     | C10 alias `ghar→location` |
| `mera kaam kya hai`                           | Aapka kaam Google hai.                                    | C10 alias `kaam→employer` |
| what do you know about me                     | Aapke baare mein ye pata hai: name Shivang, ...           | C10 generic recall |
| what's my pet                                 | Mujhe aapka pet pata nahi hai abhi.                       | C10 unknown-key fallback |
| cancel                                        | Kuch chal nahi raha cancel karne ke liye, sir.            | C9 cancel-with-no-state |

**Bandit policy observed live**
- After 1 "galat" on `get_weather`: threshold 0.5 → 0.52 (drift up — more cautious next time)

**Known limitations carried forward**
- Random-text utterance triggered disambig (between `system_info` and `get_weather`) instead of LLM fallback. Correct behaviour for the design — the bandit will solve it after a few cancellations push the threshold up.
- LLM chit-chat path requires Ollama installed + model pulled. Pipeline degrades gracefully without it.

---

## C7 Validation Log (2026-04-25)

**Files created**
- `core/feedback.py` — SQLite store, EMA threshold policy, pending pattern queue
- `core/review_cli.py` — interactive labelling tool

**Files created at runtime** (auto-managed)
- `data/feedback_log.sqlite` — 3 tables: `utterances`, `intent_thresholds`, `pending_patterns`

**Bandit policy constants** (`core/feedback.py` top of file)
- `ALPHA = 0.1` (EMA smoothing)
- `DEFAULT_THRESHOLD = 0.5`
- `MIN_THRESHOLD = 0.40`, `MAX_THRESHOLD = 0.90` (clamps)
- Drift down: avg_reward > 0.5 AND samples ≥ 5 → threshold -= 0.01
- Drift up: avg_reward < -0.2 → threshold += 0.02 (faster correction)

**Smoke test results** (`python -m core.feedback`)

| Scenario                                  | Result |
|-------------------------------------------|--------|
| Initial threshold for unseen intent       | 0.5 (DEFAULT_THRESHOLD) ✅ |
| 10 accepted `open_app` executions         | threshold drifted DOWN to **0.44** (avg_reward=+1.0) ✅ |
| 3 corrections on `play_music`             | threshold drifted UP to **0.56** (avg_reward=-1.0) ✅ |
| Cross-intent reward (corrected → correct) | `correct_intent` also gets +1 reward, threshold drops further |
| Pending pattern queued                    | Stored with utterance link, top3 JSON ✅ |

**End-to-end approve flow** (verified against isolated temp DB + temp intents.json):
- Queue → approve_pattern(pending_id, intent_name, intents_path)
- intents.json mutated correctly: open_app patterns 28 → 29; new pattern present
- Pending row status moved from "pending" to "approved"
- Approving for unknown intent name → returns False (no mutation, no exception) ✅

**Brain re-learning loop** — implicit. The brain's `IntentClassifier._boot()`
already hashes intents.json and rebuilds the k-NN index on change. So an
approved pattern requires only a Jarvis restart to take effect.

**Wiring** — None yet; C9 wires:
- brain.predict() → `accept_threshold = fb.get_threshold(predicted_intent)`
- after executor return → `fb.record_feedback(utterance_id, "accepted")` (default)
- on user "wrong"/"galat"/cancel → `fb.record_feedback(utterance_id, "corrected")`
- on low-confidence + LLM fallback → `fb.queue_low_confidence(...)`

**Review CLI** — Run with `python -m core.review_cli`. Interactive prompts:
- `1`/`2`/`3` — approve as the corresponding top-N intent
- `<intent_name>` — approve as any other known intent
- `s` — skip; `r` — reject; `l` — list intents; `q` — quit

---

## C6 Validation Log (2026-04-25)

**Files created**
- `core/llm_chat.py` — Ollama HTTP client + system-prompt assembly

**Smoke test results** (`python -m core.llm_chat`)
- `is_available()` → `False` (Ollama not running on this machine, expected)
- Code paths exercised: GET `/api/tags` health check + ConnectTimeout handling
- No exceptions raised; brain pipeline can safely call `is_available()` and route accordingly

**System prompt highlights**
- Adapts to user's language style automatically (English / Hinglish / Hindi)
- Injects `memory_facts` so chit-chat replies are user-aware
- Sentiment-driven tone hint ("match their energy" / "be gentle and supportive" / "be direct")
- Caps replies at 3 short sentences

**Setup required from user** (one-time)
1. `https://ollama.com` — download + install
2. `ollama pull phi3:mini` (3.8 GB) — or `ollama pull llama3.2:3b` (2 GB)
3. Ollama runs as background daemon — no further action needed

**Wiring** — None yet; C9 routes empty `predict()` results here when `is_available()` is True.

---

## C5 Validation Log (2026-04-25)

**Files created**
- `core/conversation.py` — ~70 lines. Deque-backed rolling buffer.

**Smoke test results** (`python -m core.conversation`)
- After 4 user/assistant pairs (8 messages) into a `max_turns=3` history (cap = 6 messages):
  - `len(h) == 6` ✅ — oldest pair dropped
  - `last_user_sentiment() == "neutral"` ✅
  - `as_messages()` returns the 6 most recent messages in OpenAI format
- Per-turn sentiment retained on user turns; assistant turns have no sentiment field

**Wiring** — None yet; consumed by C6 (LLM call) and C9 (main_engine wires both).

---

## C4 Validation Log (2026-04-25)

**Files created**
- `core/memory.py` — JSON-backed persistent store + 6 NL detection patterns

**Files created at runtime** (auto-managed)
- `data/user_memory.json` — created on first `set()` / `add_note()`

**Smoke test results** (`python -m core.memory`)

| Input | Result | Notes |
|-------|--------|-------|
| hello my name is shivang | name="Shivang" | DoD ✅ |
| my name is bob smith | name="Bob Smith" | multi-word |
| i live in new delhi please | location="New Delhi" | trailing "please" stripped by boundary |
| i work at google | employer="Google" | bug fixed: required `\s+` was missing outside the alternation |
| my favourite browser is chrome | favorite_browser="Chrome" | English word order |
| remember that i need to buy milk on tuesdays | added to notes list | |
| main hoon shaurya | name="Shaurya" | Hinglish form |
| mera favourite gaana shape of you hai | favorite_gaana="Shape Of You" | Hinglish word order — needed second pattern |
| weather batao | None (no match) | non-memory utterance correctly skipped |
| chrome kholo | None (no match) | ditto |

**Persistence** — reloaded the JSON from disk, all 5 facts + 1 note round-tripped intact.

**Wiring** — None yet; C9 inserts `mem.detect_and_store(text)` as the first step of `main_engine.run()`. C6 also injects `mem.all_facts()` into the LLM system prompt.

---

## C3 Validation Log (2026-04-25)

**Files created**
- `core/sentiment.py` — VADER wrapper, Hinglish lexicon extension (~30 booster terms), heuristic fallback

**Dependency installed**
- `vaderSentiment 3.3.2` (pure-Python, ~125 KB)

**Smoke test results** (`python -m core.sentiment`)

| Input                                       | Label    | Score   | Notes |
|---------------------------------------------|----------|---------|-------|
| thank you yaar bahut accha kaam kiya        | positive | +0.718  | DoD ≥ 0.3 ✅ |
| yeh kya bakwaas hai                         | negative | -0.612  | DoD ≤ -0.2 ✅ |
| chrome kholo                                | neutral  | +0.000  | DoD `|score|` < 0.2 ✅ |
| this is amazing                             | positive | +0.586  |       |
| i hate this so much                         | negative | -0.572  |       |
| okay theek hai                              | positive | +0.402  | "theek" from extended lex |
| mast kaam kar rahe ho                       | positive | +0.542  | "mast" from extended lex |
| kuch samajh nahi aaya                       | neutral  | -0.077  | "nahi" tilts mildly |
| bahut kharab response tha                   | negative | -0.361  | "kharab" from extended lex |
| shukriya bhai                               | positive | +0.459  | "shukriya" from extended lex |

**Wiring** — None yet. C6 (LLM chat) consumes `Sentiment` for tone-adapted replies; C9 wires it through `main_engine.run()`.

**Upgrade path documented** — swap `_classify` to `cardiffnlp/twitter-xlm-roberta-base-sentiment` via `transformers` for true multilingual sentiment (≈500 MB vs current 125 KB).

---

## C2 Validation Log (2026-04-25)

**Files created**
- `core/entity_extractor.py` — 4-layer extractor: regex → gazetteer → spaCy NER (optional) → residual span

**Files modified**
- `core/main_engine.py` — added `EntityExtractor` import + instance; replaced 14-line `_extract_entities` body with single delegation call; removed unused `_load_entities` and `_entity_lists`
- `requirements.txt` — uncommented `spacy` (optional dep, extractor degrades gracefully without it)

**Standalone test results** (`python -m core.entity_extractor`)

| Input                                            | Intent           | Extracted                                      |
|--------------------------------------------------|------------------|------------------------------------------------|
| youtube pe arijit ka latest gaana chala do       | play_youtube     | `query="arijit ka latest gaana"`              |
| 5 baje shaam ko milk lena yaad dilana            | set_reminder     | `time="5 baje shaam"`, `message="milk lena"` |
| chrome kholo                                     | open_app         | `app_name="chrome"`                          |
| google chrome open karo                          | open_app         | `app_name="chrome"` (longest-alias-wins)     |
| https://github.com/foo kholo                     | open_website     | `url="https://github.com/foo"`               |
| github.com kholo                                 | open_website     | `url="https://github.com"` (auto-scheme)     |
| 12 + 7 * 3 calculate karo                        | calculate        | `expression="12 + 7 * 3"`                    |
| with shivang at 5 pm meeting lagao               | schedule_meeting | `time="5 pm"`, `person="shivang"`            |
| note kar do meeting at 6 pm                      | create_note      | `content="meeting at 6 pm"`                  |
| python tutorial google pe search karo            | search_web       | `query="python tutorial"`                    |
| weather batao                                    | get_weather      | `{}` (no required entities)                  |

**Pipeline (brain → extractor → state_manager) results**

4/5 inputs route end-to-end. The 5th (`5 baje shaam ko milk lena yaad dilana`) is misclassified by the brain as `get_time` (the word "baje" overlaps strongly with time-query patterns). When the correct intent is forced, the extractor still pulls the right entities. Fix surface lives in C7 (continual learning will let the user correct this once and the brain learns).

**Known limitations carried forward**
- spaCy NER not installed by default — the "with X" regex shortcut handles person extraction in the meantime; install `spacy` + `en_core_web_sm` for free-form `PERSON`/`DATE` extraction.
- Trigger word lists for residual-span are hand-curated per intent. Long-term these should be derived from the patterns themselves (TF-IDF style); deferred.

---

## C1 Validation Log (2026-04-25)

**Files created**
- `core/intent_classifier.py` — multilingual encoder + k-NN, exp-weighted vote (temp=10), top-1 cosine similarity as confidence
- `core/brain.py` — `JarvisBrain` orchestrator with legacy `predict_intent()` shim
- `data/models/intent_index.pkl` — cached index (auto-built first run)
- `data/models/intent_metadata.json` — hash + counts + encoder name + build time

**Files modified**
- `core/normalizer.py` — stripped to lowercase + punctuation strip; URL chars preserved
- `core/main_engine.py` — `from core.brain import JarvisBrain`; `self.brain = JarvisBrain()`
- `requirements.txt` — `tensorflow` removed; `# spacy` queued for C2

**Files deleted**
- `core/neural_engine.py`
- `core/trainer.py`
- `data/models/jarvis_advanced_brain.h5`
- `data/models/label_encoder.pkl`
- `data/models/model_metadata.json`

**Orphan model files left in place** (safe to delete later, unrelated to current pipeline):
- `data/models/jarvis_model.h5`
- `data/models/classes.pkl`
- `data/models/words.pkl`
- (`data/models/hand_landmarker.task` is used by `utils/gesture.py` — KEEP)

**Smoke test results** (`python -m core.intent_classifier`)

| Input                                     | Predicted intent  | Confidence | Notes |
|-------------------------------------------|-------------------|------------|-------|
| chrome kholo                              | open_app          | 1.000      | ✅ |
| notepad band karo                         | close_app         | 1.000      | ✅ |
| weather batao                             | get_weather       | 1.000      | ✅ |
| volume badhao                             | volume_up         | 1.000      | ✅ |
| screenshot lo                             | take_screenshot   | 1.000      | ✅ |
| mujhe yaad dilao 5 baje                   | set_reminder      | 0.930      | ✅ |
| calculator open karo                      | open_app          | 1.000      | ✅ (was misrouted to `calculate` before exp-weighted vote) |
| youtube pe arijit ka gaana chala do       | play_youtube      | 0.798      | ✅ entity span preserved |
| kuch random baat jo intent mein nahi hai  | greet             | 0.895      | ⚠️ Misroute. Acceptable for C1; C6 LLM fallback + C7 thresholds will solve. |

**Known limitations carried forward**
- Out-of-scope sentences route to whichever intent has the most natural-language patterns (currently `greet`). To be solved in C6 + C7.
- Confidence values are top-1 cosine similarity. They are **not** per-intent calibrated yet; C7 introduces learned thresholds per intent based on user acceptance.
- Pickle index format works fine for our scale (<10k patterns). Switch to FAISS HNSW only if patterns ever exceed ~100k.

---

## Resume Protocol (read this if next session is fresh)

1. Open `BRAIN_BUILD_PLAN.md`. It is the source of truth for what to build.
2. Find the next 🔄 or ⏳ row above. Read that checkpoint's section in the plan.
3. Implement it. When done:
   - Mark the row ✅ with today's date.
   - Move the next row to 🔄.
   - Update **Currently Working On** to the next checkpoint.
   - Add a brief Validation Log section like the C1 one above.
4. If you discover the plan is wrong, **update the plan first**, then implement.
5. Don't skip checkpoints — they have ordering implied by the dependencies.

---

## Conventions

- File paths in tables and notes are relative to `New version- 3.0/`.
- Dates: `YYYY-MM-DD`.
- "Done" means: definition-of-done in the plan was met AND a smoke test was run AND no obvious regressions.
