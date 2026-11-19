# AERIS — Session Handoff (what changed + what to do next)

_Last updated 2026-08-01. One place for everything this work stream shipped and
your remaining action items._

## TL;DR
- **The "crash on the 2nd prompt" is fixed**, and split-brain mode now boots
  **faster (~20s)** than the old in-process mode **and** can't heap-crash.
- **Routing quality is materially better** — core commands that mis-routed
  9–27% now hit 50–86%, and the *dangerous* mis-routes (a reminder deleting
  files!) are blocked. All **without retraining**.
- Everything is behind the `AERIS_SPLIT_BRAIN=1` flag / in core files, so it
  applies on your **next relaunch**.

## How to run
```powershell
cd "D:\New folder (2)\1. LATEST 23 April\New version- 3.0"
$env:AERIS_SPLIT_BRAIN = "1"
& "C:\Users\Shivang\anaconda3\pythonw.exe" run_gui.py
```

## What shipped this session
| Area | What | Details |
|---|---|---|
| **Crash** | `0xC0000374` on encoder commands fixed — brain runs in a child process | `AERIS_LOADFREE…md` §6.6.3–6.6.4 |
| **Boot** | Split boot ~40–60s → **~20s** (pre-warm + child skips PyQt5) | `NEXT_LEVEL_PLAN.md` P0 |
| **Routing** | Arithmetic→`calculate` (0→68%, answers work), `search_web` 14→86%, `define_word` 9→86%, `get_time` 27→50%+ | `ROUTING_ACCURACY_AUDIT.md` |
| **Safety** | Reminder never → `empty_recycle_bin`; `"X kholo"` never → `add_expense` | `_guard_dangerous_route` |
| **"Won't open"** | Stale single-instance lock now taken over instead of silent exit | `single_instance.py` |
| **Routing anchors** | 8 deterministic no-retrain anchors: arithmetic→calculate, reminder-guard, kholo-guard, get_time, search_web, define_word, gcd_lcm, is-prime | `core/brain.py _ANCHORS`, `main_engine._guard_dangerous_route` |
| **Handler bugs (5)** | Hinglish calculate parsing · `quick_calc` error-leak · disambiguation swallow-rescue · memory recall-as-store · number→hex | various skills/core |
| **Split-parity** | intent chip forwards full dispatch · proactive double-consume fixed (`enable_scheduler=False`) | `brain_service`, `remote_brain` |
| **Docs/tooling** | `COMMANDS.md` (587 abilities, 20+ examples), `gen_commands_readme.py`, `tools/validate_command_routing.py` | — |
| **Plans** | This handoff · `NEXT_LEVEL_PLAN.md` · `SKILL_TRIM_CHECKLIST.md` · `ROUTING_ACCURACY_AUDIT.md` | — |

Fast lane: **2099 passing** throughout.

> **Known remaining quality gap = routing drift (retrain fixes it).** Smoke-testing
> confirmed the *handlers are correct when reached* — the failures are the stale
> neural head / k-NN mis-routing common commands. The built-in anchors patch the
> most common/dangerous cases deterministically; **`python -m core.retrain` is the
> clean wholesale fix.**
>
> **NEW — fix any mis-route yourself, no retrain:** edit **`data/routing_anchors.json`**
> and add `{"signal": "<regex>", "intent": "<skill from COMMANDS.md>", "exclude": "<optional>"}`,
> then restart AERIS. If a command routes to the wrong skill, that's now a one-line
> fix you control (the file has a `_help` + `_example`).

## ✅ Your action checklist (the remaining wins need you)
1. **Shakedown** — launch with the flag above, type ~15 commands (incl.
   `"thank you"`, `"ek joke sunao"`, `"12 plus 37 kitna hai"`, `"time batao"`).
   Confirm no crash + routing feels right.
2. **Retrain the neural head** (it's stale, on k-NN — the biggest remaining
   routing win): `python -m core.retrain`, then `python tools/validate_command_routing.py`
   (target 50% → 90%+).
3. **(Optional) Trim** — pick tiers in `SKILL_TRIM_CHECKLIST.md`; reply and I'll
   produce the exact diffs (I won't delete skills without your go-ahead).
4. **After 1–3 feel good:** tell me and I'll **flip `AERIS_SPLIT_BRAIN` to the
   default** (it's now both safer *and* faster) with an `AERIS_INPROCESS_BRAIN=1`
   escape hatch.

## The genuine "next level" beyond this (bigger projects)
- **Agentic capability (P2)** — multi-step "plan→act→observe" over the 587 skills
  (`agent_orchestrator` exists; harden + expand). Best done interactively, not in
  5-min loop ticks.
- **Persistent pre-warmed brain daemon** — would take split boot below ~5s.
- **Split-path polish** — richer intent chip; surface proactive offers in the GUI.

_Restart the loop (`/loop …`) or point me at any specific item above whenever you
want me to pick one up._
