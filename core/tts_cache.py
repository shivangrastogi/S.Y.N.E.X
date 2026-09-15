"""Content-addressed cache for synthesised TTS audio.

AERIS re-synthesises the same short acknowledgements ("Done.", "Yes sir.",
"Theek hai.") hundreds of times a session — each one a network round-trip to
edge-tts. This module caches the rendered ``.mp3`` keyed by the *content that
determines the audio*: ``(text, voice, rate, pitch)``. Identical phrases under
identical voice settings replay straight from disk.

Design choices:

  * **Only short phrases.** Long, unique replies (LLM chit-chat, summaries)
    would never hit the cache and would balloon the directory — gated by
    ``is_cacheable`` (≤ ``MAX_LEN`` chars). The long tail keeps going to the
    network and the reusable ``speech.mp3`` temp file.
  * **MD5 of the full key.** Collisions are not a correctness risk (worst
    case: wrong cached audio), and MD5 over the normalised key is fast and
    stable across runs.
  * **LRU by mtime.** ``prune`` keeps the newest ``MAX_FILES`` and drops the
    rest, so the cache self-limits without a separate index file.

Pure functions + a tiny bit of filesystem — no pygame, no edge_tts, no Qt —
so the whole thing is unit-testable against a tmp dir with zero audio.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)

MAX_LEN = 80          # phrases longer than this are not cached
MAX_FILES = 250       # LRU cap on cached clips

# A cache file is exactly ``<32 hex>.mp3`` — this guards prune() from ever
# touching the live ``speech.mp3`` temp file or anything else in the dir.
_CACHE_RE = re.compile(r"^[0-9a-f]{32}\.mp3$")


def _norm(text: str) -> str:
    """Normalise a phrase so trivial spacing/case differences share a clip."""
    return re.sub(r"\s+", " ", text.strip()).casefold()


def cache_key(text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> str:
    """Stable MD5 over the audio-determining inputs."""
    raw = f"{_norm(text)}|{voice}|{rate}|{pitch}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def is_cacheable(text: str, max_len: int = MAX_LEN) -> bool:
    """True for short, non-empty phrases worth caching."""
    if not text:
        return False
    t = text.strip()
    return 0 < len(t) <= max_len


def cache_path(audio_dir: str, text: str, voice: str,
               rate: str = "+0%", pitch: str = "+0Hz") -> str:
    return os.path.join(audio_dir, cache_key(text, voice, rate, pitch) + ".mp3")


def lookup(audio_dir: str, text: str, voice: str,
           rate: str = "+0%", pitch: str = "+0Hz") -> Optional[str]:
    """Return the cached clip path if it exists and is non-empty, else None.

    Also bumps the file's mtime so ``prune``'s LRU sees it as recently used.
    """
    if not is_cacheable(text):
        return None
    path = cache_path(audio_dir, text, voice, rate, pitch)
    try:
        if os.path.getsize(path) > 0:
            os.utime(path, None)   # mark as recently used
            return path
    except OSError:
        return None
    return None


def store(audio_dir: str, src_file: str, text: str, voice: str,
          rate: str = "+0%", pitch: str = "+0Hz") -> str:
    """Copy a freshly-synthesised ``src_file`` into the cache; return its path.

    Writes to a temp name then ``os.replace`` so a crash mid-copy never leaves
    a half-written clip that ``lookup`` would happily play. Falls back to
    returning ``src_file`` if anything goes wrong — caching is best-effort.
    """
    dst = cache_path(audio_dir, text, voice, rate, pitch)
    tmp = dst + ".part"
    try:
        with open(src_file, "rb") as fsrc, open(tmp, "wb") as fdst:
            fdst.write(fsrc.read())
        os.replace(tmp, dst)
        return dst
    except OSError as e:
        log.debug("[tts_cache] store failed: %s", e)
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return src_file


def prune(audio_dir: str, max_files: int = MAX_FILES) -> int:
    """Drop oldest cache clips beyond ``max_files``. Returns count removed."""
    try:
        entries = [
            os.path.join(audio_dir, n)
            for n in os.listdir(audio_dir)
            if _CACHE_RE.match(n)
        ]
    except OSError:
        return 0
    if len(entries) <= max_files:
        return 0
    entries.sort(key=lambda p: os.path.getmtime(p))  # oldest first
    removed = 0
    for p in entries[: len(entries) - max_files]:
        try:
            os.remove(p)
            removed += 1
        except OSError:
            pass
    return removed
