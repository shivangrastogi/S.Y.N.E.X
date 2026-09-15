# AERIS — Next-Level Upgrade Plan (2026-08-01)

A single, prioritized plan that consolidates this session's findings into the
path from "works but rough" → **next-level assistant**. Ranked by impact/effort.
Companion docs: `ROUTING_ACCURACY_AUDIT.md`, `AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md`
(§6.6 crash fix), `AERIS_AUTONOMOUS_YEAR_PLAN.md` (agentic vision), `COMMANDS.md`.

## Where AERIS is now  *(updated 2026-08-01, end of hardening session)*
- ✅ **Crash fixed** — `0xC0000374` "2nd-prompt" crash solved by running the brain
  in a child process (`AERIS_SPLIT_BRAIN=1`). Proven end-to-end. *Not yet the default.*
- ✅ **"Won't open" fixed**, brain-first boot (33→27s; split ≈20s).
- ✅ **Abilities fully documented** — `COMMANDS.md`, **all 588 abilities now with 20+
  examples each** (generator hardened to guarantee the floor; was 575/588).
- ✅ **Routing lifted 50% → 74.8%** end-to-end (`brain.predict` + guards), WITHOUT a
  retrain — via the deterministic anchor/guard layer (P1c below, now far bigger than
  first scoped). Every core *action* (volume, music, screenshot, notes, reminders,
  search, time, file, kill, clipboard) + conversational (joke/story/motivate/brainstorm)
  now routes reliably. Full-suite tests green (3139).
- ⚠️ **Remaining ceiling → ~90% needs a retrain.** The last low commands are the
  **superseded stubs** (get_weather/system_info/take_screenshot vs. their better
  plugins) and the **calculator sprawl** (~107 calc skills steal `calculate`). Both
  are corpus decisions (P1a/P1b/P1d) — **your data, your call.**

---

## P0 — Make the crash fix the default (highest impact, lowest effort)
The crash is *solved* but off by default, so a normal launch still crashes.
1. **You**: run a real on-screen shakedown with `AERIS_SPLIT_BRAIN=1` (type ~15
   commands, incl. `"thank you"`, `"ek joke sunao"`). Confirm it feels right.
2. **Me — ✅ split-boot pre-warm SHIPPED (2026-08-01).** The child brain (torch in
   a child process = no GIL contention) is now kicked at window construction, so
   its load overlaps first paint + the staged boot instead of running after it
   (`_kick_brain_init_once`, idempotent → no double-spawn). Combined with the
   PyQt5 child-lean fix, **measured split boot-to-ready ≈ 20 s** (was ~40–60s) —
   now *faster* than the ~27s in-process boot AND crash-free. Verified offscreen:
   window 1.3s, one `isolated brain ready`, no crash, no orphaned child.
3. **Me (after your OK):** flip the default so split-brain is on without the flag;
   keep the in-process path behind `AERIS_INPROCESS_BRAIN=1` as an escape hatch.
   *(Split is now both safer and faster — the case for defaulting it is strong.)*

## P1 — Fix routing quality (50% → **74.8% done** → 90%+ needs retrain). The real "next level" lever.
This is the concrete form of your original *"ye sb itne formulas kyu?"* instinct.
**Status: P1c (deterministic layer) is essentially complete and shipped — it carried
routing from 50% to 74.8% with no retrain. P1a/P1b/P1d (corpus trim + retrain) are the
remaining lever to ~90%, and are yours.** Detail + measurements: `ROUTING_ACCURACY_AUDIT.md`.

**P1a — Trim the calculator sprawl (biggest single win). Needs your OK (your data).**
- **107 math/calc skills** today: `misc_calc` 25, `finance` 21, `number_props` 18,
  `health_split` 9, `fun_calc` 6, `physics` 6, `compute` 5, `geometry` 5,
  `gcd_ratio` 4, `fractions` 3, `color_roman` 2, `fuel_water` 2, `number_words` 1.
- **Target:** collapse to **~10** — one strong `calculate` (general expressions +
  %, powers, roots) + a few genuinely-distinct ones (unit convert, currency, BMI,
  EMI/loan, date math). Drop the one-off formula skills (trig/log/gcd/lcm/factorial/
  ratio/fuel — a general calculator already does these).
- **Impact:** fixes `calculate` **0% → high** (basic arithmetic is currently stolen
  100% by `gcd_lcm`/`log_calc`/`gst_calc`).

**P1b — De-duplicate the core-command thieves. Needs your OK.**
- Screenshots: **5 skills** (`take_screenshot`, `screenshot_full`, `screenshot_window`,
  `screenshots_folder`, `screenshot_to_phone`) → keep `take_screenshot` (full) +
  `screenshot_window` + `screenshot_to_phone`; fold the rest in.
- Weather: `get_weather` + `weather_local` + `weather_for_city` → **one** `get_weather`
  (auto local, optional city slot).
- Notes: `create_note` + `append_note` → one. Search: `search_web` + `search_in_browser`
  + `google_jump` → one. (Keep `world_time`/`timezone_convert` — genuinely distinct.)

**P1c — Deterministic anchor + guard layer (Me — safe, no retrain). ✅ DONE.**
A two-part deterministic router that runs around the k-NN classifier:
- **~18 anchors** in `core/brain._BUILTIN_ANCHORS` (run inside `predict`, before k-NN):
  arithmetic, get_time, search_web, define_word, gcd_lcm, number_properties,
  text_transform, count_chars, who_are_you, system_stats, unit(time), base_convert,
  uuid, clipboard_transform/paste, file_search, kill_process, tell_joke/tell_story/
  motivate_me, volume_up/down/mute, play_music.
