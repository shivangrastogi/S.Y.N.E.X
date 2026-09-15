# Standalone Abilities (2026-07-19) — AERIS ka apna dimag, koi API nahi

*Principle: nayi ability = local compute (embedded Qwen + apna sentence
encoder + local whisper + pure-python parsers). Network sirf wahan jahan
data hi bahar ka ho (weather/web). Pure-python libraries (pypdf,
python-docx) install karna theek hai — wo aapki machine ka code hai,
kisi ka server nahi.*

## Naya kya bola ja sakta hai

| Bolo | Kya hota hai | Tech (sab local) |
|---|---|---|
| "index folder C:\Notes" (pehle se tha) | Docs index — **ab PDF/DOCX bhi** | pypdf + python-docx + apna encoder |
| **"docs se batao project ka deadline kya hai"** | Retrieval + jawab **citations ke saath** | encoder + embedded Qwen (`doc_answer`) |
| **"file ka summary do C:\x\plan.pdf"** | 4-6 line ka saar | parsers + Qwen (`file_summary`) |
| **"clipboard ka summary do"** | Copied text ka summary | Qwen (`clipboard_summarize`) |
| **"clipboard professional banao"** | Professional English rewrite | Qwen (`clipboard_rewrite`) |
| **"clipboard bullets banao"** | Crisp bullet points | Qwen (`clipboard_bullets`) |
| **"clipboard se numbers/emails/links nikalo"** | Instant extraction | pure regex (`clipboard_extract`) |
| **"local gaana bajao kesariya"** | Disk se fuzzy match + default player | `core/local_music` (`local_music_play`) |
| "local music bajao" | Shuffle — koi bhi local track | — |
| "music library reindex karo / dikhao" | Index rebuild / stats | Music+Downloads (+ settings `music_dirs`) |
| **"audio transcribe karo C:\recs\m.wav"** | File → text (lambi ho to data/notes mein) | local faster-whisper (`transcribe_file`)* |
| "isko english me translate karo" (pehle se tha) | **Ab clean local tier** — persona/120-token bug fixed | `local_llm.generate` |

\* faster-whisper installed nahi hai to skill saaf bata deta hai
(`pip install faster-whisper` — one-time; uske baad poora offline).
LIVE mic voice stack (Google en-IN STT + Neerja TTS) untouched hai —
ye sirf FILE transcription hai.

## Infrastructure

- **`local_llm.generate(prompt, system, max_tokens≤512)`** — long-form,
  PERSONA-FREE generation. Assistant chat path 120-token TTS cap + "sir"
  style inject karta tha — working text (translation/summary/rewrite) ke
  liye ye dedicated clean path hai.
- **Doc index v2** — chunk TEXT ab meta mein persist hota hai (answer
  synthesis ke liye); purane index par `answer()` khud "dobara index
  banao" bolta hai.
- GUI: Abilities panel registry-driven hai — ye 9 nayi abilities agli
  boot par apne aap dikhengi, zero GUI edits.

## Corpus state

407 intents · 3456 patterns · hash `fc018b79…` (bundle + COLAB synced).
Golden set: 101 items (+6 naye intents ke liye; ek purana item replace
hua kyunki learning loop ne wahi phrase real usage se seekh liya tha —
golden discipline working as designed). **Retrain pending — `python -m
core.retrain`** (naye intents tab tak k-NN/exact se chalenge).

---

## /loop expansion (2026-07-19/21) — 27 more standalone abilities, zero API

Self-paced build loop batches. Every ability is local compute (stdlib /
psutil / ctypes / os / the embedded model) — nothing leaves the machine.

