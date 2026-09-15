# Robustness + New Abilities Batch (2026-07-19)

*User: "add intents things etc make it very robust." Two robustness levers
(normalizer, enrichment) + a new standalone system-utility batch. All
local, no APIs.*

## 1. Normalizer v2 — the whole intent system got more robust

`core/normalizer.py` ab **Hinglish/SMS shorthand canonicalize** karta hai —
token-level, whole-word only. Since it runs on BOTH training patterns and
live queries (shared path), a pattern "notepad band karo" aur query
"notepad band kro" ab ek hi key par milte hain.

Expansions: `kro→karo, kr→kar, krdo→kardo, h→hai, nhi→nahi, yr→yaar,
plz→please, jldy→jaldi, msg→message, gana→gaana, u→you, coz→because…`
+ 3+ repeated LETTERS collapse (`haaaan→haan, plsss→please`).

**The important half — no corruption** (all guarded by tests + a full-corpus
audit):
- Digits never shrink: `1000` stays `1000` (elongation collapse is
  letters-only — the first draft's `1000→100` bug was caught by the audit).
- "kaha" (said) ≠ "kahan" (where) — the false mapping was caught and removed.
- URLs/paths/math tokens (`. : / + - %`) skipped entirely.
- Only 11 existing corpus patterns changed — every one an improvement
  ("gana bajao"→"gaana bajao", "battery kitni h"→"…hai").

## 2. New standalone system utilities (6 intents, all local)

`core/sys_utils.py` + `skills/sys_utils_skill.py` — psutil + Windows ctypes,
zero network:

| Bolo | Ability | Live-verified |
|---|---|---|
| "disk space batao" / "c drive me kitni jagah hai" | `disk_space` — per-drive free/total | C: 24GB/333GB ✓ |
| "kaunsa app RAM/CPU kha raha hai" | `top_process` — aggregated by name | msedge 4.3GB ✓ |
| "computer kitni der se on hai" | `system_uptime` | 2 din 15 ghante ✓ |
| "sone mat dena" / "keep awake on" | `keep_awake_on` — persistent power request | toggles ✓ |
| "ab so sakte ho" | `keep_awake_off` | ✓ |
| "recycle bin khali karo" | `empty_recycle_bin` — **confirm-gated** | ✓ |

Keep-awake robustness note: `SetThreadExecutionState` is thread-scoped, so
a short skill-call thread would lose the request instantly. It's held on a
dedicated daemon thread that re-asserts every 50s until turned off — a real
keeper, not a one-shot.

## 3. Confusion-zone enrichment (+92 patterns, all validated)

Earlier golden misses + brain_health confusion pairs guided targeted
patterns for the boundary intents (open_app vs close/shutdown/profile,
stop_music vs shutdown_system, greet vs detect_scene, calculate vs
day_summary, play_music…). A validator rejected any candidate that was a
golden held-out phrase (2 caught), already present, or owned by another
intent (1 cross-owner collision caught) — nothing force-added.

**Before → after (k-NN fallback, live)**: "chrome kro" → app_mute ❌ → 
**open_app ✓**; "gana chala kro yr" → set_reminder ❌ → **play_music ✓**.
9/9 shorthand queries now route correctly even before the neural retrain.

## Corpus state

**413 intents · 3591 patterns · hash `c19536c4…`** (was 407/3456). Bundle +
COLAB doc synced. Golden set 107 items (+6 for new intents, 0 collisions).
Fast lane **708/708** (+32 tests), intent-classifier slow lane 14/14.

**Retrain pending** — `python -m core.retrain`. The 2 fixed misses prove
the k-NN floor rose; the neural model (82% golden baseline, far better at
paraphrase) will push these further once retrained.
