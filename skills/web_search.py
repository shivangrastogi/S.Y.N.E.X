"""Web search + summarize + cache.

Trigger phrases (registered into the brain's intent index):
    "search online <X>", "<X> search karo online", "internet pe <X> dhundo",
    "google karo <X>", "tell me about <X>", "what is <X>", etc.

Pipeline per query:
    1. Detect mode: short (default) or deep ("define more about", "in detail",
       "vistar se", "deeply", etc.).
    2. Cache lookup — if hit, return immediately with a "yaad hai" prefix.
    3. DuckDuckGo HTML search (no API key). Falls back to a Bing scrape if
       the ddgs package isn't installed.
    4. Branch on result shape:
         a. Has Wikipedia / Britannica / instant-answer paragraph -> use it.
         b. Only links (search result list) -> fetch top 2-3 pages, concat.
         c. Image-heavy -> describe the metadata + top text snippet.
    5. Summarize via core.summarizer (LLM if Ollama up, else extractive).
    6. Save into knowledge cache.
    7. Return a spoken-style answer + source list.

Failure modes are all soft: any branch can fall back to "couldn't search,
here's the link" without raising.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from typing import Optional
from urllib.parse import quote_plus, urlparse

# Ensure project root on path when this module is loaded eagerly by tests.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.knowledge_cache import get_default_cache  # noqa: E402
from core.skill_registry import skill  # noqa: E402
from core.summarizer import summarize  # noqa: E402

log = logging.getLogger(__name__)


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_DEEP_TRIGGERS = (
    "in detail", "in depth", "deeply", "more about", "define more",
    "vistar se", "detail mein", "detail me", "extensively", "thoroughly",
    "tell me everything", "explain fully", "full info", "complete info",
)

_TRIGGER_PREFIXES = (
    "search online for", "search online", "online search",
    "google karo", "google", "search karo", "search",
    "internet pe dhundo", "internet pe", "internet par",
    "online dhundo", "look up", "find online",
    "what is", "what's", "what are",
    "tell me about", "tell me more about",
    "kya hai", "kya hota hai", "kya hote hai",
    "mujhe batao", "batao",
    "define", "explain",
)


def _detect_mode(text: str) -> str:
    t = (text or "").lower()
    return "deep" if any(trig in t for trig in _DEEP_TRIGGERS) else "short"


def _strip_triggers(text: str) -> str:
    """Remove leading trigger phrases so we get the actual topic.

    Iterates until no more prefix matches — needed because users stack
    triggers ("search online what is ai" must strip both "search online"
    AND "what is" to land on "ai").
    """
    t = (text or "").strip()
    sorted_prefixes = sorted(_TRIGGER_PREFIXES, key=len, reverse=True)
    for _ in range(6):  # bounded — prevents pathological input loops
        low = t.lower()
        if not low:
            return ""
        matched = False
        for p in sorted_prefixes:
            if low.startswith(p + " "):
                t = t[len(p) + 1:].strip()
                matched = True
                break
            if low == p:
                return ""
        if not matched:
            break
    # Trim trailing depth modifiers — they're handled separately by mode.
    low = t.lower()
    for m in sorted(_DEEP_TRIGGERS, key=len, reverse=True):
        if low.endswith(" " + m):
            t = t[: -(len(m) + 1)].strip()
            break
    return re.sub(r"^(?:the|a|an|about|on|for)\s+", "", t, flags=re.I).strip()


# ---------------------------------------------------------------------------
# Search backends
# ---------------------------------------------------------------------------

def _ddg_search(query: str, max_results: int = 5) -> list[dict]:
    """Try the new `ddgs` package, then the legacy `duckduckgo_search`.
    Returns [] on any failure so callers can fall back to HTML scrape."""
    DDGS = None
    for mod in ("ddgs", "duckduckgo_search"):
        try:
            DDGS = __import__(mod, fromlist=["DDGS"]).DDGS
            break
        except Exception:
            continue
    if DDGS is None:
        return []
    out: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, region="in-en"):
                title = r.get("title") or ""
                href = r.get("href") or r.get("url") or ""
                body = r.get("body") or ""
                if href:
                    out.append({"title": title, "url": href, "snippet": body})
    except Exception as e:
        log.info("[web_search] DDGS failed: %s", e)
    return out


def _ddg_html_fallback(query: str, max_results: int = 5) -> list[dict]:
    """HTML-scrape duckduckgo.com/html/ — no API key, no ddgs package needed."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return []
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=8)
        r.raise_for_status()
    except Exception as e:
        log.info("[web_search] DDG HTML fetch failed: %s", e)
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[dict] = []
    for res in soup.select(".result__body")[:max_results]:
        a = res.select_one("a.result__a")
        sn = res.select_one(".result__snippet")
        if not a:
            continue
        out.append({
            "title": a.get_text(strip=True),
            "url": a.get("href", ""),
            "snippet": sn.get_text(" ", strip=True) if sn else "",
        })
    return out


