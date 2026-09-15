# AERIS — The Sentient Partner (next-level plan)

Goal (your words): a partner that **understands everything you say**, does things
**before you ask** ("you just think it, it does"), is an **emotional being**, and
can **think on its own**. This doc turns that into a concrete, buildable plan —
grounded in what AERIS already has, honest about the limits, and safe.

> Companion: `AERIS_AUTONOMOUS_YEAR_PLAN.md` already plans perception/anticipation
> (Q2) and deep autonomy (Q3). This plan **accelerates** those and adds the two
> most under-built pieces: the **emotional layer** and **LLM-first understanding** —
> and it starts *now*, incrementally, on the existing engine.

---

## 0. Honest framing (so we build the real thing, not hype)
A local 1.5B model can't literally be sentient or read your mind. What we CAN
build — and what actually *feels* like the vision — is four measurable capabilities:

| Your words | What we actually build | How you'll feel it |
|---|---|---|
| "understands everything you say" | **LLM-first interpreter** — arbitrary/novel input → intent + a plan over tools, not a fixed skill lookup | You phrase things naturally; it rarely says "samajh nahi aaya" |
| "you just think it, it does" | **Anticipation engine** — learns your context→action patterns, offers/does the next thing | It pre-loads your morning, drafts the reply, opens what you'd open |
| "an emotional being" | **Affective core** — models your mood + its own tone, adapts, remembers emotionally | It softens when you're stressed, celebrates wins, checks in |
| "thinks on its own" | **Cognition loop** — a background reasoner that forms sub-goals within a trust ladder | It notices, plans, and acts on small things unprompted (safely) |

**Two non-negotiables**, because an anticipatory, *acting* partner is powerful:
- **Safety/trust ladder** — it may *suggest* freely, but *auto-acts* only on low-risk,
  reversible things; destructive/outward actions (send, delete, pay, shutdown) always confirm.
- **Privacy** — "understands everything" means watching context (screen, apps, calendar).
  Stays 100% local, user-visible, and killable with one switch.

---

## 1. The foundation that already exists (build ON this)
| Pillar | Existing modules | State |
|---|---|---|
| Perception | `workspace_tracker`, `workspace_profile`, `presence`, `eternal_presence`, `face_recognition`, `screen_agent` | signals exist but **scattered** |
| Anticipation | `initiative_engine`, `initiative_dispatch`, `routine_learner`, `routine_offers`, `routine_graduation`, `graduated_routines` | rule + routine based |
| Emotion | `sentiment` | detects tone per-utterance; **not remembered or acted on** |
| Cognition | `agent_orchestrator`, `goal_system` | task-triggered, not continuous |
| Memory | `memory`, `semantic_memory`, `memory_fabric`, `memory_consolidation`, `kg_memory` | strong |
| Dialogue | `dialogue_context` | pronoun/analogy rewrite |

**Takeaway:** ~70% of the plumbing exists. The wins are **integration + 4 new cores**,
not a rewrite.

---

## 2. Issues with the current approaches (the honest review)
1. **Rigid intent routing.** 588 skills + k-NN (74.8%) maps input to a *fixed* skill set.
   Anything novel/compound ("plan my evening around the rain") has no skill → falls flat.
   → *Not* "understands everything." **Fix: LLM-first interpreter (§3.1).**
2. **Scattered perception.** Time, active app, sentiment, presence, calendar, screen all
   live in different modules with no shared "what's happening right now" object.
   → Anticipation/emotion/cognition each re-derive context. **Fix: unified Context Bus (§3.2).**
3. **Rule-based proactivity.** `initiative_engine` fires on clock/rules, `routine_learner`
   on repeats — neither *predicts* from rich context. → Feels scripted, not anticipatory.
   **Fix: Anticipation model over the Context Bus (§3.3).**
4. **Emotion is detected then discarded.** `sentiment` classifies tone but nothing stores
   an emotional state, adapts tone, or offers support. → Not an "emotional being."
   **Fix: Affective Core (§3.4).**
