"""Lightweight extractive summarizer with optional LLM upgrade.

Two modes:
    short  - 2-3 sentences, suitable for spoken response
    deep   - 5-7 sentences, structured paragraph for "tell me more about"

Strategy (offline-first; no Ollama required):
  1. Sentence-split the input text.
  2. Score each sentence by:
        a) Lead-position prior  - first 2 sentences get a strong boost.
        b) TF-IDF-ish keyword overlap with the query (and intra-doc IDF).
        c) Length penalty for very short or very long sentences.
  3. Pick top-K sentences, restore original order, join.

If `LLMChat` is reachable, we hand the cleaned text + query to it for a
quality boost. Either path returns Hinglish-safe plain text.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Optional

log = logging.getLogger(__name__)


# Words that should never count toward keyword overlap. Mix English +
# common Hinglish stop-tokens so neither language dominates scoring.
_STOPWORDS = {
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "for", "to", "from", "by", "with", "as",
    "and", "or", "but", "if", "then", "else", "so", "than", "that",
    "this", "these", "those", "it", "its", "their", "they", "them",
    "he", "she", "his", "her", "we", "our", "you", "your", "i", "me",
    "my", "mine", "do", "does", "did", "have", "has", "had", "having",
    "not", "no", "yes", "can", "could", "would", "should", "will",
    "may", "might", "shall", "about", "into", "over", "under", "more",
    "most", "some", "any", "all", "each", "every", "such", "also",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    # Hinglish stop tokens
    "hai", "hain", "tha", "thi", "the", "ho", "hoon", "ka", "ki", "ke",
    "se", "mein", "me", "par", "pe", "to", "kya", "kaun", "kaisa",
    "kaisi", "kaise", "yeh", "ye", "vo", "wo", "main", "mujhe", "tumhe",
    "aap", "aapko", "haan", "nahi", "lekin", "magar", "phir", "fir",
    "abhi", "wahan", "yahan", "bhi", "bhai", "yaar", "sir", "jarvis",
    "aeris", "search", "online", "google", "internet", "batao", "bata",
    "tell", "explain", "define", "give", "show", "want", "need",
}


_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Zऀ-ॿ])")
_WORD_RE = re.compile(r"[A-Za-zऀ-ॿ]+")


def _split_sentences(text: str) -> list[str]:
    """Aggressive sentence splitter that handles abbreviations gracefully."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = _SENT_SPLIT_RE.split(text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Further split on newlines that survived (shouldn't, but defensive).
        for sub in re.split(r"\n+", p):
            sub = sub.strip(" .;:")
            if len(sub) >= 8:
                out.append(sub if sub.endswith((".", "!", "?")) else sub + ".")
    return out


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if len(w) > 1]


def _keywords(text: str) -> set[str]:
    return {t for t in _tokenize(text) if t not in _STOPWORDS}


def _score_sentences(sentences: list[str], query: str) -> list[float]:
    """Score each sentence by keyword overlap + lead bias + length penalty."""
    if not sentences:
        return []

    # Build a doc-frequency table across sentences for IDF weighting.
    df: Counter[str] = Counter()
    sent_tokens: list[set[str]] = []
    for s in sentences:
        toks = set(_tokenize(s)) - _STOPWORDS
        sent_tokens.append(toks)
        for t in toks:
            df[t] += 1
    n = len(sentences)
    idf = {t: math.log((n + 1) / (c + 0.5)) + 1.0 for t, c in df.items()}

    qkeys = _keywords(query)
    scores: list[float] = []
    for i, (sent, toks) in enumerate(zip(sentences, sent_tokens)):
        kw_score = sum(idf.get(t, 1.0) for t in toks if t in qkeys)
        intra_score = sum(idf.get(t, 1.0) for t in toks) / max(len(toks), 1)
        lead_bonus = 1.5 if i == 0 else (0.8 if i == 1 else (0.4 if i == 2 else 0.0))

        wc = len(sent.split())
        if wc < 5:
            length_pen = -1.0
        elif wc > 45:
            length_pen = -0.5
        else:
            length_pen = 0.0

        scores.append(2.0 * kw_score + 0.6 * intra_score + lead_bonus + length_pen)
    return scores


def _pick_top(sentences: list[str], scores: list[float], k: int) -> list[str]:
    if not sentences:
        return []
    k = min(max(k, 1), len(sentences))
    indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    chosen_idx = sorted(i for i, _ in indexed[:k])
    return [sentences[i] for i in chosen_idx]


