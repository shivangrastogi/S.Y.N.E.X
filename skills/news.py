"""News briefing — fetches RSS headlines and summarizes via the LLM."""

from __future__ import annotations

import json
import os
from pathlib import Path

from core.skill_registry import skill

try:
    import feedparser
    _AVAILABLE = True
except ImportError:
    feedparser = None
    _AVAILABLE = False


_ROOT = Path(__file__).resolve().parent.parent
_SOURCES_FILE = _ROOT / "data" / "news_sources.json"

_DEFAULT_SOURCES = {
    "tech":     ["https://hnrss.org/frontpage"],
    "india":    ["https://www.thehindu.com/news/national/feeder/default.rss"],
    "business": ["https://www.livemint.com/rss/news"],
    "world":    ["https://feeds.bbci.co.uk/news/world/rss.xml"],
}


def _load_sources() -> dict:
    if _SOURCES_FILE.exists():
        try:
            return json.loads(_SOURCES_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    _SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SOURCES_FILE.write_text(json.dumps(_DEFAULT_SOURCES, indent=2), encoding="utf-8")
    return _DEFAULT_SOURCES


def _pick_category(text: str) -> str:
    t = (text or "").lower()
    for cat in ("tech", "india", "business", "world"):
        if cat in t:
            return cat
    return "india"


def _fetch_headlines(category: str, max_per_source: int = 5) -> list[str]:
    sources = _load_sources()
    feeds = sources.get(category) or sources.get("india") or []
    headlines: list[str] = []
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_per_source]:
            title = (entry.get("title") or "").strip()
            if title:
                headlines.append(title)
    return headlines


@skill(
    name="news_briefing",
    description="Fetch latest headlines and summarize them in Hinglish (categories: tech, india, business, world)",
    patterns=[
        "aaj ki news batao",
        "news sunao",
        "latest headlines kya hain",
        "tech news batao",
        "india ki khabar",
        "business news",
        "world news",
        "what's the news today",
    ],
    required_entities=[],
)
def news_briefing(slots: dict) -> str:
    if not _AVAILABLE:
        return "feedparser install nahi hai. 'pip install feedparser' chalao."
    raw = " ".join(str(v) for v in slots.values()) if slots else ""
    category = _pick_category(raw or "india")

    headlines = _fetch_headlines(category)
    if not headlines:
        return f"{category} ki news abhi fetch nahi ho payi. Internet check karo."

    top = headlines[:8]
    bullet_list = "\n".join(f"- {h}" for h in top)
    return f"{category.title()} ki latest headlines:\n{bullet_list}"
