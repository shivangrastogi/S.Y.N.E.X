# AERIS — Routing Accuracy Audit (2026-07-27)

While curating natural example phrases for `docs/COMMANDS.md`, I ran **528
real-user phrasings of 24 core commands** through the live classifier
(`brain.predict`). The result is the single most important quality finding of
this work:

> ## ⚠️ Only **50%** (264/528) of natural core-command phrasings route to the intended command.

This is the concrete, quantified form of the *"ye sb itne formulas kyu?"*
concern: **587 intents is too many, and overlapping/duplicate skills are
stealing the core commands' phrases.**

## Per-command routing accuracy

| Command | Correct | Command | Correct |
|---|---|---|---|
| `open_app` | 77% | `shutdown_system` | 45% |
| `fix_grammar` | 73% | `set_reminder` | 41% |
| `volume_down` | 68% | `create_note` | 41% |
| `brainstorm_ideas` | 68% | `take_screenshot` | 32% |
| `play_music` | 64% | `system_info` | 32% |
| `tell_joke` | 64% | `get_weather` | 27% |
| `volume_up` | 64% | `get_time` | 27% |
| `volume_mute` | 59% | `search_web` | 14% |
| `tell_story` | 59% | `define_word` | 9% |
| `motivate_me` | 59% | `open_website` | 9% |
| `shutdown_system` | 45% | **`calculate`** | **0%** |

## Two kinds of mis-route

**① Harmless — routes to a functionally-equivalent (often *better*) skill.**
The core intent is a generic; a more specific skill answers correctly.
- `take_screenshot` → **`screenshot_full`** (same result)
- `get_time` → **`current_time`** (same result)
- `system_info` → **`system_stats` / `memory_stats` / `disk_space`** (more specific — good)
- `get_weather` → **`weather_local` / `weather_for_city`** (both give weather)
- `open_website` → **`youtube_jump` / `wikipedia_jump` / `open_in_browser`** (specific jumps — good)
- `set_reminder` → **`set_timer` / `add_task` / `time_until`** (reminder-adjacent)

These aren't bugs — they're **duplication**. The core intent and the specific
skill overlap; either is fine, but the redundancy bloats the corpus and hurts
the *other* commands' accuracy.

**② Harmful — routes to a WRONG/unrelated skill (real defects, some dangerous):**

| User says | Routes to | Should be | Severity |
|---|---|---|---|
| "yaad dilana bill bharne ka" | **`empty_recycle_bin`** | `set_reminder` | 🔴 destructive |
| "amazon kholo" | **`add_expense`** | `open_website` | 🔴 wrong action |
| "kal 9 baje reminder set karo" | **`dice_roll`** | `set_reminder` | 🔴 |
| "google karo best laptops 2026" | **`full_system_health`** | `search_web` | 🔴 |
| "12 plus 37 kitna hai" | **`gcd_lcm`** | `calculate` | 🟠 wrong math |
| "999 minus 88 kitna" | **`log_calc`** | `calculate` | 🟠 |
| "15 percent of 2000" | **`gst_calc`** | `calculate` | 🟠 wrong tax context |
| "iska matlab batao X" | **`tell_riddle` / `fun_fact`** | `define_word` | 🟠 |
| "likho ye note grocery list" | **`add_expense`** | `create_note` | 🟠 |
| "note save karo password hint" | **`password_generate`** | `create_note` | 🟠 |
| "samay kya hua hai" | **`change_log`** | `get_time` | 🟠 |
| "time bolo" | **`voice_faster`** | `get_time` | 🟠 |

## Root cause

1. **Skill sprawl / duplication.** 587 intents, ~108 of them calculators. Basic
   arithmetic (`calculate`) is out-competed **100% of the time** by specialized
   math skills (`gcd_lcm`, `log_calc`, `gst_calc`, `trig_calc`, `factorial_power`…).
   Screenshots, weather, notes, search, define each have 2–5 overlapping skills.
2. **k-NN-only routing on a drifted neural head.** The neural classifier is stale
   (running on the k-NN fallback), so semantically-near-but-wrong neighbours win
   among 587 candidates. With fewer, cleaner intents the k-NN would be far tighter.

## Recommended fixes (prioritized)

