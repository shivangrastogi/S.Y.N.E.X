# AERIS — Skill-Trim Checklist (for your approval) — 2026-08-01

**Reframe first:** after the **arithmetic pre-router** (shipped) deflects basic
sums to `calculate`, the "107 calculators are hurting routing" problem is *mostly
already fixed*. So you do **not** need a big cut. Most of the 107 are genuinely
distinct, useful calculators. This checklist is now small and optional — tick
what you want, leave the rest.

Legend: **[KEEP]** don't touch · **[MERGE]** fold into one owner · **[CUT?]**
optional slim (niche/rarely asked) · **[RETRAIN]** the real remaining win.

---

## ✅ Tier 1 — TRUE duplicates (recommended MERGE — clear routing win)
These overlap the core commands and split the k-NN vote. Keep one owner each.

| Keep | Fold in (cut) |
|---|---|
| `take_screenshot` (full screen) | `screenshot_full` (identical) |
| `get_time` | `current_time` (identical) |
| `create_note` | `append_note` (or keep both if append is distinct) |
| `get_weather` (auto-local + optional city slot) | `weather_local`, `weather_for_city` |
| `search_web` | `search_in_browser`, `google_jump` (keep if you like the "jump" UX) |

*(Keep the genuinely-distinct ones: `screenshot_window`, `screenshot_to_phone`,
`world_time`, `timezone_convert`, `memory_stats`/`disk_space` — these do different things.)*

## 🟡 Tier 2 — Overlap the general calculator (OPTIONAL cut — low harm now)
The pre-router already sends bare arithmetic to `calculate`, so these no longer
*steal* it; cutting them only slims the corpus. `quick_math`/`calculate` cover them.
- `gcd_lcm`, `log_calc`, `factorial_power`, `trig_calc`, `modulo_calc`,
  `number_stats`, `simplify_ratio`, `sequence_calc`, `rounding_sigfig`.

## 🟡 Tier 3 — Niche / rarely-asked (OPTIONAL cut for a leaner corpus)
Fun but seldom used; each still costs a corpus slot + a k-NN neighbour.
- `numerology`, `zodiac_sign`, `scrabble_score`, `beaufort_scale`, `richter_scale`,
  `dew_point`, `led_resistor`, `caesar_cipher`, `thunder_distance`, `decibel_scale`,
  `ppi_calculator`, `frequency_wavelength`, `heat_index`, `wind_chill`, `uv_index`,
  `coordinate_distance`, `week_number`.

## ✅ Tier 4 — KEEP (genuinely useful, distinct — do NOT cut)
Finance: `emi_calc`, `gst_calc`, `sip_calculator`, `compound_interest`,
`simple_interest`, `discount_calc`, `tip_calc`, `profit_loss`, `percent_change`,
`markup_margin`, `savings_goal`, `electricity_bill`, `fuel_trip_cost`.
Health: `bmi_calc`, `bmr_calorie`, `bill_split`, `ideal_weight`, `protein_needs`,
`one_rep_max`, `heart_rate_zones`, `water_intake`.
Utility/convert: `qr_code`, `base64_encode/decode`, `hash_text`, `roman_convert`,
`color_convert`, `number_to_words`, `ordinal_number`, `unit`/currency converters,
`area_calc`, `paint_quantity`, `tile_count`, `download_time`, `travel_time`,
`aqi_category`, `ohms_law`, geometry + physics set.

---

## 🎯 The real remaining win — RETRAIN (your action)
Trimming Tiers 1–3 helps, but the **biggest** routing lift is retraining the
neural head, which is currently **stale (on k-NN fallback)** — that's why
semantically-near-but-wrong neighbours win. After any trims:
```
python -m core.retrain
python validate_command_routing.py    # target: 50% → 90%+
```

## How to approve
Reply with which tiers to apply (e.g. "do Tier 1 + Tier 3, skip Tier 2"). I'll
produce the exact skill-file edits as a diff for your review — I won't delete any
of your skills without your explicit go-ahead. Then you retrain.