- **8 conditional guards** in `main_engine._guard_dangerous_route` (run in `process_text`):
  reminder-family, open-X→app/site, weather→`weather_local` (**was `set_reminder`!**),
  system→`system_stats`, screenshot→`screenshot_full`, note→`create_note` (**was a junk
  `add_expense`**), `clear_chat` blocked unless explicit (**pep-talk was wiping the chat**),
  brainstorm→`brainstorm_ideas`. Guards are conditional (fire only on a clear signal that
  landed OUTSIDE the right family) so correct routes are never disturbed.
- **Handler dead-end sweep — 14 skills fixed.** A whole class of "assistant feels dumb"
  bugs: a skill gated on a `required_entities` slot the entity extractor can't fill (the
  argument is *embedded in the verb phrase* or *ambient* — clipboard, screen), so it asked
  a needless "kya?" even when you already gave it. **Recipe (proven 14×):** `required_entities=[]`
  + recover the argument from `raw_text` (leading-trigger-strip / word-filter / verbatim tail
  for URLs). Fixed: `clipboard_transform`, `file_search`, `kill_process`, `qr_code`,
  `translate_to_hindi/english`, `date_diff`, `recall`, `text_expand`, `currency_convert`,
  `vault_get`, `add_task`, `brightness_set`, `volume_set`. Locked by
  `tests/test_deadend_recovery.py` (+ `test_qr_payload`, `test_translate_payload`,
  `test_productivity_extras`). Verified safely (read-only handlers, or side-effect-free paths —
  e.g. `add_task`'s empty-check returns before opening the workbook; volume/brightness tested
  via their pure parser only).
  - *Remaining candidates (same recipe, not yet done):* **mild** — `teach_command`,
    `forget_command`, `text_expand_add`, `routine_enable/disable`, `create_folder`, `open_file`,
    `copy_history_item`, `spotify_play_track`, `add_meeting` (needs 2 entities); **destructive
    (need your care, NOT autonomous)** — `send_whatsapp`, `vault_delete`, `set_timer`,
    `quick_timer`, `routine_run`, `add_expense`.
- **Result: 50% → 74.8% routing + 14 dead-ends removed**, all locked by
  `tests/test_routing_anchors.py` + `tests/test_dangerous_route_guard.py` +
  `tests/test_deadend_recovery.py` + `tests/test_productivity_extras.py` (full suite ~3,200).
  This bought most of P1a's win *before* a retrain, exactly as planned.

**P1d — Retrain (You).** After P1a–b, `python -m core.retrain` so the neural head is
fresh on the slim corpus. Then re-run **`python validate_command_routing.py`** —
target 90%+ (baseline 50%).

## P2 — Next-level abilities (agentic, not more one-shot skills)
The skill set is saturated (587); *more* one-shot skills = more bloat. The upgrade
is **capability classes**, per `AERIS_AUTONOMOUS_YEAR_PLAN.md`:
- **Multi-step agent**: "trip plan banao aur calendar me daal do" → plan→act→observe
  over existing skills (agent_orchestrator already exists — harden + expand).
- **Proactive** already built (mode suggestions over the bus) — surface it in the
  split-brain GUI path (currently reads in-process).
- **Screen-aware reasoning** (`screen_agent`) — the real differentiator; deepen it.

## What I can do without you vs. what needs you
| Can do + test now | Needs your OK / action |
|---|---|
| P1c pre-router anchors (fix worst mis-routes, dangerous ones) | P1a/P1b corpus trim (your training data) |
| P0 pre-warm split boot; flip default (after your shakedown) | P1d retrain (`python -m core.retrain`) |
| P2 agent hardening | Deciding which skills to cut |

## Where the ball is now — the decisions that unlock the rest
Everything I can safely do without touching your training data or shipping a
destructive default **is done** (P1c routing layer, COMMANDS.md, all tests green).
The next moves each need a **you** decision:

1. **Retrain to bank the last ~15 points (P1a/P1b/P1d).** The deterministic layer
   is holding routing at 74.8%; a corpus trim + `python -m core.retrain` is what
   takes it toward ~90% *and* lets the stubs (weather/system/screenshot) be
   re-pointed to their real plugins. Start point: `docs/SKILL_TRIM_CHECKLIST.md`.
   - *Quick partial you can do without a full trim:* re-point the ~13 superseded-stub
     targets in `data/command_examples.json` to the canonical plugin (e.g.
     `take_screenshot`→`screenshot_full`). Zero behaviour change, +several metric points.
2. **Flip split-brain to default (P0).** It's now both *safer* (crash-free) and
   *faster* (~20s vs ~27s). Needs one on-screen shakedown from you, then I flip it
   (in-process stays behind `AERIS_INPROCESS_BRAIN=1` as an escape hatch).
3. **`shutdown_pc` safety.** "shutdown karo"/"power off" currently fail *safe* (route
   to cancel/factorial → nothing happens). Making them reliably shut down is a
   destructive capability — recommend adding a **confirmation prompt** to `shutdown_pc`
   first; I left this untouched on purpose.
4. **P2 agentic** (multi-step agent, proactive in the split GUI, screen-aware
   reasoning) — the genuine "next level" once routing/corpus are settled.

> **Bottom line:** the "make it not feel dumb" work (reliable routing, no dangerous
> mis-fires, complete docs) is shipped and test-locked. The remaining lifts are
> corpus/retrain (yours) and the agentic layer (P2) — not more deterministic patches.