def _clean_chunk(text: str) -> str:
    """Strip junk that scrapers commonly drag along: nav crumbs, cookie text,
    'Read more', tracking suffixes, repeated whitespace."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    junk_patterns = [
        r"(?i)\baccept all cookies\b.*?\.",
        r"(?i)\bsubscribe to our newsletter\b.*?\.",
        r"(?i)\bsign up for\b.*?\.",
        r"(?i)\bcontinue reading\b.*?\.",
        r"(?i)\bread more\b\s*[\.\:\-]?",
        r"(?i)\bthis article needs additional citations.*?\.",
        r"(?i)\bplease help improve.*?\.",
        r"\[\s*\d+\s*\]",  # Wikipedia footnote refs (incl. "[ 1 ]")
        r"\[\s*citation needed\s*\]",
        r"\[\s*edit\s*\]",
    ]
    for p in junk_patterns:
        text = re.sub(p, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extractive_summary(
    text: str,
    query: str = "",
    mode: str = "short",
    *,
    max_chars: Optional[int] = None,
) -> str:
    """Pure-Python summarizer. Always returns SOMETHING usable."""
    cleaned = _clean_chunk(text)
    if not cleaned:
        return ""

    sentences = _split_sentences(cleaned)
    if not sentences:
        # Fall back to a hard char clip.
        clip = cleaned[: max_chars or 300]
        return clip.rstrip() + ("..." if len(cleaned) > len(clip) else "")

    k = 3 if mode == "short" else 7
    scores = _score_sentences(sentences, query)
    top = _pick_top(sentences, scores, k)
    summary = " ".join(top)

    if max_chars and len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


# ---------------------------------------------------------------------------
# Optional LLM upgrade
# ---------------------------------------------------------------------------

_LLM_PROMPT = """You are summarizing web content for a Hinglish voice assistant.

User asked: "{query}"
Mode: {mode}  ({mode_hint})

Below is raw scraped text from {n_sources} source(s). Produce a clean, factually
grounded summary in Hinglish (Hindi+English in Roman script — match the user's
mix). {length_hint}

Rules:
- Stay on topic. Ignore navigation crumbs, cookie banners, ads.
- Don't invent facts not in the source text.
- No headers, no bullet points unless absolutely necessary.
- Plain spoken-style sentences; this will be read aloud.

SOURCE TEXT:
{source}
"""

_MODE_HINTS = {
    "short": ("user wants a quick answer",
              "Reply with 2-3 short sentences, max 60 words. Direct and punchy."),
    "deep":  ("user wants depth and detail",
              "Reply with 5-7 sentences (~150-200 words). Cover what it is, "
              "key facts, and one interesting nuance. Still spoken-style."),
}


def llm_summary(
    text: str,
    query: str,
    mode: str,
    n_sources: int,
    llm_chat,
) -> Optional[str]:
    """Try to produce an LLM-quality summary. Returns None on any failure
    so the caller can fall back to extractive_summary()."""
    if not llm_chat:
        return None
    try:
        if not llm_chat.is_available():
            return None
    except Exception:
        return None

    mode_hint, length_hint = _MODE_HINTS.get(mode, _MODE_HINTS["short"])
    cleaned = _clean_chunk(text)
    if not cleaned:
        return None

    # Cap source size so we don't blow the model's context.
    cap = 4000 if mode == "deep" else 2500
    if len(cleaned) > cap:
        cleaned = cleaned[:cap] + " ..."

    prompt = _LLM_PROMPT.format(
        query=query or "(no specific query)",
        mode=mode,
        mode_hint=mode_hint,
        length_hint=length_hint,
        n_sources=n_sources,
        source=cleaned,
    )

    try:
        reply = llm_chat.reply(
            user_text=prompt,
            sentiment_label="neutral",
            memory_facts={},
            history=[],
        )
    except Exception as e:
        log.info("[summarizer] LLM call failed: %s", e)
        return None
    if not reply:
        return None
    return _clean_chunk(reply)


def summarize(
    text: str,
    query: str = "",
    mode: str = "short",
    *,
    n_sources: int = 1,
    llm_chat=None,
    max_chars: Optional[int] = None,
) -> str:
    """One-shot: try LLM, then extractive. Always returns a string."""
    out = llm_summary(text, query, mode, n_sources, llm_chat) if llm_chat else None
    if not out:
        out = extractive_summary(text, query, mode, max_chars=max_chars)
    if max_chars and len(out) > max_chars:
        out = out[: max_chars - 3].rstrip() + "..."
    return out


if __name__ == "__main__":
    sample = (
        "Artificial intelligence (AI) is intelligence demonstrated by machines, "
        "as opposed to the natural intelligence displayed by humans or animals. "
        "Leading AI textbooks define the field as the study of intelligent agents. "
        "AI applications include advanced web search engines, recommendation "
        "systems, understanding human speech, self-driving cars, and competing "
        "at the highest level in strategic game systems. As machines become "
        "increasingly capable, tasks once considered to require intelligence "
        "are removed from the AI definition, a phenomenon known as the AI effect."
    )
    print("SHORT:")
    print(summarize(sample, "what is ai", "short"))
    print("\nDEEP:")
    print(summarize(sample, "tell me more about ai", "deep"))
