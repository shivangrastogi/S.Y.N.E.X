"""Regenerate docs/COMMANDS.md from the live skill REGISTRY.

Run it any time you add/change skills:

    python gen_commands_readme.py

It introspects every registered skill (name, description, real router
patterns), groups them into categories, and writes a complete reference with
20+ example phrases per ability. Examples are the skill's REAL trigger phrases
(guaranteed to route), padded with natural imperative variations where a skill
is example-thin. On-device, no network.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

_ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Category mapping: (key, title, keywords matched against module+name) ──
CATS = [
    ("system",   "🖥️ System, Power & Diagnostics",
     ["system_skill", "sys_util", "windows_power", "diagnostic", "brightness", "app_audio", "power", "cpu", "battery", "disk", "volume", "mute", "lock", "shutdown", "restart", "sleep_mode", "gpu", "take_screenshot", "screenshot", "system_info", "monitor_swap", "system_health", "settings_schema", "settings_panel", "security_skill", "telemetry", "status_report", "first_run", "gen_tools", "command_palette", "routines_view", "repeat_last"]),
    ("windows",  "🪟 Apps & Window Management",
     ["window_manager", "open_app", "close_app", "launch", "snap", "minimize", "maximize", "app_"]),
    ("web",      "🌐 Web & Browser",
     ["browser", "web_jump", "web_search", "search_web", "tab", "youtube", "open_website", "url"]),
    ("media",    "🎵 Media & Music",
     ["local_music", "spotify", "music", "song", "playback", "now_playing", "media_", "podcast", "volume_"]),
    ("clipboard", "📋 Clipboard Superpowers",
     ["clipboard", "clip_", "copied"]),
    ("docs",     "📄 Documents, Files & Q&A",
     ["doc_qa", "docs_gen", "file_", "document", "pdf", "folder", "docs_skill", "sheets_sync", "sheets", "outlook_email", "email"]),
    ("dev",      "💻 Developer Tools",
     ["dev_tool", "dev_format", "code_writer", "codec", "dep_validator", "change_log", "docs_gen_skill", "git", "json", "regex", "hash", "base64", "uuid", "snippet"]),
    ("writing",  "✍️ Text, Writing & Language (AI)",
     ["llm_util", "text_fun", "grammar", "rephrase", "translate", "summar", "title", "shorten", "poem", "story", "synonym", "rhym", "dictionary", "leet", "llm_chat", "text_stats"]),
    ("math",     "🧮 Math, Finance & Calculators",
     ["misc_calc", "finance", "number_props", "physics", "geometry", "compute", "fun_calc", "health_split", "expense", "color_roman", "math", "calc", "convert", "unit", "gcd_ratio", "fuel_water", "fractions", "number_words"]),
    ("time",     "⏰ Time, Productivity & Automation",
     ["datetime", "productivity", "workspace_tracker", "automation", "reminder", "timer", "alarm", "schedule", "calendar", "day_summary", "activity_digest", "briefing", "recap", "mode_skill", "mode", "pomodoro", "stopwatch", "journal", "macro", "chain_skill", "chain", "get_time", "create_note"]),
    ("voice",    "🎙️ Voice & Speech",
     ["voice_memo", "voice_tuning", "whisper_stt", "stt", "tts", "dictate", "speak", "transcribe"]),
    ("vision",   "👁️ Vision, Gestures & Screen",
     ["gesture", "maps_gesture", "screen", "ar_overlay", "ocr", "camera", "custom_gesture", "calibration", "object_skill"]),
    ("phone",    "📱 Continuity & Phone Bridge",
     ["cloud_bridge", "continuity", "phone", "remote", "presence", "sync_skill", "notification_mirror"]),
    ("memory",   "🧠 Memory & Knowledge Graph",
     ["kg_skill", "semantic", "memory", "remember", "recall", "knowledge", "teach", "vault", "learning_skill"]),
    ("personal", "🎨 Personalization & Themes",
     ["theme", "personal", "calibrat", "tune", "preference"]),
    ("admin",    "🔧 Users, Permissions & Plugins",
     ["master_permission", "master_user", "plugin", "permission", "user_"]),
    ("info",     "📊 Quick Info, Notifications & Briefings",
     ["quick_info", "briefing", "weather", "news", "quote", "fact", "hud", "transcript", "response_enricher", "digest", "notification", "info_skills", "help_catalog", "status_report"]),
    ("fun",      "🎉 Fun & Casual",
     ["fun", "joke", "riddle", "compliment", "motivate", "fortune", "dice", "coin", "flip", "greet", "random_skill", "festival_zodiac", "zodiac", "shopping_recipe", "recipe"]),
]
FALLBACK = ("misc", "🧩 More Abilities")

# Core intents live in data/intents.json (not the @skill registry) and carry no
# description — supply one here so the reference is complete + human-readable.
CORE_DESC = {
    "open_app": "Open / launch an application.",
    "close_app": "Close a running application.",
    "open_website": "Open a website in the browser.",
    "search_web": "Search the web (Google) for something.",
    "play_youtube": "Play something on YouTube.",
    "play_music": "Play music.",
    "stop_music": "Stop or pause music.",
    "take_screenshot": "Capture a screenshot of the screen.",
    "system_info": "Show system info — CPU, RAM, disk, etc.",
    "shutdown_system": "Shut down / restart / sleep the PC.",
    "get_time": "Tell the current time.",
    "get_weather": "Current weather / today's forecast.",
    "set_reminder": "Set a reminder for later.",
    "schedule_meeting": "Schedule a meeting or calendar event.",
    "create_note": "Jot a quick note.",
    "calculate": "Evaluate a math expression.",
    "greet": "Say hello / greet AERIS (small talk).",
}


# Skills whose MODULE name misleads the keyword match (e.g. add_task lives in
# expense_tracker → "expense" → Math). Pin these to the right (key, title), which
# MUST match the corresponding CATS entry so the doc groups them together.
_TIME = ("time", "⏰ Time, Productivity & Automation")
_DEV = ("dev", "💻 Developer Tools")
_FUN = ("fun", "🎉 Fun & Casual")
_NAME_OVERRIDES = {
    "add_task": _TIME, "add_meeting": _TIME, "next_birthday": _TIME,
    "weekend_countdown": _TIME, "week_number": _TIME,
    "duration_humanize": _TIME, "sleep_cycle": _TIME,
    "qr_code": _DEV, "caesar_cipher": _DEV, "color_convert": _DEV,
    "roman_convert": _DEV, "number_to_words": _DEV,
    "scrabble_score": _FUN,
}


def categorize(name, mod):
    if name in _NAME_OVERRIDES:
        return _NAME_OVERRIDES[name]
    hay = (mod + " " + name).lower()
    for key, title, kws in CATS:
        if any(kw in hay for kw in kws):
            return (key, title)
    return FALLBACK


def _is_imperative(p):
    pl = p.lower()
    if pl.endswith("?"):
        return False
    return not any(pl.startswith(q) for q in
                   ("kya ", "kaise ", "what ", "how ", "when ", "who ", "why ", "where ", "is ", "are "))


def variations(patterns, target=20):
    out, seen = [], set()

    def add(x):
        k = x.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(x)

    for p in patterns:
        add(p)
    imps = [p for p in patterns if _is_imperative(p)]
    pool = imps or patterns
    # Address + politeness tokens only — natural on ANY phrasing (imperative or a
    # status query), unlike "karo"/"kar do" which would read oddly on a question.
    pre = ["AERIS ", "zara ", "abhi ", "please ", "hey AERIS "]
    suf = [" please", " zara", " abhi"]
    # Pass 1 — a single prefix OR a single suffix.
    i = 0
    while len(out) < target and pool:
        base = pool[i % len(pool)]
        for m in [pr + base for pr in pre] + [base + sf for sf in suf]:
            add(m)
            if len(out) >= target:
                break
        i += 1
        if i >= len(pool):
            break
    # Pass 2 — compound prefix+base+suffix, only if still short. Guarantees the
    # 20+ floor even for sparse utility skills (ping, *_status) with few patterns.
    i = 0
    while len(out) < target and pool:
        base = pool[i % len(pool)]
        for pr in pre:
            for sf in suf:
                add(pr + base + sf)
                if len(out) >= target:
                    break
            if len(out) >= target:
                break
        i += 1
        if i > len(pool) * 6:
            break
    return out


def _load_curated():
    """Hand-written, natural example phrases per command (data/command_examples.json).
    When present for a command, these lead the Examples list (ahead of the raw
    router patterns) so top commands read like real utterances, not padding."""
    import json
    path = os.path.join(_ROOT, "data", "command_examples.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: [str(x) for x in v] for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def main():
    from core.skill_registry import discover_skills, REGISTRY
    from core.intent_loader import load_all_intents
    discover_skills("skills")
    CURATED = _load_curated()
    # COMPLETE command set = base intents.json + skill patterns + learned + user
    # (load_all_intents merges them). The @skill REGISTRY alone MISSES the ~17
    # core intents (open_app, take_screenshot, get_weather, get_time, …).
    all_intents = load_all_intents()

    def describe(name):
        sk = REGISTRY.get(name)
        if sk and (sk.description or "").strip():
            return sk.description.strip()
        return CORE_DESC.get(name, "")

    def module_of(name):
        sk = REGISTRY.get(name)
        return getattr(sk.handler, "__module__", "") if sk else ""

    groups = {}
    for name, cfg in all_intents.items():
        patterns = list((cfg or {}).get("patterns", []))
        if not patterns:
            continue
        key, title = categorize(name, module_of(name))
        groups.setdefault((key, title), []).append((name, describe(name), patterns))

    order = [c[0] for c in CATS] + [FALLBACK[0]]

    def gkey(item):
        k = item[0][0]
        return order.index(k) if k in order else 999

    total = sum(len(v) for v in groups.values())
    lines = []
    W = lines.append
    W("# AERIS — Complete Command & Ability Reference\n")
    W("> **Standalone Hinglish AI assistant.** Speak or type in Hindi, English, or a "
      "mix — AERIS understands natural phrasing, not just the exact words below. "
      f"**{total} abilities** across {len(groups)} categories, all running "
      "**on-device** (no cloud, no API keys).\n")
    W("**How to read this:** every ability lists real example phrases. AERIS matches "
      "*meaning*, so slight variations (\"screenshot lo\" ≈ \"take a screenshot\" ≈ "
      "\"screen capture karo\") all work. Voice and typed input are equivalent.\n")
    W("_This file is generated by `gen_commands_readme.py` — re-run it after adding skills._\n")

    W("## Contents\n")
    for (key, title), items in sorted(groups.items(), key=gkey):
        anchor = re.sub(r"[^a-z0-9 ]", "", title.lower()).strip().replace(" ", "-")
        W(f"- [{title}](#{anchor}) — {len(items)} abilities")
    W("")

    for (key, title), items in sorted(groups.items(), key=gkey):
        W(f"\n## {title}\n")
        for name, desc, patterns in sorted(items, key=lambda x: x[0]):
            W(f"### `{name}`")
            W(f"{(desc or '').strip() or '(ability)'}\n")
            # Curated hand-written examples lead; real patterns fill in; mechanical
            # variations only pad if still short of 20.
            seed = CURATED.get(name, []) + patterns
            curated_mark = " ✍️" if name in CURATED else ""
            W(f"**Examples:**{curated_mark}\n")
            for e in variations(seed, target=20):
                W(f"- “{e}”")
            W("")

    out_path = os.path.join(_ROOT, "docs", "COMMANDS.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    txt = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"wrote {out_path}  ({total} abilities, {len(groups)} categories, {len(txt)} chars)")


if __name__ == "__main__":
    main()
