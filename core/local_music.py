"""Local music library — AERIS ka apna jukebox, zero cloud.

Walks the user's music folders once, remembers every audio file, and
fuzzy-matches spoken names ("wo kesariya wala bajao") against filenames.
Playback = ``os.startfile`` → Windows ka default player. Koi Spotify,
koi web, koi API nahi — sirf disk par padi files.

Index persists at ``data/local_music_index.json`` and rebuilds
automatically when stale (>24h) or on demand.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INDEX_PATH = os.path.join(_ROOT, "data", "local_music_index.json")

_AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aac",
              ".wma"}
_MAX_FILES = 5000
_STALE_S = 24 * 3600.0

_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "AppData",
              "Windows", "Program Files", "Program Files (x86)"}


def default_folders() -> list[str]:
    """Music + Downloads by default; extras via settings ``music_dirs``."""
    home = os.path.expanduser("~")
    dirs = [os.path.join(home, "Music"), os.path.join(home, "Downloads")]
    try:
        from core import settings
        extra = settings.get("music_dirs", []) or []
        if isinstance(extra, list):
            dirs += [os.path.expanduser(str(d)) for d in extra]
    except Exception:
        pass
    return [d for d in dirs if os.path.isdir(d)]


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) >= 2}


class LocalMusicLibrary:
    def __init__(self, index_path: str = _INDEX_PATH):
        self._path = index_path
        self._lock = threading.Lock()
        self._tracks: list[dict] = []      # {"path", "name", "folder"}
        self._built_at = 0.0
        self._load()

    # ── persistence ──────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, encoding="utf-8") as f:
                d = json.load(f)
            self._tracks = list(d.get("tracks", []))
            self._built_at = float(d.get("built_at", 0.0))
        except Exception:
            pass

    def _save(self) -> None:
        try:
            from core.atomic_io import write_atomic_json
            write_atomic_json(self._path, {
                "built_at": self._built_at, "tracks": self._tracks})
        except Exception as e:
            log.warning("[music] save failed: %s", e)

    # ── index ────────────────────────────────────────────────────────
    def build(self, folders: Optional[list[str]] = None) -> dict:
        folders = folders or default_folders()
        tracks: list[dict] = []
        for folder in folders:
            for root, dirs, names in os.walk(folder):
                dirs[:] = [d for d in dirs
                           if d not in _SKIP_DIRS and not d.startswith(".")]
                for name in names:
                    if os.path.splitext(name)[1].lower() in _AUDIO_EXT:
                        tracks.append({
                            "path": os.path.join(root, name),
                            "name": os.path.splitext(name)[0],
                            "folder": os.path.basename(folder),
                        })
                        if len(tracks) >= _MAX_FILES:
                            break
                if len(tracks) >= _MAX_FILES:
                    break
        with self._lock:
            self._tracks = tracks
            self._built_at = time.time()
            self._save()
        return {"tracks": len(tracks), "folders": folders}

    def ensure_fresh(self) -> None:
        if not self._tracks or (time.time() - self._built_at) > _STALE_S:
            self.build()

    def stats(self) -> dict:
        return {"tracks": len(self._tracks), "built_at": self._built_at}

    # ── search + play ────────────────────────────────────────────────
    def find(self, query: str, k: int = 5) -> list[dict]:
        """Token-overlap + substring fuzzy match over filenames."""
        self.ensure_fresh()
        q = (query or "").strip().lower()
        q_tokens = _tokens(q)
        if not q or not self._tracks:
            return []
        scored: list[tuple[float, dict]] = []
        for t in self._tracks:
            name = t["name"].lower()
            score = 0.0
            if q and q in name:
                score += 3.0
            name_tokens = _tokens(name)
            if q_tokens and name_tokens:
                hit = q_tokens & name_tokens
                score += 2.0 * len(hit) / len(q_tokens)
                # partial-token match ("kesari" ~ "kesariya")
                for qt in q_tokens - hit:
                    if any(nt.startswith(qt) or qt.startswith(nt)
                           for nt in name_tokens):
                        score += 0.8 / len(q_tokens)
            if score > 0.4:
                scored.append((score, t))
        scored.sort(key=lambda st: -st[0])
        return [t for _s, t in scored[:k]]

    def play_random(self) -> tuple[bool, str]:
        """Shuffle: play any one track ("local music bajao" with no name)."""
        self.ensure_fresh()
        with self._lock:
            tracks = list(self._tracks)
        if not tracks:
            return False, "Library khaali hai."
        import random
        track = random.choice(tracks)
        try:
            os.startfile(track["path"])
            return True, f"Shuffle: {track['name']}"
        except Exception as e:
            return False, f"Play nahi ho paya ({e})."

    def play(self, query: str) -> tuple[bool, str]:
        hits = self.find(query, k=1)
        if not hits:
            n = len(self._tracks)
            if n == 0:
                return False, ("Library khaali hai — Music/Downloads mein "
                               "audio files nahi mili. 'music library "
                               "reindex karo' try karo.")
            return False, (f"'{query}' library ({n} tracks) mein nahi mila.")
        track = hits[0]
        try:
            os.startfile(track["path"])          # default player, pure local
            return True, f"Chala raha hoon: {track['name']}"
        except Exception as e:
            return False, f"Play nahi ho paya ({e})."


_LIB: Optional[LocalMusicLibrary] = None
_LIB_LOCK = threading.Lock()


def get_library() -> LocalMusicLibrary:
    global _LIB
    with _LIB_LOCK:
        if _LIB is None:
            _LIB = LocalMusicLibrary()
        return _LIB
