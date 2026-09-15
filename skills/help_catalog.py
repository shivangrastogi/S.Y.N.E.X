"""Help / "what can you do" skill — generates a categorized catalog reply
from the live skill registry, so the help text never goes stale when new
skills are added.

Triggers: "help", "what can you do", "kya kar sakte ho", "list commands",
"skill list", etc. Returns a multi-line summary with one example phrase
per skill so the user knows how to invoke each one.
"""
from __future__ import annotations

import logging
import os
import re

from core.skill_registry import skill, all_skills

log = logging.getLogger(__name__)


# Category buckets — each skill name maps to a label. Anything not in the
# table goes under "Other". Keeps the help text readable instead of
# dumping 40 skills in one giant alphabetical wall.
_CATEGORIES: dict[str, str] = {
    # Apps & windows
    "open_app": "Apps", "close_app": "Apps",
    "open_explorer_here": "Apps", "open_workbook": "Apps",
    "open_in_browser": "Apps", "open_website": "Apps", "open_file": "Apps",
    "window_minimize": "Windows", "window_maximize": "Windows",
    "window_restore": "Windows", "window_close": "Windows",
    "snap_left": "Windows", "snap_right": "Windows",
    "next_desktop": "Windows", "prev_desktop": "Windows",
    "new_desktop": "Windows",
    # Voice / chat
    "greeting": "Conversational", "clear_chat": "Conversational",
    # Quick info
    "current_time": "Quick info", "current_date": "Quick info",
    "battery_status": "Quick info", "weather_local": "Quick info",
    "currency_convert": "Quick info", "date_diff": "Quick info",
    # System
    "system_stats": "System", "cpu_info": "System",
    "network_status": "System", "network_check": "System",
    "ping": "System",
    "lock_screen": "System", "sleep_pc": "System", "shutdown_pc": "System",
    "restart_pc": "System", "cancel_shutdown": "System",
    "diagnostics": "System",
    "memory_stats": "System",
    # Productivity
    "create_note": "Productivity", "snippet_save": "Productivity",
    "snippet_paste": "Productivity", "snippet_list": "Productivity",
    "expense_add": "Productivity", "expense_summary": "Productivity",
    "open_workbook": "Productivity",
    "timer_set": "Productivity", "timer_cancel": "Productivity",
    "reminder_set": "Productivity", "reminder_list": "Productivity",
    "focus_mode_on": "Productivity", "focus_mode_off": "Productivity",
    # Vision / gesture
    "gesture_mode_on": "Vision", "gesture_mode_off": "Vision",
    "gesture_status": "Vision", "cursor_mode_on": "Vision", "cursor_mode_off": "Vision",
    "snip_ocr": "Vision", "object_in_view": "Vision",
    "snap_and_save": "Vision",
    # Web / browse
    "web_search": "Web", "news_brief": "Web", "translate_text": "Web",
    # Audio / volume
    "volume_set": "Audio", "volume_mute": "Audio", "volume_unmute": "Audio",
    "brightness_set": "Audio",
    # Code / dev
    "code_write": "Dev",
    # Clipboard
    "clipboard_paste": "Clipboard", "clipboard_history_show": "Clipboard",
    "clipboard_history_clear": "Clipboard",
    # Memory & vault
    "vault_unlock": "Memory", "vault_lock": "Memory",
    "vault_set": "Memory", "vault_get": "Memory",
    "teach_skill": "Memory",
}

_CATEGORY_ORDER = [
    "Quick info", "Apps", "Windows", "System",
    "Productivity", "Vision", "Audio", "Web",
    "Clipboard", "Memory", "Dev", "Conversational", "Other",
]


def _short_desc(text: str, n: int = 60) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


