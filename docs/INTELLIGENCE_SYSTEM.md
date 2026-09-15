# AERIS Intelligence System — full design (v2.1, 2026-07-19)

*Ye document AERIS ke poore "dimag" ka blueprint hai: routing stack,
self-learning flywheel, generation lineage, health monitoring, aur
operating manual. `docs/INCREMENTAL_TRAINING.md` quick workflow hai;
ye us ke neeche ka poora design.*

---

## 1. The routing stack (utterance → action)

Har bola/typed hua sentence in layers se guzarta hai — fastest aur
sabse certain layer pehle:

```
 utterance
    │
 1. HinglishNormalizer          spelling/case/particle canonicalisation
    │
 2. Prediction LRU cache        repeated phrases: 0 ms (brain.py, 256 entries)
    │
 3. EXACT-MATCH fast path       verbatim corpus pattern → conf 1.0, no model
    │
 4. NEURAL router               fine-tuned DistilBERT-multilingual, 396 intents
    │   (sirf jab hash valid)   ~41 ms/query CPU · softmax confidence
    │
 5. k-NN fallback               frozen sentence-encoder + cosine — hamesha
    │                           loaded; neural unsure (<0.55) ya absent hone par
    │
 6. Per-intent threshold        feedback bandit (feedback.py EMA) decide karta
    │                           hai: execute / disambiguate / chat
    │
 7. Disambiguator / chat gate   top-3 tie → poochho; koi intent nahi → LLM chat
    │
 8. Executor → skill            396 intents, ek owner per phrase (guard test)
```

Design rule: **upar ki layer confident ho to neeche wali kabhi override
nahi karti.** Exact match neural ko overrule karta hai (freshly-taught
pattern turant kaam kare); neural k-NN ko sirf tab defer karta hai jab
khud unsure ho.

## 2. The data flywheel (system smarter kaise hota hai)

```
                    ┌──────────────────────────────────────────┐
                    ▼                                          │
   use AERIS ──► feedback.py logs ──► learning_loop harvest ───┤
   (roz ka kaam)  every utterance      corrections = GOLD      │
                  + outcome            accepted    = positive   │
                    │                  conf<0.60   = review     │
                    │                                          │
                    ▼                                          │
             brain_health.py                        learned_patterns.json
             score / trend / advisor                     │
                    │                                    ▼
                    │                        intent_loader merge (canonical)
                    │                         ├─► k-NN + exact (turant)
                    ▼                         └─► trainer corpus (retrain par)
             "retrain due" ──► python -m core.retrain
                                   │ incremental warm-start (gen N → N+1)
                                   │ golden gate (95 held-out items)
                                   │ promote / archive / rollback
                                   ▼
                              smarter model ──► (loop repeats)
```

Ek hi canonical merge point hai — `intent_loader.load_all_intents()`:
intents.json + skill patterns + learned patterns + user patterns. Trainer,
k-NN, exact-match, hash — sab isi se nikalte hain, isliye kabhi divergence
nahi hota.

## 3. Generations & lineage

- Har promoted model ek **generation** hai (`metadata.json` mein number,
  `data/models/train_history.json` mein poori lineage).
- **Incremental by default**: naya training pichhle generation ke weights
  se warm-start hota hai. Classification head **intent-NAME se remap**
  hota hai — purane intents apni seekhi hui rows rakhte hain, naye
  intents ko fresh rows (proof: `tests/test_incremental_training.py`).
- Har generation ke saath **corpus_snapshot.json + learned_snapshot.json**
  save hote hain — koi bhi generation baad mein exactly reproduce ho
  sakta hai chahe corpus evolve ho chuka ho.
- **Staging → gate → promote**: training kabhi live dir ko directly nahi
  chhooti. Golden gate fail → staging mein ruk jaata hai, live untouched.
  Archive last 2 generations rakhta hai; `rollback` one command.