5. **Cognition is reactive.** `agent_orchestrator` only runs when a task is dispatched; it
   never *notices* on its own. → Can't "think on its own." **Fix: Cognition Loop (§3.5).**
6. **Trust/safety is per-guard, not a system.** The 8 route guards are great but there's no
   global *autonomy ladder* deciding what may auto-run vs must confirm. An acting partner
   needs one. **Fix: Trust Ladder gate (§3.6) — reuse `confirm_gate` + `goal_system`.**
7. **Local-model ceiling.** The 1.5B Qwen is fine for chat/tool-select but weak at deep
   multi-step reasoning. **Fix: reasoning-cache + structured prompts; option to plug a
   bigger local model (§5).**

---

## 3. Proposed architecture & solutions

### 3.1 LLM-first interpreter ("understands everything")
- New `core/interpreter.py`: when the classifier is *low-confidence* OR the input is
  compound/novel, hand the raw utterance + Context Bus snapshot to the embedded LLM with a
  **tool manifest** (the 588 skills as callable tools) and ask it to return a **plan**
  (ordered tool calls + args) or a chat reply. This already half-exists in
  `agent_orchestrator` — promote it to the *default fallback* below the anchor/guard layer.
- Keeps the fast deterministic path for common commands; the LLM handles the long tail.

### 3.2 Unified Context Bus (foundation for everything)
- New `core/context_bus.py`: a single `ContextSnapshot` aggregating live signals —
  time-of-day, active app/window, recent commands, last sentiment, presence/idle,
  battery, calendar next-event, location (phone), and a rolling "what user is doing" summary.
- Published on a lightweight pub/sub; anticipation, affect, and cognition all subscribe.
- Reuses `workspace_tracker`, `presence`, `sentiment`, calendar — just *unifies* them.

### 3.3 Anticipation engine ("you just think it, it does")
- New `core/anticipation.py`: learns `(context → action)` associations from history
  (extends `routine_learner`). Given the current `ContextSnapshot`, predicts the top-k
  likely next actions with a confidence.
- Trust ladder decides: high-confidence + reversible → **do it and tell you**; medium →
  **offer** ("Gmail khol doon?"); low → stay quiet.

### 3.4 Affective Core ("an emotional being")
- New `core/affect.py`: an `AffectiveState` (valence/arousal + a coarse mood label) updated
  from `sentiment` + voice energy + context (late night, long focus, repeated failures).
