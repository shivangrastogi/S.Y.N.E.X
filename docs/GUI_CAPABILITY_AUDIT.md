# GUI ↔ Capability Audit + Redesign Plan (2026-07-19)

*User complaint: "many options broken / not shown in laptop + mobile GUI."
Audit method: script-scan of every dispatch reference in `ui/` validated
against the 397-intent merged corpus + routines.json + automation code.*

## Part A — Audit findings

### A1. The real problem is coverage, not paint

| Metric | Value |
|---|---|
| Abilities in the mind (merged corpus) | **397 intents · ~17 domains** |
| GUI dispatch references (all 12 panels) | **15** |
| Domains with ZERO GUI surface | agent/goals, learning/brain-health, **continuity/phone**, screen agent, bridge tools, memory/KG, reminders, notes/tasks, web, voice/TTS |

The 12 panels (Home/Chat/Brain/Memory/System/Settings/Vision/Workbook/
Routines/Events/Quick/Trust) are mostly **passive status views**. Every
July-era capability (agentic layer, learning loop, continuity, screen
agent, bridge phases) shipped with **no GUI presence**. Root cause:
panels are hand-coded snapshots of an April-era feature set — they rot
by design.

### A2. Genuinely broken options found

| # | Broken thing | Where | Root cause |
|---|---|---|---|
| B1 | Every `kind:"text"` quick action (e.g. "Note this meeting") silently does nothing | `SmartSuggestionsPanel.submit_text` | signal **never connected** in main_window |
| B2 | Quick-action payloads have no existence check — a renamed skill/routine becomes a dead button with no error | `SmartSuggestionsPanel._refresh` | no validation against registry/corpus |
| B3 | New dock keys impossible without touching 3 files in sync (`DOCK_ITEMS`, `_TAB_INDEX`, icon painter) | dock/tab wiring | fragile hand-sync |

(Skill/routine payload names themselves all resolve — `battery_saver`,
`pomodoro` etc. exist in routines.json; the earlier suspicion of dead
routine ids was a false positive from nested JSON.)

### A3. Mobile
Phone app surfaces chat + controls well, but has no view of what AERIS
*can do* (skills list), and no continuity/body indicator after the C1-C5
build.

## Part B — Design decision (frontend-design pass)

**Thesis: the GUI must be a *projection of the registry*, not a painting
of it.** Anything hand-listed goes stale; anything generated from
`skill_registry` / `brain_health` / `goal_system` / `continuity` cannot.

**Identity**: keep + sharpen the established AERIS instrument-panel look
(deep void navy, Inter + JetBrains Mono, arc-reactor states). No reskin
of 12 working panels. The refinement is **semantic color**: each mind
domain gets a fixed accent used in dock, headers, and phone —

| Domain | Accent | Token |
|---|---|---|
| Abilities (what I can do) | Cyan `#00D4FF` | ARC |
| Intelligence (how well I think) | Magenta `#FF2D95` | SYNAPSE |
| Continuity (where I am) | Green `#10B981` | ALIVE |
| System/attention | Amber `#FBBF24` | SOLAR |
| Agent/speech | Purple `#A855F7` | AETHER |

**Signature element**: the **Abilities index** — a live, searchable,
registry-generated constellation of every skill, grouped by module, each
with its spoken phrase in mono. Header states the living truth:
`397 ABILITIES · GENERATED FROM THE REGISTRY AT BOOT`. Click inserts the
phrase into the chat input (never auto-runs — same restraint as the
retrain rule). This panel *cannot* go stale: that is the design.

**New surfaces (right stack, 390px), one dock group "MIND":**

```
┌ ABILITIES ────────── ARC ─┐  ┌ INTELLIGENCE ── SYNAPSE ┐  ┌ CONTINUITY ── ALIVE ┐
│ 397 abilities · live index │  │  ◔ 80/100   gen 1        │  │ ● LAPTOP active now  │
│ [ search … ]               │  │  router: k-NN FALLBACK   │  │ ○ PHONE idle · 3m    │
│ ▾ PHONE BRIDGE (16)        │  │  golden 82.1 · val 73.8  │  │ link: paired ✓       │
│    ring phone   「phone…」  │  │  learned +39 · review 1  │  │ mem slice: 12 facts  │
│ ▸ VISION (34)  ▸ NOTES (19)│  │  ┌ RETRAIN DUE ────────┐ │  │ GOALS                │
│ ▸ …                        │  │  │ python -m core.     │ │  │ ▸ rahul follow-up    │
│                            │  │  │ retrain  [copy]     │ │  │   parked: "haan ya   │
│                            │  │  └─────────────────────┘ │  │   cancel?"           │
└────────────────────────────┘  └──────────────────────────┘  └──────────────────────┘
```

Rules: **no "train now" button** (training stays a user ritual — GUI
offers a copy-command card); health dial gets its one-time sweep, no
other new animation; empty states instruct ("Phone se abhi koi beat
nahi — app kholo to yahan dikhega").

**Fixes shipped with the redesign**: B1 (connect submit_text), B2
(validate payloads at refresh; invalid → hidden + one log line), B3
(new panels registered through the same three-point wiring, documented).

**Mobile decision (restraint applied)**: the phone's "Command Deck"
identity (graphite console + plasma orb) is already deliberate and
strong — repainting it with the laptop's accents would flatten a good
design, so it stays. This phase's mobile surface is what C3 already
shipped: routed proactive cards (reply.route → spoken + shown) and
presence beats. A phone-side abilities sheet needs a real PhoneSkills
catalog first (hand-listing would break the no-hand-lists rule) —
deferred to the PhoneSkills refactor. When linked, "help" already
answers from the laptop's help_catalog.

## Part C — Domain inventory (generated 2026-07-19)

apps/windows 12 · media/volume 13 · web/browser 18 · info/system 14 ·
notes/tasks/expense 19 · reminders/timers 8 · vision/gesture 34 ·
voice/TTS 19 · phone/bridge 16 · screen agent 8 · agent/goals 4 ·
learning/intelligence 4 · continuity 1 · memory/KG 8 ·
routines/automation 19 · privacy/trust 11 · power 10 · long tail ~189
(registry modules cover these — the Abilities panel lists every one).
