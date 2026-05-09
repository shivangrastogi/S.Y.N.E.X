"""Track-level Spotify control via Spotipy. Needs SPOTIPY_CLIENT_ID + _SECRET + _REDIRECT_URI."""

from __future__ import annotations

import os

from core.skill_registry import skill

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    _AVAILABLE = True
except ImportError:
    spotipy = None
    SpotifyOAuth = None
    _AVAILABLE = False


_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET", "")
_REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "http://localhost:8888/callback")


_client_singleton: "spotipy.Spotify | None" = None


def _get_client():
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton
    if not (_AVAILABLE and _CLIENT_ID and _CLIENT_SECRET):
        return None
    auth = SpotifyOAuth(
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        redirect_uri=_REDIRECT_URI,
        scope="user-modify-playback-state user-read-playback-state",
        cache_path=".spotipy_cache",
        open_browser=True,
    )
    _client_singleton = spotipy.Spotify(auth_manager=auth)
    return _client_singleton


@skill(
    name="spotify_play_track",
    description="Search Spotify for a specific track and start playback on the active device",
    patterns=[
        "spotify pe X chala do",
        "play X on spotify",
        "X gaana chala do spotify pe",
        "X by Y chala do",
    ],
    required_entities=["query"],
    prompts={"query": "Kaunsa gaana chalana hai?"},
)
def spotify_play_track(slots: dict) -> str:
    if not _AVAILABLE:
        return "spotipy install nahi hai. 'pip install spotipy' chalao."
    sp = _get_client()
    if sp is None:
        return "Spotify client ID/secret nahi hai. SPOTIPY_CLIENT_ID + SPOTIPY_CLIENT_SECRET set karo."

    query = (slots.get("query") or "").strip()
    if not query:
        return "Kya chalana hai? Track ka naam batao."

    try:
        results = sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            return f"'{query}' Spotify pe nahi mila."
        track = items[0]
        sp.start_playback(uris=[track["uri"]])
        artist = track["artists"][0]["name"]
        return f"{artist} ka '{track['name']}' chala raha hoon."
    except Exception as e:
        return f"Spotify play fail ho gaya: {e}"


@skill(
    name="spotify_pause",
    description="Pause Spotify playback on the active device",
    patterns=["spotify pause karo", "music pause kar do", "pause the music"],
    required_entities=[],
)
def spotify_pause(_slots: dict) -> str:
    sp = _get_client()
    if sp is None:
        return "Spotify configured nahi hai."
    try:
        sp.pause_playback()
        return "Pause kar diya."
    except Exception as e:
        return f"Pause fail: {e}"


@skill(
    name="spotify_next",
    description="Skip to next Spotify track",
    patterns=["agla gaana chalao", "next song", "skip karo", "next track"],
    required_entities=[],
)
def spotify_next(_slots: dict) -> str:
    sp = _get_client()
    if sp is None:
        return "Spotify configured nahi hai."
    try:
        sp.next_track()
        return "Agla gaana."
    except Exception as e:
        return f"Skip fail: {e}"
