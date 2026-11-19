# AERIS Brain v2: a model that chats, understands and remembers

*2026-11-17.* v1 learned commands well but had almost no conversation (~3 % chat). It
had no explicit understanding output and no memory skill. v2 keeps the same base
model (Qwen3-1.7B, offline on the phone) and the same free-Colab budget, and trains
**one model with three jobs**. Each job is selected by its system prompt, so the phone
runs a single GGUF.

| head | input | output | used for |
|---|---|---|---|
| **TURN** | chat so far (+ remembered facts) | the 5-type contract: `reply` / `tool_call` / `ask` / `plan` / `escalate` | every turn |
| **NLU** | one message | `{intent, act, slots, keywords, lang, sentiment, emotion}` | routing, mood-aware replies, analytics, logs |
| **MEMORY** | recent user turns | `{"facts": [...]}`: lasting facts, in the user's own words | the "yaad rakho" store |

The label sets are fixed in `brain/nlu.py`:

- **Intents** (56): 37 tools plus 19 chat intents (`chat.smalltalk`, `chat.joke`, `question.live_info`, `request.unsupported`, …).
- **Acts:** 8.
- **Sentiments:** 3.
- **Emotions:** 12.
- **Language labels:** `english`, `hinglish`, `hindi_roman`, `devanagari`.

## Where the data comes from

| source | what | how it stays correct |
|---|---|---|
| templates (`brain/generate.py`) | commands, multi-call, ask, plan, escalate | grammar-generated, exact by construction |
| Hinglish-TOP, MASSIVE, Mobile Actions, When2Call | human-written commands, "when *not* to call a tool" | converters + contract validation |
| **teacher chat** (`01b_teacher_chat`) | real conversations: 1–4 turns, reply or escalate | Qwen3-8B (Apache-2.0, open weights) + strict verifiers |
| memory (`brain/memory_data.py`) | answers that use remembered facts, honest "aapne bataya nahi", fact extraction | facts are byte-exact spans of what the user said |
| NLU (`brain/build_v2.py nlu`) | understanding labels | exact for commands (derived from the tool call); checked label sets for chat |

The teacher is never Gemini or GPT. Their terms forbid training competing models.
GPT-generated public sets such as Hinglish-Everyday-Conversations are used for **evaluation
only**, never for training.

## How bias and repetition are kept out

The sampler is designed to avoid bias, and the audit **measures** the result instead of trusting the design.

**By construction (`brain/diversity.py`, `brain/langmix.py`):**

- **Diversity grid:** every teacher conversation gets its own cell, made of:
  - a persona used once (age × city × job × interest);
  - one of 40 topics;
  - a register (aap / tum / yaar / English);
  - a code-mix level (English → English-heavy → balanced → Hindi-heavy);
  - a mood and a length.

  The cells cycle evenly, so no combination dominates.
- **Names:** balanced by gender × region × community (North, South, East, West, Northeast, Central; Hindu, Muslim, Sikh, Christian, Parsi, tribal). The template contact pool was extended with the same list after the audit showed it leaned North/West.
- **Typed Hinglish:** real spelling variation (`kya/kia`, `nahi/nhi/nai`, `hai/h`, `kar do/krdo`, …) applied *outside* labelled spans, so slots stay exact.
- **NLU balance:** at most 260 examples per intent, so `flashlight` can't drown `set_language`.
- **AERIS is male, always:**
  - verifiers reject "rahi hoon" / "karti hoon" forms;
  - verifiers reject Devanagari, markdown, emoji and long replies;
  - memory facts must be copied word for word, and rephrased facts are dropped.

**Measured (`brain/audit.py`, run as a gate in notebook 01):**

| check | limit |
|---|---|
| biggest intent share | ≤ 8 % |
| biggest / smallest intent | ≤ 60× |
| intent entropy (normalised) | ≥ 0.80 |
| each code-mix bucket | ≥ 4 % of user turns |
| any gender among recognised names | ≤ 65 % |
| distinct-2 of user turns | ≥ 0.25 |
| most common user trigram | ≤ 2 % of turns |
| exact duplicate records | ≤ 1 % |
| feminine / Devanagari AERIS replies | 0 |
| mean reply length | ≤ 28 words |

A local dry run (templates + memory + NLU, **without** teacher chat) measured:

- 42 intents, entropy 0.998, max/min 1.7×;
- English 49 % / Hinglish 48 % / Hindi-roman 3 %;
- names 44 % m / 38 % f / 18 % unisex, across all six regions;
- 0 feminine replies;
- duplicates 0.7 %.

The only failure was distinct-2 at 0.218. That's expected: the varied teacher conversations
make up 30 % of the real mix and were missing from the dry run. If the gate still fails after
01b has run, generate more cells. Don't train past it.

## The 40k mix (free T4, ~4–6 h for one epoch)

`brain/build_v2.MIX_V2`:

| share | source |
|---|---|
| 27 % | template commands |
| 6 % | Hinglish-TOP |
| 3 % | MASSIVE |
| 1 % | Mobile Actions |
| 3 % | When2Call |
| **30 %** | **teacher chat** |
| 6 % | memory answers |
| 17 % | NLU |
| 7 % | memory extraction |

## Run order (you run these; nothing trains automatically)

1. `py -m scripts.pack` → upload `dist/aeris_brain_code.zip` to `MyDrive/mobile aeris/`.
2. **`01b_teacher_chat`** on a T4, in a fresh session. It generates 12k cells, 500 per Drive chunk, and resumes after a disconnect. Read the samples it prints.
3. **`01_build_dataset`** on CPU. It mixes 40k examples and runs the audit gate.
4. **`02_train_sft`** on a T4. It trains all three heads, then scores:
   - TURN with the existing metrics;
   - NLU: intent / act / emotion accuracy, slot F1, keyword F1;
   - MEMORY: precision / recall / F1, plus the **false-memory rate**, which must stay low or memory can't be trusted.
5. `03_preference` (optional), then `04_export` → GGUF for the phone.

## Files

- `brain/langmix.py`: code-mix index, language label, typed-spelling variation.
- `brain/diversity.py`: names, personas, topics, registers, the grid.
- `brain/nlu.py`: label sets, NLU/MEMORY record builders and validators, prompts.
- `brain/memory_data.py`: memory answers and extraction data.
- `brain/teacher.py`: `chat_grid_jobs`, the teacher prompt and verifiers.
- `brain/build_v2.py`: balanced NLU, teacher split, the v2 mix.
- `brain/audit.py`: bias/variety report and gate.
- `brain/score_v2.py`: NLU/MEMORY scoring.
- `notebooks/src/01b_teacher_chat.py`, `01_build_dataset.py`, `02_train_sft.py` (`py -m scripts.py2nb` builds the `.ipynb` files).
- `tests/test_brain_v2.py`: 16 tests, including a simulated teacher response for each verifier path.

## Next, after training

App integration: run the GGUF on the phone through llama.cpp (llamadart). Keep the rule
router as the instant path and have the brain take over when the router is unsure, for chat
and for NLU/memory in the background.
