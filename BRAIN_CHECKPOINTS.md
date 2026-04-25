# JARVIS BRAIN — CHECKPOINT TRACKER

> Single source of truth for build progress. **Read this first** when resuming.
> Detailed spec for each checkpoint lives in `BRAIN_BUILD_PLAN.md`.

**Status legend:** ⏳ Pending  ·  🔄 In Progress  ·  ✅ Done  ·  ⚠️ Blocked

---

## Progress

| ID  | Checkpoint                              | Status | Date       | Notes |
|-----|-----------------------------------------|--------|------------|-------|
| C1  | Multilingual brain core (k-NN + encoder)| ✅ Done | 2026-04-25 | Index built, cached, 9-sample smoke passed. See "C1 Validation" below. |
| C2  | Layered entity extractor                | 🔄 In Progress | 2026-04-25 | Next chunk. |
| C3  | Sentiment analysis                      | ⏳ Pending |        |       |
| C4  | User memory (long-term facts)           | ⏳ Pending |        |       |
| C5  | Conversation context (short-term)       | ⏳ Pending |        |       |
| C6  | Chit-chat LLM via Ollama                | ⏳ Pending |        | Will catch the "random talk → greet" misroute observed in C1. |
| C7  | Reward-shaped continual learning        | ⏳ Pending |        | This is the "RL" piece, done as contextual bandit per intent. |
| C8  | Disambiguation                          | ⏳ Pending |        |       |
| C9  | Main engine rewire                      | ⏳ Pending |        | Removes the legacy `predict_intent()` shim from `brain.py`. |
| C10 | Executor extensions                     | ⏳ Pending |        |       |
| C11 | Tests                                   | ⏳ Pending |        |       |
| C12 | STT/TTS local upgrade                   | ⏳ Pending |        | Defer to last. |

---

## Currently Working On

**C2 — Layered Entity Extractor**
- New file: `core/entity_extractor.py`
- Layers: regex → gazetteer (existing `entities.json`) → spaCy NER → residual span
- Wires into `main_engine.py` so entities are filled before slot-filling triggers
- Adds `spacy` to `requirements.txt`; user must run `python -m spacy download en_core_web_sm`

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