## 4. Evaluation — "smarter" ka proof

- **Golden set** (`data/intent_eval.json`): 95 held-out Hinglish
  paraphrases jo kabhi training mein nahi jaate. Twin intents (get_time/
  current_time, shutdown_pc/shutdown_system...) `also_ok` se handle.
- **Gate rule**: naya model, purane model ke known-intents subset par,
  2pt margin ke andar girna nahi chahiye. Naye intents purane model ke
  khilaaf count nahi hote (fair comparison).
- **Baselines (2026-07-19, gen-1 model)**: val 73.8% · golden **82.1%** ·
  41 ms/query CPU. Har retrain ke baad `python -m core.intent_eval
  compare` + train_history trend se progress dikhta hai.
- **Quantization — evaluated & REJECTED**: int8 dynamic quantization ne
  2.4x speed di (41→17 ms) par golden −3.2 pts (82.1→78.9%). Router mein
  latency bottleneck nahi hai, accuracy hai — isliye fp32 hi rahega.
  (Golden set ka pehla concrete save yehi tha.)

## 5. Self-monitoring (brain_health)

`python -m core.brain_health` / voice: **"brain health"**

- **health_score 0-100** = 50% acceptance rate + 25% golden acc +
  15% neural-active + 10% (1 − correction rate); jo component missing
  ho uska weight renormalise.
- Confusion pairs (model ne X kaha, user ne Y karaya), correction
  hotspots, low-confidence intents (avg <0.65), chat-fallback rate.
- **Retrain advisor** — 3 triggers: hash drift (k-NN fallback), ≥15 naye
  learned samples, correction spike. Boot par bhi drift + pending
  samples log hote hain (brain.py).
- Har report `data/report_card/brain_health_*.json` mein.

## 6. Safety rails (kyun ye kabhi khud ko kharab nahi karega)

| Rail | Mechanism |
|---|---|
| Bad retrain live nahi jaata | staging + golden gate + margin |
| Model kho nahi sakta | archive (2 gens) + `rollback` |
| Poison data corpus mein nahi ghusta | corrections=gold; accepted conf≥0.60; baaki review queue; reject CLI |
| Stale model galat answers nahi deta | intents-hash check → k-NN fallback |
| Ek phrase do maalik nahi | test_pattern_collisions guard |
| Training kabhi auto nahi chalti | retrain sirf explicit CLI ritual hai (voice skills read-only) |
| Reproducibility | per-generation corpus/learned snapshots |
| Crash-safe writes | atomic_io everywhere (learned store, history, cards) |

## 7. Operating manual (Shivang ke commands)

Roz: bas AERIS use karo. Kabhi kabhi:

```
"kya seekha tumne"  /  "brain health"      # voice se status
python -m core.retrain --dry-run           # plan dekho
python -m core.retrain                     # poora ritual: harvest→train→gate→promote
python -m core.retrain --colab             # GPU chahiye to bundle + steps
python -m core.model_registry rollback     # naya model pasand nahi aaya
python -m core.learning_loop reject "..."  # galat seekha hua phrase hatao
```

AERIS chalte hue retrain karoge to pipeline khud stage-only kar dega
(model files locked hoti hain) aur promote ka command bata dega.

## 8. The agentic layer (v2.1 — ab LIVE on embedded Qwen)

Pehle embedded backend par tool-calling hard-disabled thi (1.5B ka free-form
JSON unreliable tha) — matlab is laptop par multi-step commands mar jaate
the. v2.1 ne use teen tarkeebo se zinda kiya, aur live verify hua:

1. **Grammar-constrained JSON** — `local_llm.chat_json()` llama.cpp ke
   `response_format=json_object` se sampler ko non-JSON dena hi impossible
   bana deta hai (purane llama-cpp builds par graceful fallback).