@skill(
    name="help_catalog",
    description="What can AERIS do — a concise category overview by default, full list on request.",
    patterns=[
        "help", "what can you do", "kya kar sakte ho", "list commands",
        "skill list", "show commands", "show skills", "commands",
        "what are your skills", "kaunsi commands chalti hain",
        "what can i ask", "menu", "list of commands", "available commands",
        "kya kya kar sakte ho", "help me", "show me what you can do",
        "tumhare commands", "all skills",
        # "what all is there" phrasings (Hinglish) — the natural way users ask.
        "kya kya hai", "kya kya seekha", "mere jarvis mein kya hai",
        "jarvis mein kya kya hai", "sab kuch batao", "features batao",
        "abilities batao", "kya kya aata hai", "tumhare paas kya kya hai",
        "kya kya features hain",
    ],
    required_entities=[],
)
def help_catalog(slots: dict) -> str:
    raw = (slots.get("raw_text") or slots.get("text") or "").lower()
    want_full = any(w in raw for w in (
        "full", "poori", "puri", "detail", "sabhi", "everything",
        "list all", "har command", "complete list", "saare",
    ))

    by_cat = _group_by_category(all_skills())
    total = sum(len(v) for v in by_cat.values())

    # Drill-down: "system commands kya hain" / "math skills" → just that category.
    cat = None if want_full else _detect_category(raw, by_cat.keys())
    if cat:
        entries = by_cat[cat]
        lines = [f"{cat} — {len(entries)} commands:", ""]
        for _name, desc, example in entries:
            if not example:
                continue
            tail = f"  — {_short_desc(desc, 60)}" if desc else ""
            lines.append(f"  • “{example}”{tail}")
        lines.append("")
        lines.append("Koi bhi phrase bol ke try karo · 'help' se saari categories.")
        return "\n".join(lines)

    if want_full:
        lines = [f"AERIS — {total} skills across {len(by_cat)} categories.",
                 "Say any example phrase below (Hinglish bhi chalega):"]
        for title, entries in _ordered(by_cat):
            lines.append("")
            lines.append(f"── {title} ({len(entries)}) ──")
            for name, desc, example in entries:
                lines.append(f"  • {name:24s} e.g. {example!r}")
                if desc:
                    lines.append(f"      {_short_desc(desc, 90)}")
        lines.append("")
        lines.append("Tip: 'diagnose' se health check chalta hai.")
        return "\n".join(lines)

    # Concise overview (default) — counts + a few examples per category.
    lines = [f"Main {total} tarah ke kaam kar sakta hoon, {len(by_cat)} categories mein:", ""]
    for title, entries in _ordered(by_cat):
        examples = [ex for _, _, ex in entries if ex][:3]
        lines.append(f"▸ {title} ({len(entries)})")
        if examples:
            lines.append("    " + "  ·  ".join(f"“{e}”" for e in examples))
    lines.append("")
    lines.append("Poori list ke liye 'full list' bolo · ya seedhe koi command try karo · 'diagnose' = health check.")
    return "\n".join(lines)


def _group_by_category(skills) -> dict:
    """Bucket every skill into a category. Prefers the shared keyword categorizer
    from gen_commands_readme (same buckets as docs/COMMANDS.md); falls back to the
    local hand-map if that module isn't importable."""
    try:
        from gen_commands_readme import categorize as _cat

        def title_of(name, sk):
            mod = getattr(sk.handler, "__module__", "") or ""
            return _cat(name, mod)[1]
    except Exception:
        def title_of(name, sk):
            return _CATEGORIES.get(name, "Other")

    by_cat: dict[str, list[tuple[str, str, str]]] = {}
    for name, sk in sorted(skills.items()):
        title = title_of(name, sk)
        example = sk.patterns[0] if sk.patterns else None
        by_cat.setdefault(title, []).append((name, sk.description, example))
    return by_cat


def _ordered(by_cat: dict):
    """Biggest categories first; 'Other'/'More' bucket always last."""
    def key(kv):
        title, entries = kv
        misc = title.lower() in ("other", "more abilities", "more")
        return (misc, -len(entries), title)
    return sorted(by_cat.items(), key=key)


# User words that differ from the category title wording, mapped to a word that
# DOES appear in a title (so "calculator commands" → "Math, Finance & Calculators").
_CAT_SYNONYMS = {
    "calc": "calculators", "calculator": "calculators", "maths": "math",
    "audio": "music", "song": "music", "gaana": "music", "gaane": "music",
    "reminder": "productivity", "timer": "productivity", "task": "productivity",
    "routine": "productivity", "note": "productivity",
    "screenshot": "screen", "camera": "vision", "gesture": "gestures",
    "web": "browser", "internet": "browser",
    "code": "developer", "coding": "developer", "dev": "developer",
    "grammar": "text", "translate": "text",
    "phone": "continuity", "bridge": "continuity",
    "recall": "memory", "knowledge": "memory",
    "theme": "themes", "notification": "notifications", "briefing": "briefings",
    "permission": "permissions", "plugin": "plugins",
    "power": "system", "cpu": "system", "ram": "system", "disk": "system",
    "window": "apps", "app": "apps",
    "document": "documents", "pdf": "documents",
    "fun": "casual", "joke": "casual",
}


def _detect_category(raw: str, titles):
    """If the query clearly names a category ('system commands', 'math skills'),
    return that category title; else None. Matches title words (>=4 chars) plus a
    synonym boost for user words that differ from the title wording."""
    raw = (raw or "").lower()
    hay = raw
    for k, v in _CAT_SYNONYMS.items():
        if k in raw:
            hay += " " + v
    best, best_score = None, 0
    for title in titles:
        words = [w for w in re.findall(r"[a-z]{4,}", title.lower())
                 if w not in ("more", "abilities", "management", "superpowers")]
        score = sum(1 for w in words if w in hay)
        if score > best_score:
            best, best_score = title, score
    return best if best_score >= 1 else None