1. **🔴 Trim the corpus (biggest win, needs your OK — it's your training data).**
   - Collapse the ~108 math skills: keep a single powerful `calculate` +
     a handful of genuinely-distinct ones; drop the one-off formula skills
     (the "formulas" you already wanted gone). This alone fixes `calculate` 0% → high.
   - De-duplicate: `take_screenshot`/`screenshot_full`, `get_time`/`current_time`,
     `create_note`/`append_note`, the multiple weather/search skills → one owner each.
2. **🔴 Fix the dangerous collisions immediately** regardless of retrain: a reminder
   phrase must never reach `empty_recycle_bin`, and "kholo" must never reach
   `add_expense`. Add negative/guard patterns or exact-match anchors for these.
3. **🟠 Add exact-match anchors for the core intents** so the most common exact
   phrasings ("screenshot lo", "time batao", "reminder set karo", "note banao",
   "12 plus 37") deterministically hit the core intent before k-NN runs.
4. **Retrain** (`python -m core.retrain`) after trimming so the neural head is
   fresh on the slimmed corpus — you run training.

## How this was measured

`scratchpad/validate_curated.py` → loads the real engine, runs every phrase in
`data/command_examples.json` through `brain.predict`, checks `pred.intent ==
command`. Re-run it after any corpus change to track accuracy back up toward 100%.

---

# UPDATE — 2026-08-01 (deterministic hardening, no retrain)

Executed recommendations #2 and #3 above **without touching the training corpus**
(retrain remains yours). `validate_command_routing.py` now measures the **real
end-to-end pipeline** (`brain.predict` **+** `_guard_dangerous_route`), not the raw
classifier alone — so the number reflects what the user actually gets.

### Progress
| Date | Measured | What |
|---|---|---|
| 2026-07-27 | **50%** | baseline, raw `brain.predict` |
| 2026-08-01 | **60.8%** | raw `brain.predict` after the anchor layer grew |
| 2026-08-01 | **65.5%** | end-to-end (predict + guards) |
| 2026-08-01 | **69.5%** | + conversational anchors (joke/story/motivate) |
| 2026-08-01 | **74.8%** | **+ volume/music anchors** (up/down/mute/play all 95-100%) — ships today |

Plus **+13 phrasings** route to a *better canonical skill* (weather→`weather_local`,
system→`system_stats`, screenshot→`screenshot_full`) that the metric still counts as
"wrong" only because `command_examples.json` names the deprecated **stub** as expected.
Real routing quality is therefore materially above 65.5%.

### What was implemented
- **Deterministic anchors** (`core/brain._BUILTIN_ANCHORS`, run inside `predict`):
  arithmetic pre-router, get_time, search_web, define_word, gcd_lcm, number_properties,
  text_transform, count_chars, who_are_you, system_stats, unit(time), base_convert,
  uuid, clipboard_transform/paste, **file_search**, **kill_process**, and the
  entertainment trio **tell_joke / tell_story / motivate_me** (these were scattering
  to play_music/current_time/keep_awake_on; the skills are already LLM-backed, so this
  was pure routing — lifted them to 95/100/86%), and the core actions **volume_up /
  volume_down / volume_mute / play_music** (the modifier word disambiguates up/down/mute;
  these were mis-routing to the OPPOSITE direction or to create_note — now 95-100%).
  Locked by `tests/test_routing_anchors.py`.
- **8 conditional route guards** (`core/main_engine._guard_dangerous_route`, run in
  `process_text`) — each fires only on a clear signal that landed OUTSIDE the right
  skill family, so correct routes are never disturbed:
  1 reminder→reminder-family · 2 "open X"→open_app/website · 3 weather→`weather_local`
  (**was `set_reminder` — would CREATE a reminder!**) · 4 system→`system_stats` ·
  5 screenshot→`screenshot_full` · 6 note→`create_note` (**was `add_expense` — junk
  expense**) · 7 `clear_chat` blocked unless an explicit wipe word (**pep-talk was
  wiping the conversation**) · 8 brainstorm→`brainstorm_ideas`.
  Measured impact: of 200 mis-routes, **39 rescued** (26 → exact expected command,
  13 → better canonical skill). Locked by `tests/test_dangerous_route_guard.py` (43).
- **Handler dead-end fixes** (same "ambient/embedded argument" class): `clipboard_transform`,
  `file_search` (`_fs_query`), `kill_process` (`_proc_name`) no longer gate on a
  `content` slot the extractor can't fill; they recover the argument from `raw_text`.
  Locked by `tests/test_productivity_extras.py`.

### Still open — needs YOU (corpus owner) or the LLM layer
- **Re-point or de-dup the stubs.** `get_weather` (a hardcoded "25°"), `system_info`,
  `take_screenshot`, `get_time` are superseded by better plugins. Either re-point their
  `command_examples.json` targets to the canonical plugin (fixes the metric, zero
  behaviour change) **or** de-dup the patterns + `python -m core.retrain`.
- **`calculate` 0% / `define_word` / `search_web`** — the ~108 math skills still
  out-compete `calculate`; the arithmetic anchor covers plain sums but the corpus trim
  is the real fix.
- **`shutdown_system`** — "shutdown karo"→`cancel_shutdown`, "power off"→`factorial_power`.
  Currently **fails safe** (nothing shuts down). Fixing = enabling reliable auto-shutdown;
  recommend adding a **confirmation** to `shutdown_pc` first, then re-point. *Not*
  auto-fixed — a destructive capability shouldn't be wired up unattended.
- ~~**Conversational scatter** (`motivate_me`, `tell_story`, `tell_joke`)~~ — **DONE
  2026-08-01.** These skills were *already* LLM-backed (`core/local_llm`); the problem
  was routing, fixed with the entertainment anchors above (now 86-100%). No LLM-fallback
  rewire needed.
