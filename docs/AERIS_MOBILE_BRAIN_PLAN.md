# AERIS Mobile Brain — the plan

**Goal:** a model of our own, running **on the phone**, that
1. chats naturally in **English and Hinglish** (short, spoken-style answers),
2. understands commands with **very high accuracy** — the right action *and*
   the right details (contact, number, message, time, app…), and
3. knows **your** world — contacts, apps, preferences, past conversations —
   through on-device retrieval (RAG).

Trained by you on **Colab**; nothing is trained on this PC. Written 2026-10-17
after the first live test on the phone, where fixed patterns failed on natural
phrasing ("I want to do send a WhatsApp message on this number 7300 978845
hi" → contact "i want to do send a").

> **Status (2026-10-17, evening):** P1–P3 tooling is **built** in
> `aeris_brain/`: tool registry (37 tools), output contract and validator,
> template data factory (~630 English and Hinglish templates), 6 public-dataset
> converters (tested on real rows), teacher jobs with verifiers, quality
> pipeline, release-gate eval set (96 real-style items), scorer, DPO pairs,
> and 5 Colab notebooks (bake-off → dataset → SFT and Optuna → DPO/GRPO →
> GGUF export with a quantisation gate). 28 tests pass. **Next:** you run
> Phase 0 on the phone and notebooks 00 → 04 in Colab. Then Phase 4 (phone
> integration) is built against the winning model/runtime.

> **Status (2026-10-18):** Phase 0 done (Qwen3 1.7B Q4_K_M on llama.cpp CPU),
> dataset v1 built (265k), SFT v1 training in Colab. **Phase 4 is built** in
> `aeris_remote/lib/brain/`: Dart ports of the contract, prompt and grammar,
> pinned byte-for-byte to the Python pipeline by golden fixtures
> (`py -3.10 -m scripts.sync_app`); llama.cpp runtime via `llamadart` with
> greedy, grammar-constrained decoding and a persisted system-prompt KV cache;
> an executor for all 37 tools; phone-local memory; off / shadow / on modes
> with a decision log; a Brain screen for testing. **v2 prompt change to
> make:** move `Now:` and memory lines *below* the tool list, so they no longer
> break the cached prefix (the phone currently leaves them out).

---

## 0. Honest framing

- **This is a system, not one model.** "The brain" = a fine-tuned small LLM
  + a tool registry + on-device memory/RAG + guards + a cloud fallback. Most
  real-world assistant accuracy comes from the system around the model
  (constrained output, tool retrieval, verification), not from size alone.
- **Small models can be excellent at a narrow job.** Google ships a 270M
  model (FunctionGemma) purpose-built to be fine-tuned for phone actions, and
  the AndroidControl study found fine-tuned small models beat much larger
  zero-shot models *in domain*. The narrow job here — "your commands, your
  phone, your languages" — is exactly where fine-tuning wins.
- **Small models will not match Gemini at open-ended knowledge or
  reasoning.** The plan keeps a cloud escalation path for "explain quantum
  computing" and live-web questions; the on-device brain owns commands, chat,
  memory and anything private.
- **Data is the real project.** Training itself is a few Colab sessions; the
  data factory, evaluation sets and the retraining loop are where the months
  go. That's what most of this plan is about.

---

## 1. Targets (how we'll know it worked)

| Metric | Target v1 | Target v2 |
|---|---|---|
| Command **action** accuracy (held-out real utterances) | ≥ 97 % | ≥ 99 % |
| Command **exact match** (action + every argument) | ≥ 92 % | ≥ 97 % |
| "No tool needed" / "ask a clarifying question" correct | ≥ 92 % | ≥ 97 % |
| Valid structured output | 100 % (enforced by constrained decoding) | 100 % |
| Hinglish ↔ English: same command, same result | ≥ 95 % agreement | ≥ 98 % |
| Chat quality vs Gemini (blind side-by-side, your judgement) | ≥ 40 % win-or-tie | ≥ 55 % |
| Command latency, end of speech → action starts | ≤ 1.5 s | ≤ 0.8 s |
| Peak RAM while loaded | ≤ 3 GB | ≤ 2.5 GB |
| Works fully offline | commands + chat + memory | same |

"Held-out real utterances" = a test set built from **your own** phrasings,
never trained on (§6.6). Synthetic test sets flatter models; this one won't.

---

## 2. The hardware we're designing for

Measured over adb on 2026-10-17: **Realme RMX3741, MediaTek Dimensity 7050
(MT6877V), 12 GB RAM, Android 15**. That's 2× Cortex-A78 + 6× Cortex-A55,
a Mali-G68 GPU, and a MediaTek APU.

What that implies (to be **measured** in Phase 0, not assumed):
- 12 GB RAM comfortably holds a **1–4 B parameter model at 4-bit** (~1–2.5 GB)
  next to the app, STT and an embedding model.
- Published speeds are mostly from flagships: guides quote 5–15 tok/s for
  mid-range phones, ~10–20 tok/s for 1.5–2B models on 8 GB phones, and
  Gemma 4 E2B at ~47–52 tok/s on a Galaxy S26 Ultra. A Dimensity 7050 will
  be well below the flagship figures; the bake-off decides model size.
- A command needs only ~20–60 output tokens (a JSON call), so even
  10 tok/s ≈ 2–4 s worst-case → we'll also lean on **prefix caching** and
  short prompts. Chat replies stream, so first-token latency matters most.
- Phones throttle when hot: sustained speed drops as the device heats up.
  Long agent runs must budget for that.

---

## 3. Architecture

```
                     you speak / type
                            │
               Google STT (en-IN / en-US, per Language setting)
                            │
          ┌─────────────────┴──────────────────┐
          │ L0  instant patterns (exists today)│  "torch on", "volume up"
          │     exact, offline, ~0 ms          │  → run immediately
          └─────────────────┬──────────────────┘
                            │ anything not trivially certain
          ┌─────────────────┴──────────────────────────────────────┐
          │ L1  AERIS BRAIN  (fine-tuned small LLM, on-device)     │
          │                                                        │
          │  prompt = persona + retrieved tools + retrieved memory │
          │         + last turns + user text                       │
          │                                                        │
          │  output (constrained): ONE of                          │
          │   • tool_call {name, args}       → verify → execute    │
          │   • ask {question}               → clarify ("What      │
          │                                    should I tell Ravi?")│
          │   • reply {text}                 → speak (chat)        │
          │   • plan {steps}                 → phone agent         │
          │   • escalate {why}               → cloud (L3)          │
          └───────┬──────────────────────────────┬─────────────────┘
                  │                              │
   ┌──────────────┴─────────────┐   ┌────────────┴─────────────────┐
   │ L2  MEMORY / RAG (on-device)│   │ L3  CLOUD (optional)         │
   │  EmbeddingGemma / MiniLM    │   │  Gemini: web, hard questions │
   │  + sqlite-vec + BM25        │   │  only when L1 escalates or   │
   │  contacts · apps · facts ·  │   │  is unsure                   │
   │  chat summaries · notes ·   │   └──────────────────────────────┘
   │  tool docs                  │
   └─────────────────────────────┘
```

Key design decisions:

1. **One output contract.** The brain always emits one of five typed outputs
   (tool_call / ask / reply / plan / escalate). Constrained decoding (a JSON
   grammar) makes malformed output impossible — LiteRT-LM supports tool use
   with constrained decoding; llama.cpp has GBNF grammars.
2. **Tool retrieval.** With 60+ tools, putting every schema in every prompt
   makes a small model slower *and* less accurate. Retrieve the top ~8 tool
   schemas for the utterance (embedding search over tool descriptions),
   always including `reply` / `ask` / `escalate`.
3. **Verify before acting.** The model proposes; code checks. Contact must
   exist (or be a valid number), app must be installed, time must parse,
   messaging/payment actions follow the existing confirm + guard rules from
   the phone agent. A failed check becomes an `ask`, never a wrong action.
4. **Single source of truth for tools.** The Dart tool registry generates
   (a) the runtime schemas, (b) the training-data templates and (c) the eval
   coverage report. Add a skill once → it shows up in all three.
5. **Shadow mode first.** v1 runs *alongside* the current router: both
   decide, only the old path acts, disagreements are logged. The brain takes
   over per-tool once its logged accuracy clears the gate.

---

## 4. Choosing the model

You asked for option B, "a bit larger scaled". Candidates:

| Model | Size | Why consider it | Watch out for |
|---|---|---|---|
| **Gemma 4 E2B** | ~2B effective (≈1.3 GB Q4) | Built for phones; native structured tool use; runs on LiteRT-LM with GPU; audio + vision input | One developer saw number-formatting bugs in tool-call arguments on a Mali GPU (`2026` → `202026`) — must test on our Mali-G68 |
| **Gemma 4 E4B** | ~4B effective (≈2.5 GB Q4) | Reported considerably more reliable on complex tool schemas | ~2.5× slower than E2B; 4–5 GB RAM at runtime |
| **Qwen3 1.7B** | 1.7B | Strongest multilingual option at this size; Apache-2.0; easy Unsloth fine-tuning | Hinglish must come from our data |
| Qwen3 0.6B / FunctionGemma 270M | tiny | Ultra-fast command router | Can't carry real chat |
| Phi-4-mini | 3.8B | Smartest at usable speed on flagships | Likely too slow on a Dimensity 7050 |
| Llama 3.2 3B / SmolLM3 3B | 3B | Mature tooling | Weaker multilingual than Qwen3 |

**Recommendation:** run the **Phase 0 bake-off** on your actual phone between
**Gemma 4 E2B** and **Qwen3 1.7B** (with E4B as the "large" option if speed
allows). Pick by measured tok/s, RAM, and zero-shot accuracy on our eval set.
Ship **one base model + LoRA adapters** (flutter_gemma supports LoRA on
Android): a *command* adapter and a *chat* adapter on the same base, or one
merged adapter if the bake-off shows no interference.

### 4.1 Phase 0 results — measured on the RMX3741, 2026-10-17

Prompt: `aeris_brain/eval/bakeoff_prompt.txt` (real AERIS system prompt, ~685
tokens) + "I want to do send a WhatsApp message on this number 7300 978845 hi".
Memory read over adb (`dumpsys meminfo`); phone 35–39 °C, charging.

| Model · runtime | First answer | With cached instructions | Writing speed | RAM | Number copied right? |
|---|---|---|---|---|---|
| Gemma 4 E2B · LiteRT **GPU** (AI Edge Gallery) | 10.2–10.6 s total | — | fast | 2.6 GB | ❌ **corrupted both runs** ("7300 9788455", "730 7884555") — the reported Mali-GPU bug, reproduced |
| Gemma 4 E2B · LiteRT CPU | 51.4 s total | — | slow | 3.7 GB peak | ✅ exact |
| Qwen3 1.7B **Q8_0** · llama.cpp CPU (PocketPal) | 85 s to first token | 1.9 s | 1.7–2.6 tok/s | 2.6 GB | ✅ digits (put in `contact`) |
| **Qwen3 1.7B Q4_K_M** · llama.cpp CPU | 35.4 s to first token | **3.0 s** | **5.4–5.6 tok/s** | **1.7–1.8 GB** | ✅ digits (put in `contact`) |

Conclusions:
- **Base model for v1 = Qwen3 1.7B Q4_K_M on llama.cpp (CPU).** It's the
  only option that is correct, under 2 GB and usable: about 3 s to start
  once the instructions are cached, then about 5.5 tok/s, so a 25–40 token
  command answer finishes in about 8–10 s.
- **Prefix caching is mandatory.** 35 s → 3 s. The app must keep the
  system-prompt KV cache warm. Tool retrieval must not change the cached
  prefix: retrieved tools go AFTER the fixed part, or v1 uses a fixed tool
  list.
- **Gemma on the Mali GPU is ruled out** until LiteRT fixes the number
  corruption. Re-test on each LiteRT release, because it's ~5× faster.
- **Zero-shot errors seen (training targets):** number in `contact`
  instead of `number`; stray quotes (grammar fixes this); invented optional
  args (`days:"monday"`, `label:"Morning Alarm"`); time normalised
  ("07:00") instead of copied as a span; the trailing "AERIS" word swallowed
  into a contact name.
- **Zero-shot accuracy (notebook 00, Colab T4, no grammar, 2026-10-17):**

  | model | set | valid | decision | action | exact | arg F1 |
  |---|---|---|---|---|---|---|
  | Qwen3 1.7B | seed_real (96) | 67.7 | 53.1 | 49.3 | 22.5 | 0.559 |
  | Qwen3 1.7B | templated_test (400) | 73.7 | 60.4 | 51.3 | 27.6 | 0.544 |
  | Qwen3 0.6B | seed_real | 68.8 | 33.3 | 31.0 | 19.7 | 0.423 |
  | Qwen3 0.6B | templated_test | 69.0 | 32.4 | 23.1 | 10.3 | 0.282 |

  → **Train 1.7B.** 0.6B starts ~25 points behind on decisions. It's an
  optional later experiment, not the v1 base.
- **Next speed levers:** Qwen3 0.6B (about 3× faster decode) for commands,
  if notebook 00 shows its accuracy is close; shorter output keys; instant
  patterns for the most common commands; llama.cpp thread count (the 7050
  has only 2 big cores, so test 2 vs 4 threads).

## 5. Runtime on the phone

| Option | Package | Pros | Cons |
|---|---|---|---|
| **LiteRT-LM** | `flutter_gemma` (Google's docs point Flutter users to it) | GPU via OpenCL on Android, LoRA, constrained tool use, Gemma-native | `.litertlm` conversion step; NPU path is Qualcomm-focused (we're MediaTek) |
| **llama.cpp** | `llamadart` (GGUF; also wraps LiteRT-LM) | Any GGUF model (Qwen3, Gemma…), GBNF grammars, huge community | Android GPU (Vulkan) is experimental/opt-in → mostly CPU |

Phase 0 benchmarks both. The brain runs in a **background isolate** (never
the UI thread — today's ANR showed how little headroom the main thread has),
loads lazily, keeps the KV-cache prefix for the fixed system prompt, and
unloads after idle.

---

## 6. The data factory (the heart of the project)

Target scale for v1: **~300–500k training examples** total, deduplicated
and quality-filtered. Every example is stored once in a neutral JSONL format
and rendered into the chosen model's chat template at training time, so
switching base model never means rebuilding data.

### 6.1 Commands / tool calling (~55 % of the mix)

| Source | What it gives | Size | License / note |
|---|---|---|---|
| **Our template grammar** (generated from the Dart tool registry) | Every tool × phrasings × slot values, English + Hinglish | 100–200k | ours |
| **Google Mobile Actions** (FunctionGemma dataset) | Phone actions in exactly this tool-call shape | small | CC-BY-4.0 |
| **Hinglish-TOP** (Google Research) | 10k **human-annotated** code-switched parses + 170k generated (CST5) | 180k | open; human split reserved for eval |
| **MASSIVE** (Amazon) | 1M+ utterances, 51 languages, 60 intents, 55 slot types | map en-US + hi-IN subsets to our tools | CC-BY-4.0 |
| **xLAM function-calling-60k** (Salesforce APIGen) | General, execution-verified function calling | 60k | **CC-BY-NC — personal use only** |
| **When2Call** (NVIDIA) | When *not* to call a tool / when to ask | 10–100k + preference pairs | check card |
| **Glaive function-calling v2** | Varied tool schemas | ~100k | check card |

**Augmentation**, each tested against the eval set to see that it helps:
- **Speech-recognition noise:** dropped or merged words, homophones
  ("to"/"two", "WhatsApp"/"what's up"), numbers as words, spaced digits
  ("7300 978845").
- **Filler and politeness:** "I want to…", "can you…", "yaar zara…", "please".
- **Code-switching:** the same command in English, in Hinglish, and mixed.
- **Slot variety:** real Indian names (your contacts, opt-in, on Colab only),
  apps actually installed on your phone, times/dates in every spoken format.
- **Multi-intent and follow-ups:** "call Ravi … actually WhatsApp him instead".
- **Hard negatives:** questions that *look* like commands ("what is WhatsApp?").

### 6.2 Chat — English + Hinglish (~30 %)

There's no well-documented, large romanised-Hinglish chat dataset with clear
licensing (checked). Candidates to verify by hand:
`Sujalvc/hinglish-instruct-dataset` (~10k), `Shrijanagain/ST-x-R` (~986k,
Apache-2.0, card is promotional — inspect it), plus English instruction data
(SmolTalk / UltraChat subsets). The plan is to **build our own**: take good
English conversations → rewrite them in natural romanised Hinglish with an
**open-weight teacher model running in Colab**, then filter (§6.5). Everything
gets the AERIS persona: short, spoken, no markdown, friendly.

### 6.3 Memory- and RAG-grounded turns (~10 %)

Examples where the prompt contains retrieved facts and the answer must use
them correctly or say "I don't know": "what did I ask you to remember about
mom's birthday?", plus memory tools (`remember`, `recall`, `forget`).

### 6.4 Phone-agent steps (~5 % in v1, grows in Phase 7)

**AndroidControl** (14.5–15.3k tasks across 833 apps, with an **accessibility
tree for every screenshot**) maps almost directly onto our `dumpUi` format.
AITW (715k episodes) is screenshot-only and needs OCR — lower priority.

### 6.5 Where synthetic data comes from — read this

- **Don't train on Gemini outputs.** The Gemini API terms forbid using the
  service "to develop models that compete" with it. A personal assistant
  model is a grey area at best. So the agent traces logged from the current
  Gemini-driven agent are for *evaluation*, not training.
- **Use an open-weight teacher in Colab instead** (e.g. Qwen3 32B or Gemma
  3/4 27B in 4-bit) for paraphrasing, Hinglish rewriting and judging. Their
  licenses permit it, and the data is fully ours.
- **Quality pipeline:** normalise → exact + MinHash dedupe → **decontaminate
  against every eval set** → teacher-as-judge filter (drop low-scoring
  samples) → validate every tool call against the schema → balance per tool
  → render to the chat template.

### 6.6 Evaluation sets — never trained on

1. **Your real set:** 1–2k utterances you actually said, captured by the app's
   miss log (opt-in) plus a recording session. Hand-labelled; the
   2026-10-17 WhatsApp-number sentence is item #1.
2. The **Hinglish-TOP human test split** converted to our tools. There's
   already a 300-turn function-calling version on Hugging Face.
3. A **robustness suite:** the same commands with STT noise, fillers and
   code-switching.
4. A **no-call / clarify suite** (When2Call style).
5. A **chat set:** 200 prompts, blind A/B against Gemini, judged by you.

---

## 7. Training (Colab, run by you)

**Toolkit:** Unsloth (QLoRA). Its guides fit Qwen3 and Gemma 3 fine-tuning on
the free 16 GB T4, and its float16 path works around the T4's lack of bf16.

| Stage | What | Why |
|---|---|---|
| **S0 baseline** | Zero-shot eval of each candidate on §6.6 | Know the gap before spending GPU hours |
| **S1 SFT** | QLoRA on the full mix; loss on assistant tokens only; sequence packing | Learns the tools, the persona and Hinglish |
| **S2 preference** | DPO on call / ask / no-call pairs (When2Call + our hard negatives) | Fixes "acts when it should ask" and the reverse |
| **S3 RL (optional)** | GRPO with a **verifiable reward**: schema-valid + correct tool + correct args | The biggest remaining lever for exact-match accuracy |
| **S4 quantise + re-eval** | Export GGUF Q4_K_M / Q5 or `.litertlm` int4; re-run every eval | Gate: ≤ 1 point drop after quantisation |

**Hyperparameter search** (Optuna, on a 10–20 % data slice, short runs,
metric = dev exact-match + chat-judge score):

| Parameter | Search range | Starting point |
|---|---|---|
| learning rate | 5e-5 … 3e-4, cosine, 3–5 % warmup | 2e-4 |
| LoRA rank r | 16 / 32 / 64 / 128 | 32 |
| LoRA alpha | r … 2r | 2r |
| LoRA dropout | 0 … 0.05 | 0 |
| target modules | all linear layers | all linear |
| effective batch | 32 … 128 | 64 |
| epochs | 1 … 3 (early stop on dev) | 2 |
| max sequence | 1024 / 2048 | 2048 |
| data mix (tools / chat / RAG / agent) | ± 15 % around 55/30/10/5 | 55/30/10/5 |

**"Chunking" in training:**
- **Packing:** pack short examples to the max sequence length without
  attention leaking across examples.
- **Long conversations:** split into overlapping turn windows that always
  end on an assistant turn.
- **Never cut a tool call in half:** truncation only ever drops whole old
  turns.

**Colab realities:**
- Free T4 sessions disconnect. Checkpoint to Google Drive every ~200 steps;
  every notebook resumes from the last checkpoint.
- Track runs (TensorBoard/W&B in Drive) and **hash every dataset version**, so
  every model can be traced to the exact data it saw.
- 1.7–4B QLoRA fits a T4. A full hyperparameter sweep on 300k+ examples is
  far faster on a Colab Pro A100. Worth it for the sweep, not required for
  single runs.

---

## 8. RAG on the phone

| What gets indexed | How it's chunked | Refresh |
|---|---|---|
| Contacts (names, nicknames, relations) | 1 contact = 1 chunk | on change |
| Installed apps (label, package, what it's for) | 1 app = 1 chunk | daily |
| "Yaad rakho" facts | 1 fact = 1 chunk, with timestamp | on write |
| Conversation memory | rolling **summary per session**, not raw turns | session end |
| Notes / documents you share with AERIS | recursive split by headings and paragraphs, ~256 tokens, ~15 % overlap, with metadata | on add |
| Tool descriptions (for tool retrieval, §3) | 1 tool = 1 chunk | each build |

**Stack:**
- **Embeddings:** EmbeddingGemma, reported to run in under 200 MB of RAM when
  quantised. Its Matryoshka dimensions (768/512/256/128) let us store 256-d
  vectors to save space. MiniLM is the lighter fallback.
- **Storage and search:** sqlite-vec, plus SQLite FTS5 (BM25) for hybrid
  search, so exact names like "Ravi" win over fuzzy matches.
- **Ranking:** a light recency boost.
- **Prompt budget:** ≤ 600 tokens of retrieved context.

Google's AI Edge RAG SDK for Android is the reference design. We'd wrap the
same idea for Flutter.

---

## 9. The learning loop (how it keeps improving)

```
use AERIS → brain unsure / you correct it / Gemini fallback disagrees
        → saved locally in a "misses" list (opt-in, on the phone)
        → you review it in an in-app screen (keep / fix label / discard)
        → export JSONL → add to dataset vN+1 → retrain in Colab
        → re-run ALL evals → release only if no metric regresses
```

---

## 10. Roadmap

| Phase | What | Output | Effort |
|---|---|---|---|
| **P0 Bake-off** | Benchmark Gemma 4 E2B / E4B / Qwen3 1.7B on your phone via both runtimes | tok/s, RAM, zero-shot accuracy table → base model + runtime chosen | ~1 week |
| **P1 Contract** | Tool registry v1 (~60 tools), the 5-way output contract, eval sets §6.6 | `brain_tools.json`, eval JSONLs, scoring script | 1–2 weeks |
| **P2 Data factory** | Generators, converters (Hinglish-TOP, MASSIVE, Mobile Actions…), teacher notebook, quality pipeline | dataset v1 (300–500k) + data card | 3–4 weeks |
| **P3 Train v1** | S0 → S1 + hyperparameter sweep → S4 | adapter v1 + eval report | 2 weeks (your Colab time) |
| **P4 Integrate** | Background-isolate runtime, constrained decoding, verification, **shadow mode**, latency HUD | brain running beside today's router | 2 weeks |
| **P5 Memory/RAG** | Embeddings + sqlite-vec + hybrid search + tool retrieval | grounded answers, memory tools | 2–3 weeks |
| **P6 Train v2** | Misses from shadow mode + S2 DPO + S3 GRPO | exact-match ≥ 97 % | 3 weeks |
| **P7 On-device agent** | AndroidControl + our traces → agent steps on-device (Gemini stays as fallback) | multi-step tasks without cloud | 4–6 weeks |
| **P8 Continuous** | Monthly retrain from reviewed misses; regression-gated releases | keeps getting better at *you* | ongoing |
| **P9 (stretch)** | Speech straight into the model (Gemma 4 E2B/E4B accept audio) to skip the STT step | lower latency, better Hinglish | research |

Roughly **4–6 months** of focused work to v2, which is the "wholesome
achievement". Every phase ships something usable on its own.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Phone too slow for the chosen size | P0 measures before any training; fall back to E2B / 1.7B; prefix cache; short prompts |
| Model invents arguments (wrong contact / number) | Constrained decoding + code verification (§3.3) + `ask` instead of guessing |
| Not enough real Hinglish data | Hinglish-TOP human data + open-teacher rewriting + your own logged utterances |
| Training on outputs we're not allowed to use | Open-weight teachers only (§6.5); xLAM kept to personal / non-commercial use |
| Colab disconnects lose work | Drive checkpoints, resumable notebooks, dataset hashing |
| Tuned for synthetic data, fails on real speech | Your real set (§6.6.1) is the release gate, not the synthetic dev set |
| Phone heat during long agent runs | Step caps already exist; adaptive pacing; prefer E2B for agent steps |
| Mali GPU kernel bugs (reported number corruption) | Bake-off includes number-heavy tests; CPU fallback per model |

---

## 12. Decisions for you

1. **Model "scale":** do you accept the bake-off deciding between ~2B (fast)
   and ~4B (smarter, slower), or do you want 4B regardless of speed?
2. **Colab tier:** free T4 only, or Colab Pro for the hyperparameter sweeps?
3. **Your data:** may the data generator use your real contact names and
   installed-app list (processed in Colab, never uploaded anywhere else)?
4. **Cloud fallback:** keep Gemini for web and hard questions, or go fully
   offline?
5. **Personal-use licenses:** OK to use non-commercial datasets like xLAM,
   given AERIS is personal?

## 13. What happens at max effort (next session)

1. P0 bake-off kit: an in-app benchmark screen (loads a model, runs the
   eval set, reports tok/s, RAM and accuracy) plus the download steps.
2. P1 tool registry generated from the Dart skills, the output contract, and
   the eval sets (seeded with today's real failures).
3. P2 data factory: generators, dataset converters, the Colab teacher
   notebook, the quality pipeline and the data card.
4. P3 Colab training notebook: Unsloth QLoRA, Optuna sweep, Drive
   checkpoints, export + post-quantisation re-eval.

---

### Sources

- Models & speeds: [Cactus — best on-device LLM framework 2026](https://cactuscompute.com/compare/best-on-device-llm-framework) · [DEV — LLMs locally on Android 2026](https://dev.to/alichherawalla/how-to-run-llms-locally-on-your-android-phone-in-2026-no-cloud-no-account-2cd1) · [PromptQuorum — Phi-4 Mini vs Gemma 3 vs SmolLM](https://www.promptquorum.com/power-local-llm/mobile-llm-models-phi4-gemma-smollm) · [PromptQuorum — Android local LLM apps 2026](https://www.promptquorum.com/power-local-llm/best-local-llm-apps-android-2026) · [distil labs — on-device inference 2026](https://www.distillabs.ai/learn/on-device-llm-inference-in-2026/) · [MobileLLM-R1 (arXiv)](https://arxiv.org/pdf/2509.24945)
- Gemma 4: [LiteRT-LM overview](https://developers.google.com/edge/litert-lm/overview) · [Gemma 4 E2B on Mali GPU — tool-calling eval (forum)](https://discuss.ai.google.dev/t/gemma-4-e2b-litert-lm-0-10-x-on-mali-gpu-patterns-from-a-structured-tool-calling-eval/143976) · [MindStudio — E2B vs E4B on phones](https://www.mindstudio.ai/blog/gemma-4-e2b-vs-e4b-edge-models-audio-vision-phone) · [MindStudio — Gemma 4 edge deployment](https://www.mindstudio.ai/blog/gemma-4-edge-deployment-e2b-e4b-models) · [iTechGuides — Gemma 4 on Android](https://www.itechguides.com/gemma-4-on-mobile-which-model-to-load-e2b-vs-e4b-and-how-to-integrate-it-on-android/) · [Gemma 4 E2B litert-lm (HF)](https://huggingface.co/huggingworld/gemma-4-E2B-it-litert-lm)
- FunctionGemma / Mobile Actions: [Google — fine-tune FunctionGemma for Mobile Actions](https://ai.google.dev/gemma/docs/mobile-actions) · [Mobile-Action dataset card (HF)](https://huggingface.co/datasets/AliRGHZ/Mobile-Action/blob/main/README.md)
- Flutter runtimes: [LiteRT-LM on Flutter (flutter_gemma)](https://developers.google.com/edge/litert-lm/flutter) · [llamadart](https://pub.dev/documentation/llamadart/0.12.1/) · [flutter_gemma_litertlm](https://pub.dev/documentation/flutter_gemma_litertlm/1.3.0/)
- Hinglish / intent data: [Hinglish-TOP (Google Research)](https://github.com/google-research-datasets/Hinglish-TOP-Dataset) · [hinglish-fc-test (HF)](https://huggingface.co/datasets/MukulVashistha/hinglish-fc-test) · [MASSIVE (HF)](https://huggingface.co/datasets/qanastek/MASSIVE) · [L3Cube HingCorpus (arXiv)](https://arxiv.org/pdf/2204.08398) · [Hinglish TOP (Kaggle)](https://www.kaggle.com/datasets/nexuswho/hinglish-top-dataset) · [MT for multilingual intent detection (ACL)](https://aclanthology.org/2022.mmnlu-1.8.pdf)
- Hinglish chat: [Airavata (arXiv)](https://arxiv.org/pdf/2401.15006) · [Sample-efficient Hinglish conversational AI (arXiv)](https://arxiv.org/pdf/2504.19070) · [ST-x-R (HF)](https://huggingface.co/datasets/Shrijanagain/ST-x-R/blob/main/README.md) · [hinglish-bench (HF)](https://huggingface.co/datasets/saidutta69/hinglish-bench) · [Sujalvc datasets (HF)](https://huggingface.co/Sujalvc/datasets)
- Function-calling data: [ToolACE (ICLR 2025)](https://www.iclr.cc/virtual/2025/poster/30779) · [When2Call (HF)](https://huggingface.co/datasets/nvidia/When2Call/tree/main/train) · [ToolMind open datasets mirror (HF)](https://huggingface.co/datasets/Nanbeige/ToolMind/tree/main/open_datasets) · [APIGen-MT](https://github.com/apigen-mt/apigen-mt.github.io) · [xLAM-2 (HF)](https://huggingface.co/Salesforce/xLAM-2-32b-fc-r)
- Fine-tuning: [Qwen docs — Unsloth](https://qwen.readthedocs.io/en/latest/training/unsloth.html) · [Towards AI — Unsloth free-tier](https://pub.towardsai.net/unsloth-just-made-fine-tuning-llms-a-free-tier-task-9ce05a931b75) · [Codecademy — Gemma 270M with Unsloth + QLoRA](https://www.codecademy.com/article/how-to-fine-tune-google-gemma-270m-with-unsloth-and-qlora)
- RAG: [Google AI Edge RAG for Android](https://ai.google.dev/edge/mediapipe/solutions/genai/rag/android?hl=en) · [On-device RAG with Gemma (Medium)](https://medium.com/google-developer-experts/develop-an-on-device-rag-system-powered-by-gemma-models-f7cdb7bca221) · [Margelo — RAG in your pocket](https://margelo.com/blog/fitting-RAG-in-your-pocket/llms.txt) · [flutter_edge_ai_rag](https://pub.dev/packages/flutter_edge_ai_rag)
- Phone-agent data: [AITW (arXiv)](https://arxiv.org/pdf/2307.10088) · [AndroidControl — data scale for UI agents (arXiv)](https://arxiv.org/pdf/2406.03679) · [Lightweight Neural App Control (arXiv)](https://arxiv.org/pdf/2410.17883)
- Terms: [Gemini API Additional Terms (mirror)](https://open.windriver.com/info/uni-license-list/licenses/gemini-api-additional-tos-2025.html) · [Simon Willison on Gemini terms](https://feeds.simonwillison.net/2024/Oct/17/gemini-terms-of-service/)