| Ability (intent) | Bolo | Tech |
|---|---|---|
| `world_time` | "london me kitne baje hain" | stdlib zoneinfo (599 zones) |
| `date_math` | "aaj se 45 din baad kaunsi date" | datetime |
| `days_until` | "christmas me kitne din bache" | date parser |
| `age_calc` | "main 1995 me paida hua age batao" | datetime |
| `coin_toss` / `dice_roll` | "sikka uchalo" / "d20 roll karo" | secrets.SystemRandom |
| `random_number` / `random_pick` | "1 se 100 number" / "in me se ek chuno" | random |
| `folder_stats` | "downloads me kitni files hain" | os.walk (capped) |
| `find_large_files` | "bade files dhundo" | heapq.nlargest |
| `read_file_aloud` | "is file ko padho X.txt" | reply-TTS |
| `unit_convert` | "10 km me kitne mile" | factor table + affine temp |
| `disk_space` / `top_process` / `system_uptime` | "disk space batao" / "ram kaun kha raha" / "kitni der se on" | psutil |
| `keep_awake_on/off` | "sone mat dena" / "ab so sakte ho" | SetThreadExecutionState |
| `empty_recycle_bin` | "recycle bin khali karo" (confirm-gated) | SHEmptyRecycleBinW |
| `discount_calc` / `gst_calc` / `tip_calc` | "1500 pe 20% off" / "2000 pe 18% gst" / "800 pe 10% tip" | pure math |
| `emi_calc` / `simple_interest` | "5L loan 12% 24 months emi" / "10000 pe 8% 3 saal" | finance math |
| `password_strength` | "password strength check karo <pw>" | entropy + common-word penalty |
| `stopwatch_start/check/stop` | "stopwatch start/kitna hua/stop karo" | monotonic count-up |
| `number_to_words` | "1234567 ko words me batao" | Indian lakh/crore + international |

**Doc Brain v2 / clipboard AI / local music / transcribe / translator**
(earlier batch, above) round out the standalone set. Bugs caught + fixed
during the loop: normalizer digit-corruption (1000→100), "kaha"→"kahan"
false map, password-skill "check karo" mistaken for a password,
_international thousands >99, and the long-standing **eval-harness
TrustGate flake** (wall-clock quiet-hours coupling → pinned to a fixed
noon clock, deterministic now).

Corpus grew across the loop to **434+ intents** (hash tracked in
COLAB_TRAINING.md, bundle synced each batch). Golden set grew in step,
always held-out. **Retrain still pending — `python -m core.retrain`.**

---

## Full standalone catalog (2026-07-21, /loop iters 1-25) — 68 abilities

Every ability below is 100% local — stdlib / psutil / ctypes / os, or
AERIS's OWN embedded Qwen (no external API, no network). Two test layers
protect them: a garbage-input robustness guard (caught 6 real bugs —
overflow, hang, leaks) and an end-to-end exact-match routing integration
test (every intent's pattern routes back through the live brain).

**Date/Time (7):** world_time · date_math · days_until · age_calc ·
day_of_week · time_until · timezone_convert

**Random/decision (4):** coin_toss · dice_roll · random_number ·
random_pick

**Files (3):** folder_stats · find_large_files · read_file_aloud

**System (6):** disk_space · top_process · system_uptime · keep_awake_on/off
· empty_recycle_bin (confirm-gated)

**Money/math (11):** discount_calc · gst_calc · tip_calc · emi_calc ·
simple_interest · percent_change · bmi_calc · bill_split · gcd_lcm ·
simplify_ratio · number_stats · factorial_power

**Numbers/dev (6):** unit_convert · number_to_words · base_convert ·
number_properties · caesar_cipher · phonetic_spell

**Text (10):** color_convert · roman_convert · morse_code · palindrome_check
· anagram_check · text_transform · count_chars · acronym_maker · text_stats
· stopwatch (start/check/stop) · password_strength

**Local-LLM utilities — AERIS's own brain (15):** fix_grammar ·
brainstorm_ideas · explain_simply · make_title · shorten_text · define_word
· pros_cons · how_to_steps · write_poem · motivate_me · tell_joke ·
tell_story · tell_riddle · synonyms_antonyms · rephrase_text · fun_fact ·
give_compliment

Plus the earlier batch (doc brain v2, clipboard AI, local music,
transcribe, clean translator) and every pre-existing skill.

**Corpus:** ~474 intents (hash tracked in COLAB_TRAINING.md, aeris_train_
bundle.zip synced each batch). **Test suite:** 1175+ fast-lane green.
**Retrain still pending** — `python -m core.retrain`; all abilities work
on k-NN/exact meanwhile (verified end-to-end each iteration).

**Extraction pattern lessons (for future skills):**
- Payload AFTER the command word → `_strip(pattern, count=1)`.
- Payload can be BEFORE the command ("<topic> ke fayde batao") →
  `_drop_words(cmd_set)` token filter.
- Never let a repeated-letter collapse touch digits; cap primality/
  factorial/power/date-offset inputs; a skill must never hang or crash on
  garbage — the robustness guard enforces this.
