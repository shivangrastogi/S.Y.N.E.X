# AERIS — Self-Awakening, Self-Learning Agent: Full Blueprint

Complete engineering blueprint for evolving AERIS into a **self-awakening,
continuously self-learning agent** that learns from *use, feedback, its own
outcomes, and its surroundings*. Contains: research grounding, wireframes,
black-box specs, system diagrams, and a month-by-month plan.

> **Honesty first.** "Consciousness" here is an *engineering target*, not a claim
> of sentience. We build the observable properties that make a system feel like a
> mind — continuity, self-model, initiative, reflection, and self-improvement —
> using real, testable components. Nobody can build literal subjective experience,
> and pretending otherwise would be dishonest. What we CAN build is genuinely
> powerful, and it's specified precisely below.

---

## Part 0 — The wake-word fix (the "sunta nahi" bug)

**Symptom:** after the false-wake retune, saying "Aeris" stopped registering.

**Root cause:** the v1 fix used a *fixed* VAD floor (`rms ≥ 0.012`) to gate the
AGC. But this phone runs hardware noise-suppression, so its genuine speech frames
often sit **below** that constant — the AGC never engaged, and combined with the
hotter threshold the spotter went effectively deaf. A fixed constant can't work
across devices/mics/rooms.

**Fix (two-stage wake, shipped 2026-07-12):**
- **Stage 1 — sensitive detector + *adaptive* noise floor.** The AGC now gates on
  `rms > voicedFloor`, where `voicedFloor` tracks an EMA of the room's actual
  ambient level. A steady fan raises the floor to itself (so it's never "voiced");
  real speech still clears it on any device. Threshold back to the sensitive,
  July-11 live-verified zone (balanced 0.16/2.6).
- **Stage 2 — speech-plausibility check.** On any keyword hit, the last ~1.5 s
  must look like *bursty, voiced* audio (voiced-ratio ≥ 0.2 **and** peak ≫ median).
  Stationary hiss the model hallucinated on fails; a real utterance passes.
- Offline-validated: 5/5 genuine hits pass stage-2, synthetic hiss is rejected,
  "hello world" stays clean.

**The durable cure is still A6 — a personal wake model on your voice.** Two-stage
buys reliability now; your own recordings make it rock-solid. See Part 4, Month 1.

---

## Part 1 — Research grounding (what a self-learning agent actually needs)

Cognitive science models "functional consciousness" (what a mind *does*, not what
it *feels*) as a handful of measurable properties. We anchor to the ones with real
theory behind them and map each to a mechanism + existing AERIS code:

- **Global Workspace Theory (Baars, Dehaene)** — a mind has a "broadcast stage":
  many processes compete, the *salient* one wins attention and is broadcast to the
  rest. → our **Initiative/Salience Engine** (Q2·M5) is exactly this stage.
- **Predictive processing (Clark, Friston)** — a mind constantly predicts its input
  and learns from *surprise* (prediction error). → the **World-Model** emits a
  surprise signal that drives learning loop 1.
- **Two functional pillars on top:** **Wakefulness** (self-awakening: dormant ↔ awake
  ↔ proactive — our wake service + state machine, §4.3) and **Attention** (act on the
  *matlab-ki* thing, not everything — salience again).

Six build-capabilities, each mapped to a concrete mechanism and to code that already
exists in AERIS. This is the difference between buzzwords and a build.

| Property of "mind" | Concrete mechanism | Grounded in / built as |
|---|---|---|
| **Continuity** (remembers across time) | typed memory + embedding recall + nightly consolidation | `memory_fabric.py` ✅, `semantic_memory` ✅ |
| **Self-model** (knows its own state, abilities, limits) | a live introspective "self" record: skills, health, recent errors, confidence | NEW `self_model.py` (Month 3) over `skill_registry`, `telemetry`, `ledger` |
| **World-model** (knows what's going on around it) | situation object from calendar/mail/location/screen/sensors | Year-plan Q2·M4 |
| **Initiative / will** (acts unprompted, appropriately) | salience-scored triggers, ladder-governed | Year-plan Q2·M5 + `autonomy.py` ✅ |
| **Reflection** (critiques + corrects itself) | Reflexion critic pass after each action; outcome logging | Year-plan Q3·M7 + `ledger.py` ✅ |
| **Self-learning** (improves from experience) | 4 learning loops (below) | `feedback` ✅, `routine_learner` ✅, `export_corpus` ✅ |

### The four learning loops (how it "learns by itself")

Self-learning isn't one thing — it's four distinct feedback loops running at
different timescales. AERIS gets all four:

1. **Immediate — from correction.** You say "no, the other one" / thumbs-down →
   a durable preference is written and respected next time. *(seconds; `feedback`
   + Memory Fabric)*
2. **Daily — from consolidation.** A nightly job summarizes the day's episodic log
   into durable facts and prunes noise — the agent's "sleep". *(hours;
   `memory_consolidation`)*
3. **Weekly — from patterns.** Repeated behaviour becomes an *offered* routine;
   an offer accepted N times and never reverted **graduates** to auto-execute.
   *(days; `routine_learner` → graduation)*
4. **Periodic — from the whole corpus.** A personal LoRA fine-tuned on your
   (redacted) interaction history makes the local model speak/predict like *your*
   AERIS. *(weeks; `export_corpus` → Colab → adapter)*

"Learns from its surroundings" = loops 1–3 fed by the **world-model + sensors**
(screen, presence, location, notifications, calendar) — the agent notices what
happens around it and folds it into memory and routines.

### Why "self-awakening" is safe and real

Self-awakening = the agent starts acting/speaking on its own, not only on command.
That's powerful and dangerous, so it is **gated by the Autonomy Ladder (built)**:
initiative only fires within earned per-class levels, inside budgets and quiet
hours, every act logged with a "why" and undoable, with a panic word that halts
everything. Awakening without this gate would be a liability; with it, it's trustworthy.

---

## Part 2 — Wireframes (the experience)

Text wireframes for the surfaces that make the agent legible. (Can be turned into
Figma via the design tools when you want pixel mocks.)

### 2.1 The Voice Core HUD (exists — the "awake" face)
```
┌─────────────────────────────────────┐
│ AERIS            ● LAPTOP LINKED   ✕ │   status: linked / standalone
│                                       │
│              ╭───────────╮            │   the reactive core:
│           ╱  ╭─────────╮  ╲           │    · cyan   = listening
│          │   │  ◯ orb  │   │          │    · violet = thinking
│           ╲  ╰─────────╯  ╱           │    · mint   = speaking
│              ╰───────────╯            │   spokes react to real mic amplitude
│                                       │
│          ● SUN RAHA HOON              │   live state label
│      "aaj ka mausam batao"            │   live partial transcript
│                                       │
│               ( ⏹ stop )              │   tap core = barge-in
│      "bas" bolo ya tap karke band     │
└─────────────────────────────────────┘
```

### 2.2 The "Mind" dashboard (NEW — makes the agent legible)
```
┌─ AERIS · Mind ──────────────────────┐
│                                       │
│  ◐ STATE                              │
│    Mood: focused   Confidence: 82%    │   from self_model
│    Awake · listening · L3 autonomy    │
│                                       │
│  ◐ GOALS (3 active)             [›]   │   from goal_system
│    ▸ Rahul flat follow-up  ⏸ 6pm      │
│    ▸ Goa trip research     ▶ acting   │
│    ▸ read-list tidy        ✓ done     │
│                                       │
│  ◐ RECENTLY DID (why)           [›]   │   from ledger
│    · silenced phone — you always DND  │
│      in meetings              [undo]  │
│    · drafted reply to Mom     [undo]  │
│                                       │
│  ◐ LEARNED THIS WEEK            [›]   │   from learning loops
│    · you prefer PhonePe over GPay     │
│    · morning brief at 8:10, not 9     │
│                        [forget] [keep]│
└───────────────────────────────────────┘
```

### 2.3 Trust settings (NEW — governs awakening)
```
┌─ AERIS · Trust ─────────────────────┐
│  Autonomy per action type:            │
│   Device (torch, volume)   [L3 Act ▾] │   ladder promote/demote
│   Messages                 [L2 Draft▾]│
│   Calls                    [L2 Draft▾]│
│   Payments                 [L0 Ask ▾] │   (hard-capped, can't raise)
│   Delete / forget          [L1 Sug ▾] │
│                                       │
│  Quiet hours   [23:00]–[07:00]        │
│  Spend cap/day        ₹[5000]         │
│                                       │
│  [ 🛑 PANIC — halt all autonomy ]     │   → everything drops to L0
│  Recent actions ledger          [›]   │
└───────────────────────────────────────┘
```

### 2.4 Wake setup / personal model (NEW — fixes A6)
```
┌─ AERIS · Wake word ─────────────────┐
│  Sensitivity:  Low  [Balanced]  High  │
│                                       │
│  Personal voice model:                │
│   Say "Aeris" 5 times to train:       │
│   [ ● Record 1/5 ]  ▓▓▓░░              │
│   Accuracy on your voice:  —          │
│                                       │
│  Last heard:  "aeris" (conf 0.71) ✓   │   live confidence meter
│               "arre yaar" (0.18) ✗    │
└───────────────────────────────────────┘
```

---

## Part 3 — Black-box specifications

Each module as inputs → guarantees → outputs, so any can be built/tested in
isolation. (✅ = already built.)

### 3.1 Wake Engine ✅ (two-stage, v2)
```
IN:   16 kHz PCM mic frames
OUT:  wake event  { keyword, confidence, ts }
GUARANTEE: fires only on voiced, bursty audio matching a keyword; adaptive to
           room noise; ≤1 fire / 3 s; never holds the mic once the app acks
FAIL:  deaf → raise sensitivity / personal model; noisy → stage-2 + lower
```

### 3.2 Memory Fabric ✅
```
IN:   remember(text, kind) ; recall(query, k)
OUT:  ranked typed MemoryHit[]  (episodic|semantic|preference|note|fact)
GUARANTEE: hybrid rank (similarity⊕recency⊕salience); federates 3 stores;
           never crashes a turn on a store fault
```

### 3.3 Goal System ✅
```
IN:   capture(utterance) ; advance(goal, orchestrator)
OUT:  persistent Goal with lifecycle; resumes at the right trigger
GUARANTEE: survives restart; parks on need_user|need_time|need_tool;
           timed reminders NOT captured (reminder skill owns them)
```

### 3.4 Trust Gate + Ledger ✅
```
IN:   authorize(action, requested_level, cost)
OUT:  Decision(allow|confirm|deny, why) ; append-only ledger entry
GUARANTEE: irreversible classes ≤ L2 (hard cap); budgets + quiet hours + panic;
           every autonomous act explainable + (if reversible) undoable
```

### 3.5 Self-Model (NEW — Month 3)
```
IN:   skill_registry, telemetry, ledger, health_server, goal_system
OUT:  self()  → { skills[], health, recent_errors, confidence, mood,
                  awake, autonomy_level, active_goals }
GUARANTEE: read-only introspection; the planner cites it to know its own
           abilities/limits ("main ye nahi kar sakta kyunki…")
USE:  powers the Mind dashboard (2.2) + honest "can I do this?" answers
```

### 3.6 Initiative Engine (NEW — Year Q2·M5)
```
IN:   events + world-model deltas + goal due-times
OUT:  action candidates, salience-scored, routed act|offer|drop
GUARANTEE: routes through Trust Gate; anti-nag budget; quiet hours;
           precision-tuned (only truly-salient interrupts)
```

### 3.7 Learning Engine (NEW — Year Q4, spec here)
```
IN:   corrections (feedback), daily episodic log, weekly patterns, corpus
OUT:  durable preferences ; consolidated facts ; graduated routines ; LoRA
GUARANTEE: every learned item is inspectable + one-tap forgettable;
           nothing auto-executes above its ladder class
```

---

## Part 4 — System diagrams

### 4.1 The cognitive loop (runtime)
```
   ┌──────────── SENSES ────────────┐
   │ mic · screen · camera · location│
   │ calendar · mail · notifications │
   │ presence · power · app-usage    │
   └───────────────┬─────────────────┘
                   ▼  events
        ┌──────────────────────┐        ┌───────────────┐
        │  ① World Model +      │◄──────►│ Memory Fabric │ (episodic/
        │     Self Model        │ recall │  + Self store │  semantic/
        └──────────┬───────────┘        └───────────────┘  proc/pref)
                   ▼ situation + self
        ┌──────────────────────┐        ┌───────────────┐
        │  ② Planner (LLM,      │◄──────►│  Goal System  │ standing
        │     tiered + router)  │ goals  │  (persistent) │ intentions
        └──────────┬───────────┘        └───────────────┘
                   ▼ next step
        ┌──────────────────────┐        ┌───────────────┐
        │  ③ Trust Gate ────────┼───────►│    Ledger     │ why + undo
        │     (authorize)       │  log   └───────────────┘
        └──────────┬───────────┘
                   ▼ allowed
        ┌──────────────────────┐
        │  ④ Executor (tools:   │  phone · laptop · web
        │     skills/web/a11y)  │
        └──────────┬───────────┘
                   ▼ outcome
        ┌──────────────────────┐
        │  ⑤ Reflector (critic) │  worked? next? stuck?
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │  ⑥ Learning Engine    │  4 loops → back into Memory + Routines
        └──────────────────────┘
                   │
                   └────► ⑦ Initiative Engine ──(salience)──► speak/act via phone
```

### 4.2 One mind, two bodies (deployment)
```
        ┌──────────── THE AERIS MIND (laptop core) ───────────┐
        │  loop ①–⑦ · Memory Fabric · Goals · Trust · Self    │
        └───────────────▲──────────────────────┬──────────────┘
              E2E bridge │ (memory slice + goal sync)
        ┌────────────────┘                      ▼
   ┌────┴──────────────┐            ┌───────────────────────┐
   │ PHONE (body: sense │            │ CLOUD (Gemini): web +  │
   │ + act + presence)  │            │ knowledge, gated       │
   │ hotword·mic·TTS·   │            └───────────────────────┘
   │ apps·calls·a11y·loc│
   └───────────────────┘
```

### 4.3 State machine (the "awakening")
```
   [DORMANT] ──hotword / assist / schedule──► [AWAKE]
       ▲                                          │
       │ "so jao" / timeout / panic               │ perceive → decide
       │                                          ▼
   [LISTENING] ◄──follow-up── [ACTING] ──initiative──► [PROACTIVE]
       │                          │                      │
       └────── silence ───────────┴──────────────────────┘
   (PANIC from any state → DORMANT + autonomy L0)
```

---

## Part 5 — Month-by-month plan (self-learning agent)

Builds on everything shipped. Each month: shippable + tested + demoed.

**Reliability spine (already done):** Memory Fabric, Goal System, Autonomy
Ladder+Ledger+panic, two-stage wake. ← foundation complete.

### Month 1 — Rock-solid senses + self-view
- ✅ **Self-Model v1** (`core/self_model.py`) BUILT 2026-07-12 — read-only
  introspection over skills + ledger + goals + telemetry + panic; `snapshot()`
  → SelfState, `describe(q)` answers "kya kar sakta hai / abhi kya kar raha hai /
  kaisa hai / ye kyun kiya". Wired into `main_engine` Step 2f. 10 tests green.
- ✅ **Mind dashboard** (wireframe 2.2) BUILT 2026-07-12 — live at
  **http://127.0.0.1:8765/mind** (health server `/mind` + `/mind.json`). Themed
  AERIS dashboard (dark + plasma, mono), polls the self-model every 3 s: state
  (mood/confidence/awake/autonomy), capabilities-by-class bars, active goals,
  "recently did · why" (from the ledger), recent errors. Read-only, smoke-tested
  live; 23 health/self fast-lane tests green.
- ✅ **Two-stage wake** shipped (Part 0). On-device verify pending.
- ▶ **A6 personal wake model** (your voice) + live confidence meter (2.4).
- *Demo:* ask "AERIS, tu kaisa hai?" → honest state from the self-model.

### Month 2 — Continuity across bodies
- Memory-slice sync to phone; goal sync (capture on phone → laptop pursues).
- Nightly **consolidation** with the local LLM (loop 2 goes live).
- *Demo:* tell the phone something; the laptop knows it; "kal shaam kya kiya?"
  answered from consolidated memory.

### Month 3 — World-model + self-model deepen
- World Model (calendar + Gmail read-only + location + screen + notifications).
- Self-Model reads health/errors/telemetry → honest capability answers.
- *Demo:* "aaj ka din kaisa hai?" → real situation, not a template.

### Month 4 — Initiative (the awakening)  ✅ CORE BUILT 2026-07-12
- ✅ **Initiative Engine** (`core/initiative_engine.py`) — salience
  (importance×timeliness×confidence×openness), routes act/offer/drop through the
  Trust Gate, **quiet-hours silences ALL surfacing**, anti-nag budget
  (max/hour) + de-dup cooldown. Candidate sources: due goals (→ resurface) +
  pluggable extra sources (world-model events later). `pending()` shown on the
  Mind dashboard ("WANTS TO SAY"). 12 tests green, 102 fast-lane green.
- ✅ **Goal resurfacing works live** — a goal parked need_time, once due, is
  scored + surfaced (verified through the dashboard end-to-end). This IS the Q1
  north-star ("Rahul follow-up comes back").
- ▶ **NOT auto-spoken yet** — by design (trust before autonomy). Proactive
  speech via phone/TTS wires only after on-device quiet-hours/DND verification.
- *Demo:* localhost:8765/mind → "WANTS TO SAY" shows the resurfaced goal.

### Month 5 — Reflection + deeper brain
- Qwen2.5-3B/7B upgrade + brain router + **Reflexion critic** (loop after acting).
- *Demo:* a multi-step task where it catches its own mistake and recovers.

### Month 6 — Self-learning loops live
- Preference learning (loop 1) + routine graduation (loop 3) + "Learned this
  week" panel with forget.
- *Demo:* a habit graduates to auto-execute; a correction is respected next time.

### Month 7 — Real-world hands
- Web agent (Playwright, staged bookings) + phone a11y multi-step flows,
  Trust-Gate-guarded.
- *Demo:* "find + stage a booking" end-to-end to the confirm step.

### Month 8 — Sub-agents + background work
- Researcher/Scheduler/Operator/Scribe; durable background task queue.
- *Demo:* multi-day trip planning survives a restart and reports progress.

### Month 9 — Surroundings-aware learning
- Feed world-model + sensors into the learning loops: it notices context
  (place, time, app, people) and adapts routines/preferences to them.
- *Demo:* it learns "at office after 6pm → offer to book a cab" purely from
  observed pattern.

### Month 10 — Personal LoRA (becomes *yours*)
- Fine-tune a LoRA on your redacted corpus (Colab); load the adapter locally.
- *Demo:* blind A/B — the personalized model sounds/predicts more like your AERIS.

### Month 11 — Ambient presence + full continuity
- Shared working memory across devices; task started on one finished on the other.
- *Demo:* start by voice on phone, finish by typing on laptop, no repetition.

### Month 12 — Trust, eval, and the report card
- Nightly golden-task eval (recall/planning/tool-use/initiative/safety/resilience);
  Agent Report Card; failure drills.
- *Demo:* a green nightly eval + a one-screen report card; a scripted "bad day"
  causes zero unsafe actions.

---

## Part 6 — Risks (the honest register)

| Risk | Mitigation |
|---|---|
| Wake reliability (device-specific) | two-stage (done) → personal model (M1); confidence meter to diagnose |
| Annoying initiative kills trust | salience engine + anti-nag + learned openness + "silence is a feature" |
| Wrong autonomous act | Autonomy Ladder (done): irreversible ≤ L2, ledger + undo, panic |
| Over-claiming "consciousness" | honest framing everywhere; it's observable properties, not sentience |
| Privacy leak to cloud | local-first; PII only in allowed classes; E2E bridge; audit (M12) |
| Learning drifts / overfits | every learned item inspectable + forgettable; LoRA optional + swappable |
| Scope / never-ships | one shippable, tested, demoed increment per month |

---

## Part 7 — Definition of done (12 months)

AERIS will: **hear its name reliably; know itself** (abilities, state, limits);
**hold goals for days** and resume them; **perceive its surroundings** and
**act unprompted** — only when it earns it; **explain and undo** every action;
**learn continuously** from correction, sleep, habit, and corpus — adapting to
context; **live across your devices as one mind**; and be **measurably
trustworthy**. That is a self-awakening, self-learning agent — built as real,
governed, testable components, not a claim we can't back.
