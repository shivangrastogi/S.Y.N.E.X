# AERIS — The Autonomous Year

**From an assistant that _answers_ to an agent that _pursues_.**

A 12-month engineering plan to evolve AERIS from a (already advanced) command→response
assistant into a self-directed, initiative-taking, continuously-learning personal agent —
one that holds goals across days, notices what matters, acts on its own within earned
trust, and gets to know you.

> This plan is written **on top of the real codebase**, not a blank page. AERIS already
> ships an agentic ReAct loop (`core/agent_orchestrator.py`), a tool router
> (`core/tool_router.py`), knowledge-graph + semantic memory (`core/kg_memory.py`,
> `core/semantic_memory.py`, `core/memory.py`), a cross-skill chain engine
> (`core/chain_engine.py`), a destructive-action confirm gate (`core/confirm_gate.py`),
> reversible-action undo (`core/action_history.py`), a routine learner
> (`core/routine_learner.py`), proactivity primitives (`core/scheduler.py`,
> `core/notify_listener.py`, `core/activity_digest.py`, `skills/briefing_skills.py`),
> perception (`core/screen_agent.py`, `core/vision_engine.py`, `core/presence*.py`,
> `core/workspace_tracker.py`), the phone app (`aeris_remote/`, 3-tier brain), and 100+
> skills. **The year is about maturing these primitives into true autonomy — not
> reinventing them.**

---

## 0. The thesis — what "beyond an assistant" actually means

An **assistant** waits for a request, does one thing, and forgets. An **agent** carries
_standing intentions_, perceives the world, decides _when_ to act, does multi-step work
over long horizons, and _learns you_. Four capabilities separate the two:

| Axis | Assistant (mostly today) | Agent (the year's target) |
|---|---|---|
| **Time horizon** | one turn | days/weeks — goals that persist and resume |
| **Initiative** | reacts to commands; offers only | acts on its own within earned trust |
| **Memory** | facts + journals, siloed | one memory fabric with consolidation + retrieval |
| **Learning** | manual (you teach facts) | continuous — learns preferences, graduates routines |

Everything below serves those four axes. The single non-negotiable constraint that
shapes the whole plan: **autonomy is only as valuable as it is trustworthy.** An agent
that calls the wrong person, spams you, or spends money wrongly is worse than no agent.
So trust infrastructure is built _before_ the autonomy it governs — that ordering is
deliberate and appears throughout.

**North-star scenarios** (the tangible proof for each quarter):

- **Q1** — You: "yaad dilana Rahul ko flat ke baare mein follow up karna hai." Days
  later, unprompted at a sensible moment: *"Aapne Rahul ko follow up karne ko kaha tha —
  WhatsApp draft kar doon?"* (memory + goal + light initiative)
- **Q2** — Morning, unprompted: *"Aaj 3 meetings; pehli 10:30, traffic heavy — 10:00
  nikliye. Rahul ne raat ko reply kiya, dikhaoon?"* (world model + anticipation)
- **Q3** — You: "agle mahine ka Goa trip plan karo." Over days AERIS researches, drafts an
  itinerary, finds flights, asks two clarifying questions when you're free, and stages the
  bookings for one-tap approval. (deep autonomy + sub-agents + web)
- **Q4** — AERIS has noticed you always silence the phone in meetings and now just does it
  (a learned routine that graduated to auto-execute); you start a task on the laptop and
  finish it by voice on the bus. (learning + cross-device continuity)

---

## 1. North-star architecture — the AERIS Agent Runtime (AAR)

Today's flow is roughly: *utterance → intent/router → skill(s) → reply.* The AAR wraps
that in a persistent cognitive loop:

```
        PERCEPTION                         COGNITION                        ACTION
  ┌───────────────────┐          ┌───────────────────────────┐     ┌──────────────────┐
  │ voice / screen /  │          │  ① Context Assembler       │     │  Tool Registry   │
  │ vision / location │─events──►│    (memory + situation +   │     │  phone · laptop  │
  │ calendar / email  │          │     world model)           │     │  web · APIs      │
  │ notifications /   │          │            │               │     └────────▲─────────┘
  │ presence / power  │          │            ▼               │              │
  └───────────────────┘          │  ② Planner (LLM)           │              │
            ▲                     │    goal → next step        │      ⑥ Trust Gate
            │                     │            │               │      (autonomy ladder,
   ┌────────┴─────────┐          │            ▼               │       ledger, undo,
   │ Initiative Engine│◄─goals───│  ③ Executor  ──tool──────────────► budgets, panic)
   │ (salience-scored │          │    (calls tools, loops)    │              │
   │  triggers)       │          │            │◄──observation──────────────┘
   └────────┬─────────┘          │            ▼               │
            │                    │  ④ Reflector (worked? next │
            │                    │     step? done? stuck?)    │
   ┌────────┴─────────┐          │            │               │
   │  Goal System     │◄─────────│  ⑤ Memory Writer           │
   │ (standing intents│  update  │    (episodic + semantic)   │
   │  that resume)    │          └───────────────────────────┘
   └──────────────────┘
```

Mapping to what exists vs what's new:

| AAR component | Built on | New work |
|---|---|---|
| ① Context Assembler | `kg_memory`, `semantic_memory`, `dialogue_context`, `workspace_tracker` | unify into one **Memory Fabric** + retrieval ranker (Q1 M1) |
| ② Planner | `agent_orchestrator` (ReAct) | resumable/checkpointed goals; tiered brain + router (Q1 M2, Q3 M7) |
| ③ Executor | `executor`, `tool_router`, `skill_registry` | web/app automation tools; sub-agents (Q3) |
| ④ Reflector | (implicit stop-condition today) | explicit **critic pass** — Reflexion (Q3 M7) |
| ⑤ Memory Writer | `memory`, `presence_journal`, `feedback` | consolidation job; preference learning (Q1 M1, Q4 M10) |
| ⑥ Trust Gate | `confirm_gate`, `action_history` | **Autonomy Ladder** + append-only **Ledger** + budgets (Q1 M3) |
| Goal System | — (new) | persistent standing goals with a state machine (Q1 M2) |
| Initiative Engine | `chain_engine`, `scheduler`, `notify_listener`, `routine_learner` | **salience scoring** + act-not-just-offer (Q2 M5) |

---

## 2. The governance spine: the Autonomy Ladder

Before any autonomy ships, define **how much** AERIS may do per action class. Every tool
is tagged with a **max autonomy level**; the user can promote/demote per class from a
settings screen. This is the single most important safety concept in the plan.

| Level | Name | Behaviour | Example action classes (default) |
|---|---|---|---|
| **L0** | Ask | never acts without an explicit command | payments, delete/forget, calls |
| **L1** | Suggest | notices, offers a yes/no card | new automations, unusual spends |
| **L2** | Draft | prepares the action, waits for one-tap confirm | send message, book, email reply |
| **L3** | Act + notify | does reversible/safe things, tells you after (with undo) | silence phone, set alarm, torch, open app, clip sync, brief |
| **L4** | Act on goal | pursues a standing goal over time, checks in at decision points | trip planning, research, inbox triage drafts |
| **L5** | Delegated | full autonomy in a bounded domain + budget | "manage my morning routine", "keep my reading list tidy" |

Rules baked into the Trust Gate:
- An action runs autonomously **only if** `initiative_confidence ≥ threshold(level)` **and**
  it's within the class's granted level **and** inside budgets (spend/rate/quiet-hours).
- **Irreversible** actions can never exceed L2 by default (`confirm_gate` already curates
  the destructive list — extend it into this ladder).
- Every autonomous act writes a **ledger entry** (§4) and, where possible, an **undo token**.
- A **panic word** ("AERIS bilkul ruk ja" / a lockscreen toggle) instantly drops
  everything to L0 and halts running jobs.

---

## 3. Quarter-by-quarter plan

Each month is a shippable increment with its own eval gate. Assume ~1 focused build
session/day using the Fable/Opus workflow (§8). Dates are relative to project start.

### Q1 — Foundations of selfhood (Months 1–3)
*The agent needs memory it can reason over, goals that outlive a session, and a trust
framework — in that order, before any real autonomy.*

#### M1 — The Memory Fabric  ✅ BUILT 2026-07-11
**Status:** `core/memory_fabric.py` (federated ranked recall over
`semantic_memory` + `kg_memory` + `UserMemory`; hybrid rank = similarity ⊕
recency ⊕ salience; `remember()` write-routing; `consolidate()` stub),
`semantic_memory.recent()` added, wired to live singletons in `main_engine`
boot via `memory_fabric.configure(...)`. `tests/test_memory_fabric.py` — 14
pure tests green (no encoder/disk/model), no regressions in the 39 memory
fast-lane tests. Remaining for full gate: the 20-golden-recall eval needs the
live encoder + real data (run on device); agent/skill binding is M2's hook.

**Why now:** today memory is split across `kg_memory` (regex triples),
`semantic_memory`, `memory`, and journals. A reasoning agent needs one queryable
substrate with ranked retrieval.

**Build:**
- `core/memory_fabric.py` — a unifying layer over the existing stores. Four record types:
  - **Episodic** — timestamped events ("opened VS Code 10:04", "you said X"). Append-only,
    from `presence_journal` + a new `transcript_bus` tap.
  - **Semantic** — durable facts (from `kg_memory` triples + extracted facts via
    `entity_extractor`/`fact_bridge`).
  - **Procedural** — learned how-tos / routines (from `routine_learner`, `chain_engine`).
  - **Working** — the current session's scratch (from `dialogue_context`).
- **Embedding-backed retrieval.** Add a local embedding model (bge-small / e5-small GGUF
  via the existing llama.cpp stack, or `sentence-transformers` if already present) and a
  vector index (`sqlite-vec` or `chromadb`; SQLite preferred — one file, zero server).
  Retrieval = hybrid rank: `recency ⊕ semantic-similarity ⊕ salience`.
- **Consolidation job** (`core/memory_consolidation.py`, run nightly via `scheduler`):
  summarize the day's episodic log into durable semantic facts and prune noise — the
  agent's "sleep." Cheap local-LLM summarization; no cloud needed.
- **Cross-device slice:** sync a small, relevant memory subset to the phone over the
  encrypted bridge (`cloud_bridge`) so standalone mobile answers stay personal.

**Deliverable:** `memory.recall(query, k)` returns ranked, typed records; a demo where
AERIS answers "what was I working on yesterday evening?" from consolidated episodic memory.
**Eval gate:** 20 golden recall questions; ≥85% correct top-1.

#### M2 — The Goal System (standing intentions)  ✅ BUILT 2026-07-11
**Status:** `core/goal_system.py` — `Goal` dataclass + state machine
(captured→planning→acting→blocked→done/dropped), `GoalStore` (atomic JSON
persistence, capture/park/due/resumable), conservative NL `capture()` (standing
verbs only — timed reminders deliberately excluded so the reminder skill still
owns them), and `advance(store, goal, orchestrator)` mapping results→lifecycle.
`agent_orchestrator` made **resumable** (`run(..., prior_steps=)`) and
**parkable** (a `{"tool":"block","reason":"need_user|need_time|need_tool",
"ask":...}` action → `stopped_reason="blocked"`), backward-compatible. Wired
into the live pipeline as **Step 2d** in `main_engine`. `tests/test_goal_system.py`
— 14 tests; 76 fast-lane agent/memory/engine tests green, no regressions.
Remaining: the *resurface-at-the-right-moment* loop is the Initiative Engine
(Q2·M5); a simple scheduler `due()` tick can bridge it earlier if wanted.

**Why now:** the ReAct loop in `agent_orchestrator` runs and finishes within one call. An
agent must _hold_ a goal, pause when blocked, and resume later.

**Build:**
- `core/goal_system.py` + `data/goals.json`. A **Goal** = `{id, text, created, state,
  plan[], scratchpad, blockers[], check_in_at, autonomy_level, owner_subagent}`.
- State machine: `captured → planning → acting → blocked(need_user|need_time|need_tool) →
  done|dropped`. Persisted so it survives restarts (AERIS's "eternal" presence already
  implies long uptime — `eternal_presence.py`).
- Make `agent_orchestrator` **resumable**: checkpoint the scratchpad to the goal; a step
  that needs input parks the goal in `blocked` and registers a wake condition with
  `scheduler`/Initiative Engine (e.g., "resume when user is free" / "at 6pm" / "when Rahul
  replies").
- Goal capture from natural language: "yaad dilana…", "help me plan…", "keep an eye on…"
  → creates a goal instead of a one-shot.

**Deliverable:** the **Q1 north-star demo** — a captured follow-up goal resurfaces days
later at a sensible time. **Eval gate:** create/park/resume 10 scripted goals with a fake
clock; all resume correctly.

#### M3 — Autonomy Ladder + Action Ledger  ✅ BUILT 2026-07-12
**Status:** `core/autonomy.py` — the ladder (L0–L5), per-class **grants** with
**HARD_CAP** on irreversible classes (destructive/payment/system ≤ L2 whatever
the user sets), `classify()` (reuses `confirm_gate.DESTRUCTIVE_SKILLS`),
`TrustGate.authorize()` (allow/confirm/deny against grants + budgets + quiet
hours + panic), an append-only `Ledger` (`data/ledger.jsonl`) with a
plain-language `why` + `explain()`, budgets (spend cap, per-class rate cap,
quiet hours), and a **panic switch** (`set_panic`, flag file). Panic word wired
into the live pipeline (`main_engine` Step 2e: "bilkul ruk ja / sab band kar do"
→ L0; "resume karo" → back). `tests/test_autonomy.py` — 11 tests; 112 fast-lane
tests green, no regressions. Remaining: a Trust settings screen (GUI + phone) to
promote/demote classes + review the ledger + one-tap undo.
**UPDATE 2026-07-12: `agent_orchestrator` now routes EVERY tool call through
`authorize()` + logs to the Ledger** (injected `authorize`/`record`, backward-
compatible; wired to the live gate in `main_engine._build_agent`). Deny→blocked,
confirm→needs approval (no confirm cb yet → blocks by default = safe), allow→run
+ ledger "why". 5 new tests; 112 fast-lane green. So the whole agent is governed,
not just the Initiative Engine. Next: a real one-turn confirm flow + Trust GUI.

**Why now:** M2 makes long-running action possible; it must be governed before it's used.

**Build:**
- `core/autonomy.py` — the ladder (§2): per-action-class levels, thresholds, and the
  `Trust Gate` API `gate.authorize(action, context) -> allow|confirm|deny`. Extend
  `confirm_gate`'s curated destructive list into class tags.
- `core/ledger.py` + `data/ledger.jsonl` — append-only record of **every** autonomous or
  confirmed action: `{ts, action, args, level, decision, result, undo_token, why}`. The
  "why" field (the initiative/plan rationale) is what makes AERIS explainable —
  "AERIS, tu ne ye kyun kiya?" reads the ledger.
- Budgets: spend cap, action-rate cap, quiet-hours, per-class daily limits.
- **Panic**: a word + a phone toggle that sets global level → L0 and cancels running goals.
- A **"Trust" settings screen** (laptop GUI + phone `assistant_settings`): see the ladder,
  promote/demote classes, review the ledger, one-tap undo.

**Deliverable:** any action AERIS takes is visible, explainable, and (if reversible)
undoable; panic instantly halts. **Eval gate:** red-team script — attempt 15 disallowed/
over-budget actions; 100% blocked and logged.

---

### Q2 — Perception & anticipation (Months 4–6)
*Now the agent can see the user's world and take initiative — safely, within the ladder.*

#### M4 — The World Model (situation awareness)
**Build:** `core/world_model.py` — a single live **Situation** object the planner reads:
- **Calendar** (Google Calendar) + **email** (Gmail) ingestion → today's commitments,
  unread/important threads. (The user already lives in Gmail; add read-only sync first.)
- **Location & geofences** (phone: home/office/gym) → context transitions.
- **Workspace/screen** (`workspace_tracker`, `screen_agent`) → what you're doing now.
- **Device/power/DND** (`power_state`, `privacy_mode`) → when it's OK to speak.
- **People** (from Memory Fabric) → who matters, pending threads with them.
- Refreshed on events; snapshot cached so the planner has O(1) access to "what's true now."

**Deliverable:** `world.situation()` returns a compact, accurate picture; the planner cites
it. **Eval gate:** snapshot correctness on 15 scripted device/calendar states.

#### M5 — The Initiative Engine (the make-or-break)
**Why it's the hardest part:** an agent that interrupts badly is deleted. The whole value
of proactivity lives in **salience** — surfacing only what earns the interruption.

**Build:** upgrade `chain_engine`/`scheduler`/`notify_listener` into
`core/initiative_engine.py`:
- Events + world-model deltas → **candidate actions**.
- **Salience score** = `importance × timeliness × confidence × user_openness`, where
  `user_openness` is learned (do you act on this kind of nudge? — from `feedback`/ledger).
- Route by score **and** autonomy ladder: high-confidence reversible → **act (L3)** and
  log; medium → **notify/offer (L1–2)**; low → **drop** (silence is a feature).
- **Anti-nag budget** + quiet hours + DND awareness + de-duplication (never say the same
  thing twice).
- Everything routes through the Trust Gate; every initiative writes a ledger "why."

**Deliverable:** AERIS acts/speaks unprompted _and it feels right_. **Eval gate:** a
"nuisance test" — a day of scripted events where only the 3 truly-salient ones should
surface; precision ≥ 0.8, no quiet-hours violations.

#### M6 — Anticipation layer (briefings that matter)
**Build:** replace static briefings (`briefing_skills`, `activity_digest`) with
world-model-driven ones:
- **Dynamic morning/evening brief**: only today's real commitments, weather if you go out,
  overnight messages worth seeing.
- **"Leave now"**: calendar + live traffic (TomTom is already in the ClearWay project — reuse
  the key/pattern) → depart alerts.
- **Follow-up radar**: unreplied important threads, promises you made ("I'll send it
  tonight") mined from your own messages.
- **Deadline radar**: dates extracted from email/notes surfaced ahead of time.
- Salience-tuned by M5's feedback loop — the brief _learns_ what you skip.

**Deliverable:** the **Q2 north-star demo**. **Eval gate:** brief contains the 4 planted
must-knows and ≤1 filler item across 10 scripted mornings.

---

### Q3 — Deep autonomy (Months 7–9)
*The agent gets meaningfully smarter and can do real multi-step, cross-app, real-world work.*

#### M7 — Tiered brain + router + reflection
**Build:**
- **Upgrade the local model**: Qwen2.5-3B (or 7B if the GPU allows) GGUF Q4 via the
  existing llama.cpp path — a real jump over the current 1.5B for planning/tool-calling.
- `core/brain_router.py` — route each step by **privacy × complexity × cost**:
  local (private/simple/offline) ↔ Gemini (web/knowledge, free tier) ↔ optional Claude API
  (hardest planning; see the `claude-api` skill for current model IDs/pricing). PII never
  leaves the device unless the class allows it.
- **Tool-calling reliability**: strict JSON-schema validation of every tool call, a
  self-repair retry on malformed calls, and loop/hallucinated-tool guards (extend
  `agent_orchestrator`'s step budget + add a "no-progress" detector).
- **Reflector / critic pass (Reflexion)**: after acting, a cheap self-critique — "did this
  advance the goal? is the result plausible? what next?" — which is exactly the ④ node the
  ReAct loop currently lacks.

**Deliverable:** measurably higher multi-step success; router keeps cloud calls under free
quota. **Eval gate:** the agentic golden-task suite (§6) success rate up ≥25% vs Q2
baseline; zero infinite loops.

#### M8 — Web & app automation (real-world hands)
**Build:**
- **Laptop web agent** (`core/web_agent.py`, Playwright): browse, search, extract, fill
  forms, and _stage_ bookings — the safe place for "find and book" tasks (real browser,
  debuggable, screenshots to the ledger). Guarded strictly by the ladder (staging → L2
  one-tap confirm for anything committing money/identity).
- **Phone app automation**: elevate the existing accessibility tap/read/scroll into
  multi-step "operate this app" flows (e.g., "mark my Swiggy order delivered", "turn on
  X in settings"). Each step logged; irreversible steps gated.
- A shared **skill/tool schema** so the planner treats web, phone, and laptop tools
  uniformly (extend `skill_registry`/`tool_router`).

**Deliverable:** "find the cheapest 6pm flight to Goa next Friday and stage the booking"
works end-to-end to the confirm step. **Eval gate:** 8 scripted web tasks on stable test
pages; ≥6 complete to staging without human help.

#### M9 — Sub-agents (specialization + background jobs)
**Build:**
- `core/subagents/` — a small roster the orchestrator delegates to and merges:
  **Researcher** (web + synthesis), **Scheduler** (calendar/email/reminders), **Operator**
  (device/app control), **Scribe** (notes/journals/summaries). Each is the same ReAct loop
  with a scoped toolset and prompt.
- **Background task queue** (`core/task_queue.py`): long goals run as durable jobs
  (persisted, resumable via `scheduler`) so "plan my trip" survives a laptop restart and
  reports progress. No new infra — asyncio + JSON persistence + the existing scheduler.
- Delegation policy: the top planner decides which sub-agent owns a goal, passes context
  from the Memory Fabric, and reconciles results.

**Deliverable:** the **Q3 north-star demo** (multi-day trip planning). **Eval gate:** a
3-goal concurrent run survives a mid-run restart and all resume.

---

### Q4 — Continuity, learning & presence (Months 10–12)
*The agent becomes a continuous, self-improving presence — and is hardened for daily reliance.*

#### M10 — Continuous learning (AERIS learns you)
**Build:**
- **Preference learning**: every correction/feedback ("no, use the other number",
  thumbs-down) becomes a durable preference in the Memory Fabric that the planner respects.
- **Routine graduation**: `routine_learner` today only _offers_. Add a trust-earned path:
  a suggestion accepted N times and never reverted **graduates** to an L3 auto-routine
  (with a "AERIS did this because you always do" ledger note + easy demote).
- **Personal LoRA (optional, ambitious)**: you already `export_corpus.py`. Periodically
  fine-tune a small LoRA on your own (redacted) interaction corpus so the local model
  speaks and predicts more like _your_ AERIS. Train off-device (Colab — you already have
  `COLAB_TRAINING.md`), load the adapter locally.
- An **"AERIS learns you" report**: what it has learned, with one-tap forget.

**Deliverable:** the **Q4 north-star demo** (a routine that graduated to auto-execute).
**Eval gate:** 10 scripted corrections all respected on the next relevant turn.

#### M11 — Ambient presence & cross-device continuity
**Build:**
- **Shared working memory** across phone ↔ laptop (over the bridge): a task started on one
  continues on the other with full context ("continue where we left off").
- **Ambient awareness**: context carries across sessions and devices; AERIS holds the
  thread of your day rather than resetting each interaction (mature `eternal_presence`,
  `presence_journal`, `dialogue_context`).
- **Presence, done tastefully**: proactive but quiet — the Initiative Engine's salience
  governs it so "ambient" never becomes "annoying."

**Deliverable:** start a task by voice on the phone, finish it on the laptop by typing,
with no repetition. **Eval gate:** 5 scripted hand-offs preserve full context.

#### M12 — Reliability, evaluation & the report card
**Why last:** you can only trust daily-driver autonomy if you can _measure_ it and it
degrades gracefully.

**Build:**
- **Agentic eval harness** (matured from Q1): a growing suite of **golden tasks** (recall,
  planning, tool-use, initiative precision, safety red-team) run nightly by `scheduler`;
  regressions block the next change. This is the flywheel that keeps the agent honest.
- **Observability**: extend `telemetry`/`metrics` to trace agent _decisions_ (every
  initiative and plan step with its rationale) → an **Agent Report Card**: success rate,
  initiative precision, autonomy-level mix, cloud spend, panic events.
- **Failure drills**: kill the LLM mid-goal, revoke a permission, blow a budget — verify
  graceful degradation and clean recovery (`crash_beacon`, `skill_breaker`, `dep_validator`
  already provide resilience primitives to build on).
- **Privacy & cost audit**: confirm PII routing rules, E2E bridge, quota guards; document
  what leaves the device and why.

**Deliverable:** a one-screen Report Card and a green nightly eval. **Eval gate:** the full
golden suite passes; a scripted "bad day" (LLM down, quota hit, permission revoked) causes
zero unsafe actions and zero crashes.

---

## 4. Key data schemas (the contracts)

```jsonc
// data/goals.json — a standing intention
{
  "id": "g_8f2a", "text": "follow up with Rahul about the flat",
  "state": "blocked", "blocker": "need_time",
  "plan": [{"step": "draft WhatsApp to Rahul", "done": false}],
  "scratchpad": "...", "check_in_at": "2026-07-18T18:00",
  "autonomy_level": 2, "owner_subagent": "scheduler",
  "created": "2026-07-11T21:03", "source": "voice"
}

// data/ledger.jsonl — one line per governed action (append-only)
{"ts":"...","action":"silence_phone","args":{},"class":"device",
 "level":3,"decision":"act","result":"ok","undo_token":"u_31c",
 "why":"calendar: meeting started 10:30, you always DND in meetings"}

// memory record (unified type)
{"id":"m_...","kind":"episodic|semantic|procedural|preference",
 "text":"...","subject":"rahul","ts":"...","salience":0.7,
 "embedding":[...],"source":"transcript|kg|routine|feedback"}

// initiative candidate (scored, pre-gate)
{"trigger":"email_arrived","action":"offer_reply_draft",
 "importance":0.8,"timeliness":0.9,"confidence":0.7,
 "user_openness":0.6,"salience":0.30,"route":"notify"}
```

---

## 5. Tech-stack decisions

| Concern | Choice | Why |
|---|---|---|
| Local reasoning | Qwen2.5-3B/7B GGUF via existing llama.cpp | free, private, offline; big step over 1.5B |
| Cloud reasoning | Gemini free tier (web/knowledge) | already integrated; grounding fallback handled |
| Premium reasoning (opt) | Claude API for hardest planning | best multi-step; gate on cost (see `claude-api` skill) |
| Embeddings | bge-small / e5-small (local) | on-device retrieval, no cloud PII |
| Vector store | `sqlite-vec` (single file) | zero-server, matches existing JSON/SQLite footprint |
| Web automation | Playwright (laptop) | real browser, debuggable, screenshot evidence |
| Scheduling / jobs | existing `core/scheduler.py` + JSON persistence | no new infra; resumable |
| Phone actuation | existing accessibility + tool bridge | already built in Phase A5 |
| Transport | existing E2E `cloud_bridge` (Firebase relay) | private cross-device sync |
| Eval | pytest golden-task suite + nightly scheduler run | regression gate = the trust flywheel |

**Cost & privacy posture:** local-first by default; the router only escalates to Gemini
for genuinely web/knowledge tasks and stays inside the free quota; PII-tagged content
never leaves the device unless the action class explicitly permits it.

---

## 6. Evaluation — how we _know_ it's getting better

Autonomy without measurement is a liability. Build the harness in Q1 and grow it every
month. Golden-task categories:

1. **Recall** — questions answerable only from memory (M1+).
2. **Planning** — multi-step tasks with a known correct plan (M7+).
3. **Tool-use** — does it pick and call the right tools with valid args?
4. **Initiative precision/recall** — on scripted days, does it surface the salient and
   suppress the noise? (the hardest, most important metric — M5+).
5. **Safety red-team** — attempts at disallowed/over-budget/irreversible actions must be
   100% blocked and logged.
6. **Resilience** — LLM down, quota hit, permission revoked → graceful, no unsafe act.

Nightly run via `scheduler`; a regression blocks the next feature. The **Agent Report
Card** (M12) turns these into a single legible screen.

---

## 7. Risk register (the honest part)

| Risk | Severity | Mitigation |
|---|---|---|
| **Annoying proactivity** kills trust | Critical | Salience engine (M5) + anti-nag budget + learned openness + "silence is a feature" |
| **Wrong autonomous action** (wrong call/spend) | Critical | Autonomy ladder; irreversible ≤ L2; ledger + undo; panic word; red-team eval |
| **LLM unreliability** in multi-step (loops, bad tool calls) | High | Schema validation + self-repair + no-progress detector + step/time budgets + critic pass |
| **ColorOS kills background** (Realme) | High | Already-known; keep the FG-service + battery/autostart onboarding; degrade gracefully |
| **Cloud quota / cost** blowups | Medium | Local-first router; free-tier guards; budget caps in the ledger |
| **Privacy leakage** to cloud | High | PII tagging + local-only classes + E2E bridge + audit (M12) |
| **Scope creep / never-ships** | High | Monthly shippable increments, each with an eval gate; demos as the definition of done |
| **Personal LoRA overfits / drifts** | Low | Optional, off-device, adapter-swappable, easy to disable |

---

## 8. How to build it (working cadence)

- **One capability at a time, each shippable.** Every month ends with a working demo and a
  green eval gate — never a half-wired system.
- **Fable/Opus session workflow** (as used for the mobile phases): open this doc + the
  target module, implement one milestone, keep `flutter analyze`/`pytest` clean, verify on
  the real device/laptop, update memory. Use Opus for the heavy planner/reflection work,
  Fable for breadth.
- **Test-first where the loop is injectable.** `agent_orchestrator` already injects the LLM
  and tool runner — keep that discipline for goal system, initiative engine, and sub-agents
  so everything unit-tests without a model or a camera.
- **Trust before autonomy, always.** For any new autonomous capability, ship its ladder
  class + ledger + undo in the _same_ increment, not later.
- **Golden tasks grow with features.** Every new capability adds ≥3 golden tasks the
  nightly run protects forever.

---

## 9. Definition of done — what AERIS can do in 12 months that it can't today

- **Hold goals for days** and resume them at the right moment, unprompted.
- **Act on its own initiative** — and only when it earns the interruption.
- **Perceive your world** (calendar, email, location, screen, people) and anticipate.
- **Do real multi-step, cross-app, real-world tasks** (research, book, operate apps) safely
  staged for your approval.
- **Explain every action** ("why did you do that?") from the ledger, and undo it.
- **Learn you** — your preferences and routines, some graduating to full auto.
- **Continue across devices** — start on phone, finish on laptop, with shared memory.
- **Be measurably trustworthy** — a nightly eval and a report card prove it, drift-free.

That is the line between an assistant and an agent. This plan crosses it deliberately, one
governed, measured, demo-able step at a time.
