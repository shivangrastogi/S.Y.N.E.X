"""Local music by voice — "local gaana bajao kesariya".

Disk-only jukebox (core/local_music): Music/Downloads index + fuzzy
filename match + default-player playback. Deliberately separate from the
existing ``play_music`` (jo Spotify/web kholta hai) — ye AERIS ka APNA,
offline raasta hai.
"""
from __future__ import annotations

import logging
import re
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)

_STRIP_RE = re.compile(
    r"^(?:mera\s+)?(?:local|offline|downloaded)\s*"
    r"(?:gaana|gana|song|music)?\s*"
    r"(?:bajao|chalao|play\s+karo|play|suna(?:o|do))\s*"
    r"|^(?:local\s+music\s+bajao|local\s+song\s+play\s+karo)\s*",
    re.IGNORECASE,
)


@skill(
    name="local_music_play",
    description="Play a song from the LOCAL disk library (Music/Downloads) in the default player — no Spotify, no web.",
    patterns=[
        "local gaana bajao", "local music bajao", "offline gaana bajao",
        "local song play karo", "mera downloaded gaana chalao",
        "mera gana chalao local se", "downloaded song bajao",
        "local se bajao",
    ],
    required_entities=[],
)
def local_music_play(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _STRIP_RE.sub("", text).strip(" ?\"'")
    from core.local_music import get_library
    lib = get_library()
    if not query:
        # Bare "local music bajao" → shuffle: koi bhi ek track.
        ok, msg = lib.play_random()
        if ok:
            return msg
        return ("Kaunsa gaana, sir? Jaise: 'local gaana bajao kesariya'. "
                "(Ya pehle 'music library reindex karo'.)")
    _ok, msg = lib.play(query)
    return msg


@skill(
    name="local_music_list",
    description="Show what's in the local music library (top matches or totals).",
    patterns=[
        "music library dikhao", "mere gaane dikhao", "local music list",
        "library me kya gaane hain", "kitne gaane hain library me",
    ],
    required_entities=[],
)
def local_music_list(slots: dict) -> str:
    from core.local_music import get_library
    lib = get_library()
    lib.ensure_fresh()
    st = lib.stats()
    if not st["tracks"]:
        return ("Library khaali hai — Music/Downloads mein audio nahi mila. "
                "settings 'music_dirs' mein aur folders add kar sakte ho.")
    text = (slots.get("raw_text") or "")
    q = re.sub(r".*?(?:dikhao|list|hain)\s*", "", text).strip()
    hits = lib.find(q, 5) if q else []
    if hits:
        names = " · ".join(h["name"][:40] for h in hits)
        return f"{len(hits)} match: {names}"
    when = time.strftime("%d %b %H:%M", time.localtime(st["built_at"])) \
        if st["built_at"] else "—"
    return (f"Library mein {st['tracks']} tracks hain (indexed {when}). "
            "'local gaana bajao <naam>' se chalao.")


@skill(
    name="local_music_reindex",
    description="Rebuild the local music index from Music/Downloads (+ settings music_dirs).",
    patterns=[
        "music library reindex karo", "local music index karo",
        "music library refresh karo", "gaane dobara index karo",
    ],
    required_entities=[],
)
def local_music_reindex(_slots: dict) -> str:
    from core.local_music import get_library
    r = get_library().build()
    return (f"{r['tracks']} tracks index kiye "
            f"({len(r['folders'])} folder se).")