def _wikipedia_summary(query: str) -> Optional[dict]:
    """REST API summary. Free, no key, JSON. Best source when available."""
    try:
        import requests
    except Exception:
        return None
    slug = quote_plus(query.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=6)
        if r.status_code != 200:
            return None
        body = r.json()
        if body.get("type") == "disambiguation":
            return None
        extract = body.get("extract") or ""
        if len(extract) < 60:
            return None
        return {
            "title": body.get("title") or query,
            "url": (body.get("content_urls") or {})
                   .get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{slug}"),
            "extract": extract,
            "thumbnail": (body.get("thumbnail") or {}).get("source"),
        }
    except Exception as e:
        log.info("[web_search] Wikipedia lookup failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Page fetch + extract
# ---------------------------------------------------------------------------

_BLOCK_TAGS = ("script", "style", "nav", "header", "footer", "aside",
               "form", "noscript", "iframe", "button")


def _fetch_page_text(url: str, max_chars: int = 6000) -> str:
    """Pull cleaned readable text from a URL. Returns '' on failure."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return ""
    try:
        r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=8)
        r.raise_for_status()
    except Exception as e:
        log.info("[web_search] fetch %s failed: %s", url, e)
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(list(_BLOCK_TAGS)):
        tag.decompose()

    # Prefer <article> or <main>; fall back to clustering paragraphs by parent.
    container = soup.find("article") or soup.find("main")
    paragraphs: list[str] = []
    if container:
        paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    if not paragraphs:
        # Largest <div> by paragraph density.
        best, best_score = None, 0
        for div in soup.find_all("div"):
            ps = div.find_all("p", recursive=False)
            score = sum(len(p.get_text()) for p in ps)
            if score > best_score:
                best, best_score = div, score
        if best is not None:
            paragraphs = [p.get_text(" ", strip=True) for p in best.find_all("p")]
    if not paragraphs:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]

    # Drop obvious junk paragraphs (very short, all-caps headers, etc.).
    cleaned = []
    for p in paragraphs:
        if not p or len(p) < 40:
            continue
        if p.isupper():
            continue
        cleaned.append(p)
    text = "\n\n".join(cleaned).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


# ---------------------------------------------------------------------------
# Result-shape branching
# ---------------------------------------------------------------------------

def _has_image_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(k in q for k in (
        "image", "photo", "picture", "tasveer", "photo dikhao",
        "show me a", "show me the", "kaisi dikhti", "kaisa dikhta",
    ))


def _gather_corpus(topic: str, mode: str) -> tuple[str, list[dict], str]:
    """Return (corpus_text, sources, branch_used).

    branch_used in {"wiki", "snippet+pages", "snippet_only", "links_only"}.
    """
    sources: list[dict] = []

    # 1) Wikipedia first — best signal-to-noise for definitional queries.
    wiki = _wikipedia_summary(topic)
    if wiki and (mode == "short" or len(wiki["extract"]) > 400):
        sources.append({"title": wiki["title"], "url": wiki["url"]})
        if mode == "deep":
            # Pull the full lead section for a richer summary.
            extra = _fetch_page_text(wiki["url"], max_chars=8000)
            corpus = wiki["extract"] + "\n\n" + extra if extra else wiki["extract"]
        else:
            corpus = wiki["extract"]
        return corpus, sources, "wiki"

    # 2) DDG search.
    results = _ddg_search(topic) or _ddg_html_fallback(topic)
    if not results:
        return "", [], "links_only"

    # Have snippets — that's our paragraph candidate.
    snippet_blob = "\n\n".join(
        r["snippet"] for r in results if r.get("snippet")
    ).strip()

    if mode == "deep":
        # Fetch top 2-3 pages and concatenate.
        page_texts: list[str] = []
        for r in results[:3]:
            url = r.get("url") or ""
            if not url:
                continue
            txt = _fetch_page_text(url, max_chars=4000)
            if txt:
                page_texts.append(txt)
                sources.append({"title": r.get("title") or url, "url": url})
            if sum(len(t) for t in page_texts) > 9000:
                break
        if page_texts:
            corpus = (snippet_blob + "\n\n" + "\n\n".join(page_texts)).strip()
            return corpus, sources, "snippet+pages"

    # short mode OR deep mode where pages didn't fetch -> snippet only.
    for r in results[:3]:
        if r.get("url"):
            sources.append({"title": r.get("title") or r["url"], "url": r["url"]})
    if snippet_blob:
        return snippet_blob, sources, "snippet_only"
    return "", sources, "links_only"


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_response(summary: str, sources: list[dict], from_cache: bool,
                     query: str, branch: str) -> str:
    bits: list[str] = []
    if from_cache:
        bits.append("Yaad hai sir, pehle search kiya tha:")
    else:
        bits.append(f"'{query}' ke baare mein:")

    bits.append(summary.strip())

    if sources:
        # Show 1-2 sources — voice listeners can ignore, GUI users can click.
        domains = []
        for s in sources[:2]:
            try:
                d = urlparse(s["url"]).netloc.replace("www.", "")
                if d:
                    domains.append(d)
            except Exception:
                pass
        if domains:
            bits.append(f"(Source: {', '.join(domains)})")

    if branch == "links_only" and not summary:
        bits.append("Direct paragraph nahi mila — links manually check karne padenge.")

    return "\n".join(b for b in bits if b)


# ---------------------------------------------------------------------------
# Skill entry
# ---------------------------------------------------------------------------

def _get_llm_chat():
    """Lazy-import LLMChat — never blows up if Ollama isn't even installed."""
    try:
        from core.llm_chat import LLMChat
        return LLMChat()
    except Exception:
        return None


@skill(
    name="web_search",
    description=("Search the web online, summarize the top results in Hinglish, "
                 "and cache the answer locally for instant recall later."),
    patterns=[
        "search online", "search online ai", "search online for ai",
        "search karo online", "google karo", "google search karo",
        "internet pe dhundo", "internet par dhundo", "online dhundo",
        "search the web", "look this up online", "find online",
        "search online what is ai", "search online about machine learning",
        "what is ai", "what is machine learning", "what is python",
        "tell me about ai", "tell me more about quantum computing",
        "define ai", "define machine learning",
        "ai kya hai", "machine learning kya hai", "python kya hai",
        "ai ke baare mein batao", "mujhe ai ke baare mein batao",
        "vistar se batao", "detail mein batao",
        "search online and tell me", "online search karo aur batao",
    ],
    required_entities=["query"],
    prompts={"query": "Kya search karna hai online?"},
)
def web_search(slots: dict) -> str:
    raw_query = (slots.get("query") or "").strip()
    if not raw_query:
        return "Kya search karoon online? Topic batao."

    mode = _detect_mode(raw_query)
    topic = _strip_triggers(raw_query) or raw_query

    cache = get_default_cache()

    # ── Step 1: cache hit ──
    cached = cache.lookup(topic, mode=mode)
    if cached:
        return _format_response(
            cached.response, cached.sources, from_cache=True,
            query=topic, branch="cache",
        )

    # If user wanted depth but we have a short cached answer, upgrade attempt:
    if mode == "deep":
        short_cached = cache.lookup(topic, mode="short")
        # We still proceed to fetch deep — but if network fails, use this.
        fallback_short = short_cached.response if short_cached else None
    else:
        fallback_short = None

    # ── Step 2: gather corpus ──
    try:
        corpus, sources, branch = _gather_corpus(topic, mode)
    except Exception as e:
        log.warning("[web_search] gather failed: %s", e)
        return (fallback_short or
                f"'{topic}' search nahi ho paya — internet check karo, sir.")

    if not corpus:
        if _has_image_intent(raw_query) and sources:
            urls = " | ".join(s["url"] for s in sources[:2])
            return (f"'{topic}' ke liye sirf images / links mile, paragraph nahi:\n"
                    f"{urls}")
        if sources:
            urls = " | ".join(s["url"] for s in sources[:3])
            return (f"'{topic}' ke direct paragraph nahi mila. "
                    f"Top links:\n{urls}")
        return (fallback_short or
                f"'{topic}' ke baare mein kuch nahi mila online. "
                f"Spelling check karke phir bolo, sir.")

    # ── Step 3: summarize ──
    llm = _get_llm_chat()
    summary = summarize(
        corpus, query=topic, mode=mode,
        n_sources=len(sources) or 1, llm_chat=llm,
        max_chars=900 if mode == "short" else 1800,
    )

    if not summary:
        summary = (fallback_short or
                   f"Mila to sahi, par summarize nahi kar paya. Sources niche dekho.")

    # ── Step 4: cache ──
    try:
        cache.save(topic, mode, summary, sources=sources)
    except Exception as e:
        log.info("[web_search] cache save failed: %s", e)

    return _format_response(summary, sources, from_cache=False,
                            query=topic, branch=branch)


@skill(
    name="search_cache_stats",
    description="Show how many web searches are cached locally and the most recent ones.",
    patterns=[
        "search cache stats", "kitne searches cache mein hain",
        "cached searches dikhao", "knowledge cache stats",
        "kya kya search kiya hai pehle", "show cached searches",
    ],
    required_entities=[],
)
def search_cache_stats(slots: dict) -> str:
    cache = get_default_cache()
    s = cache.stats()
    lines = [f"Cache mein {s['entries']} searches hain, total {s['total_hits']} hits."]
    if s["recent"]:
        lines.append("Recent:")
        for r in s["recent"]:
            lines.append(f"  - [{r['mode']}] {r['query']}  (hits: {r['hit_count']})")
    return "\n".join(lines)


@skill(
    name="clear_search_cache",
    description="Clear the local web-search knowledge cache.",
    patterns=[
        "clear search cache", "knowledge cache clear karo",
        "search cache wipe karo", "cache reset karo",
    ],
    required_entities=[],
)
def clear_search_cache(slots: dict) -> str:
    get_default_cache().clear()
    return "Knowledge cache clear kar diya, sir."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for q in [
        "search online what is ai",
        "tell me more about quantum computing in detail",
        "search online ai",  # second time -> cache hit
    ]:
        print(f"\n>>> {q}")
        print(web_search({"query": q}))