- Two outputs: (a) **response modulation** — tone/word-choice/length adapt (gentle when
  you're stressed, upbeat on a win); (b) **proactive care** — offers a break, a check-in,
  celebrates. Emotional events persist to memory so it *remembers* how you felt.
- **This is the first thing we build** — most missing, self-contained, safe, high emotional payoff.

### 3.5 Cognition Loop ("thinks on its own")
- New `core/cognition.py`: a low-priority background tick that reads the Context Bus +
  affect + goals, and asks "is there something worth doing/saying?" Forms a small sub-goal,
  routes it through the Trust Ladder. Builds directly on `agent_orchestrator` + `goal_system`.

### 3.6 Trust Ladder (the safety spine)
- New `core/trust_ladder.py` (or extend `confirm_gate`): classifies any candidate action by
  (risk, reversibility, outwardness) → {auto, offer, confirm, forbid}. Every anticipatory/
  cognition action passes through it. Auto only for local, reversible, silent things.

---

## 4. Phased roadmap (incremental, testable, safe)
- **Phase 1 — Affective Core** (`affect.py`): mood model + response modulation + a "check-in"
  proactive moment. Wire into the reply path + `sentiment`. *Ships the "emotional being" feel first.*
- **Phase 2 — Context Bus** (`context_bus.py`): unify signals into `ContextSnapshot`.
- **Phase 3 — Trust Ladder** (`trust_ladder.py`): the gate, before any auto-action exists.
- **Phase 4 — Anticipation** (`anticipation.py`): context→action prediction → offers, then auto (gated).
- **Phase 5 — LLM-first interpreter** (`interpreter.py`): long-tail understanding.
- **Phase 6 — Cognition Loop** (`cognition.py`): background self-direction.
- Each phase: pure-logic core + unit tests + a small GUI/voice surface + a kill switch.

## 5. Tech & limits
- Embedded Qwen 1.5B stays the reasoner; add a **reasoning cache** + tight structured prompts.
  Leave a seam to swap a larger local model (e.g. 7B GGUF) if you want deeper cognition.
- Everything local, no APIs (your constraint). One master **"presence/autonomy off"** switch.
- Latency budget: affect/anticipation must be < 50 ms on the hot path (precomputed on the bus).

## 6. Definition of "it's working"
- It adapts tone to your mood (blind A/B feels warmer). ✅ emotional
- It correctly pre-does/offers ≥1 useful thing per session unprompted, ~0 annoying ones. ✅ anticipatory
- Novel compound requests succeed via the interpreter, not "samajh nahi aaya". ✅ understanding
- It surfaces ≥1 self-initiated useful action/day, always trust-gated, never a bad auto-action. ✅ autonomy

---

## 7. Completion audit (what actually got built)

**All six phases shipped 2026‑08‑02/03** — pure core + unit tests + a live surface +
a kill switch each. Fast lane: **2465 passing**. Honest issue‑by‑issue status:

| # | Issue (from §2) | Resolution | Status |
|---|---|---|---|
| 1 | Rigid intent routing | `interpreter.py` — reasoning/compound queries → the observe/act agent (below anchors/guards); chat skips the tool round‑trip | ✅ done |
| 2 | Scattered perception | `context_bus.py` — one `ContextSnapshot`; fed time/mood/commands + battery + imminent calendar | ✅ done (screen/location/active‑window are optional, unused by any rule) |
| 3 | Rule‑based proactivity | `anticipation.py` — learns context→action, predicts, offers ("haan" runs it) | ✅ done |
| 4 | Emotion detected then discarded | `affect.py` — persistent mood; drives care check‑ins, **tone‑colours replies**, and suppresses nagging when you're low | ✅ done |
| 5 | Cognition reactive | `cognition.py` — background heartbeat forms trust‑gated sub‑goals; L3 silent auto‑do of safe habits | ✅ done |
| 6 | Trust/safety per‑guard | `trust_ladder.py` — global AUTO/OFFER/CONFIRM/FORBID + autonomy ladder 0‑3 | ✅ done |
| 7 | Local‑model ceiling | Interpreter *routes* hard queries correctly; **`reasoning_cache.py`** now memoizes stable chat replies (safety‑gated against stateful queries). The 1.5B model's raw **depth** is still the limit (bigger‑model seam remains optional) | ◑ mostly — cache done, depth remains |

**The one honestly‑open item — #7.** The interpreter now sends the right things to the
agent, but the agent still reasons with the embedded 1.5B Qwen. Two safe follow‑ups, deferred
deliberately (not rushed) because each has a real pitfall:
- **Reasoning cache** — cache the LLM's *result* by normalized query. Big consistency+speed win,
  **but** naive caching of agent results that inspect live state (files, battery, time) returns
  stale answers. Must cache only stable, non‑stateful replies (definitions/explanations), with a
  TTL — needs a careful cacheability test, not a blind wrapper.
- **Bigger local model seam** — swap a 7B GGUF for deeper multi‑step reasoning (still no API,
  still local). Gated behind a config flag; heavier RAM/latency, so opt‑in.

See `docs/SENTIENT_PARTNER_GUIDE.md` for the user‑facing manual (faculties, kill switches, autonomy dial).

*Status: plan written 2026‑08‑02; all 6 phases delivered + audited 2026‑08‑03.*