2. **Tool selection** (`core/tool_select.py`) — ~400 tools ka poora menu
   nahi; intent-brain ka top-3 + token overlap (+ Hinglish→English hint
   map: "bhejo"→send, "bajao"→play…) se ≤12 relevant tools. Har agent turn
   par query = goal + latest observation, to menu plan ke saath adapt hota
   hai.
3. **Tight prompts + guards** — 2048-token budget: chhota system block,
   observations 220 chars, scratchpad tail 6 steps; "final se pehle GOAL
   re-check karo" rule adhoore chains rokta hai. Orchestrator ke apne
   guards (step budget, loop detection, reflection nudge) upar se.

Live-verified chains (real Qwen, canned tools):
  * "aaj ka weather check karke note me save karo" → get_weather →
    create_note(weather text) → final ✓
  * "screenshot le aur phone pe bhej do" → take_screenshot →
    image_to_phone(observed path) → final ✓
  * "notepad kholo aur volume mute karo" → open_app → volume_mute ✓

Confirm flow ab poora hai: gate "confirm" par run PARK hota hai, trace
**goal store mein persist** hota hai (`_park_agent_run`), user ka "haan"
`goal_system.advance(approve_last=True)` se wahi run resume karta hai —
"cancel" drop. Kill-switch: settings `agent_embedded false`.

Multistep trigger (fallback ke andar): " aur phir ", " uske baad ",
" karke ", " kar ke ", " then "… — confident single commands classifier
se hi nikal jaate hain, ye sirf unmatched utterances par lagta hai.

## 9. Roadmap (agla next-level)

1. ~~Auto-review via LLM~~ ✅ v2.1: `python -m core.learning_loop
   review-ai` — Qwen suggestion, final word user ka.
2. ~~Nightly health cron + retrain nudge~~ ✅ v2.1: nightly `__eval__` ke
   saath brain_health card; initiative source `retrain_due` (24h throttle,
   OFFER band — kabhi autonomous act nahi).
3. **Gen-2 retrain abhi bhi pending**: `python -m core.retrain` (ya
   `--colab`).
4. **Agent golden tasks**: naye chains (weather→note, screenshot→phone) ko
   tests/golden JSON mein scripted-LLM ke saath pin karna.
5. **Confusion-driven golden growth**: har naya confusion pair golden set
   mein 1-2 held-out items add kare (manually curated).
6. **Autonomous-year tie-in**: health_score ko L3→L4 autonomy gate ke
   report card mein feed karna (docs/AERIS_AUTONOMOUS_YEAR_PLAN.md).

## 10. File map

| Path | Role |
|---|---|
| `core/brain.py` | routing stack orchestration (layers 2-5) |
| `core/tool_select.py` | ≤12-tool relevance menu for the embedded agent |
| `core/local_llm.py` | embedded Qwen + grammar-constrained `chat_json` |
| `core/llm_chat.py` | chat + embedded tool/agent turns (compact prompts) |
| `core/agent_orchestrator.py` | ReAct loop (budget/loop/reflection guards) |
| `core/goal_system.py` | parked goals + "haan" resume (approve_last) |
| `core/intent_model.py` | neural router inference |
| `core/intent_classifier.py` | k-NN + exact match |
| `core/intent_loader.py` | THE canonical corpus merge |
| `core/feedback.py` | outcome logging + bandit thresholds |
| `core/learning_loop.py` | harvest + learned store + curation CLI |
| `core/train_intent.py` | incremental trainer + gate + promote |
| `core/model_registry.py` | staging/promote/archive/rollback/lineage |
| `core/intent_eval.py` | golden evaluator + gate |
| `core/brain_health.py` | self-monitoring + advisor |
| `core/retrain.py` | one-command pipeline (+ --colab bundle) |
| `skills/learning_skill.py` | voice: learning_status + brain_health |
| `data/intent_eval.json` | 95 golden items (NEVER train on these) |
| `data/learned_patterns.json` | harvested knowledge |
| `data/models/train_history.json` | generation lineage |
