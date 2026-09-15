# AERIS — Sentient Partner: User Guide

*The "understands everything, does it before you ask, feels, and thinks on its own" layer.*
Built 2026‑08‑02/03. **Everything here runs 100% locally — no external APIs — and every part
has an off switch.** AERIS works exactly as before with all of it disabled.

---

## The six faculties

| # | Faculty | Module | What it does |
|---|---------|--------|--------------|
| 1 | 💗 **Feels** | `core/affect.py` | Tracks a mood (valence/arousal → *frustrated / low / tired / content / excited / neutral*) from your sentiment, successes and failures. Decays to neutral over time. Drives gentle proactive check‑ins and tells the other faculties when to *back off*. |
| 2 | 👁 **Perceives** | `core/context_bus.py` | One unified "what's happening right now" snapshot — time of day, quiet hours, recent commands, mood, battery, next reminder. Every other faculty reads from this. |
| 3 | 🛡 **Acts safely** | `core/trust_ladder.py` | Classifies every action into **AUTO / OFFER / CONFIRM / FORBID**. Sending, deleting, paying, shutting down are *never* automatic. This is the safety spine — nothing proactive can bypass it. |
| 4 | 🔮 **Anticipates** | `core/anticipation.py` | Learns your habits (*"in the morning after checking time, you open Gmail"*) and, at the right moment, offers the next step. Say **"haan"** and it runs it. |
| 5 | 🧠 **Understands** | `core/interpreter.py` | When your words don't match a known command, it decides *how to understand them* — sending genuine "go figure it out" requests to the reasoning agent instead of a blind guess. |
| 6 | ✨ **Thinks on its own** | `core/cognition.py` | A background reasoner. Each heartbeat it looks at the full context and raises the single most worthwhile thought — a low‑battery nudge, a rest reminder late at night, an imminent‑event heads‑up, or a learned habit. |

All six are stitched together: cognition uses perception + habits + mood + the trust ladder on every tick.

---

## The autonomy dial

Set the environment variable **`AERIS_AUTONOMY_LEVEL`** (default **2**):

| Level | Behaviour |
|-------|-----------|
| **0** | Manual. Even normally‑automatic actions are confirmed first. |
| **1** | AERIS may *offer*, never auto‑do. |
| **2** | *(default)* Safe automatic actions are fine; it offers habits and speaks nudges. |
| **3** | **Trusted.** For a *safe, reversible, high‑confidence* habit, while you're at the machine and it isn't quiet hours, AERIS just **does it and tells you** — no asking. This is the literal *"you just think it, it does."* |

Level 3 can only ever auto‑run **AUTO‑tier** actions (open an app, adjust volume, tell the time). Anything that
sends, deletes, pays, or changes lasting state is impossible to auto‑run at *any* level — it always asks.
Every self‑initiated act is written to the log as an `auto_action` event so you can audit exactly what AERIS did.

---

## Kill switches

Set any of these to `1` to fully disable that faculty (AERIS keeps working without it):

| Variable | Turns off |
|----------|-----------|
| `AERIS_AFFECT_OFF=1` | The emotional core (mood + proactive check‑ins). |
| `AERIS_ANTICIPATE_OFF=1` | Habit learning + anticipation offers. |
| `AERIS_INTERPRET_OFF=1` | The reasoning‑query routing (reverts to the old fallback). |
| `AERIS_COGNITION_OFF=1` | The self‑directed "thinks on its own" heartbeat. |
| `AERIS_AUTONOMY_LEVEL=0` | The strictest safety floor (confirm everything). |

**Privacy:** all state (mood, habits) lives in local JSON under `data/`. Nothing leaves the machine.
Delete those files to make AERIS forget; set the switches to make it stop learning.

---

## How to try it

1. Run AERIS normally (`AERIS.bat` / your usual launcher).
2. Use it for a few sessions — the anticipation engine needs to *see* a habit at least ~3 times before it predicts it.
3. It'll start offering the next step (*"Waise — gmail kholo karoon?"*) — say **"haan"** to run it.
4. On the proactive heartbeat it may raise its own thought (battery, rest, an imminent reminder, a habit).
5. Want the hands‑off experience? `set AERIS_AUTONOMY_LEVEL=3` and it'll quietly do the safe, confident ones.

*Tests: `tests/test_affect.py`, `test_context_bus.py`, `test_trust_ladder.py`, `test_anticipation*.py`,
`test_interpreter.py`, `test_cognition*.py`, `test_sentient_integration.py`. Design notes: `docs/SENTIENT_PARTNER_PLAN.md`.*
