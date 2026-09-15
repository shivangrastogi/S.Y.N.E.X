"""Dependency completeness validator.

Maintains a hand-curated map of ``dependency → affected_skills`` so we
can tell the user "if you `pip install pycaw`, these 4 skills come back
online". Used by the enriched diagnostics + the first-run wizard.

Public API:
    list_deps() -> list[dict]   # one entry per dep + affected skills + install hint
    missing_skills() -> dict     # {skill_name: [missing dep names]}
"""
from __future__ import annotations

import importlib
import logging
from typing import Iterable

log = logging.getLogger(__name__)


# (dep import name, pip install hint, [affected skill names])
_DEP_MAP: list[tuple[str, str, list[str]]] = [
    # Audio
    ("pyttsx3",   "pip install pyttsx3",
     ["voice_slower", "voice_faster", "voice_louder", "voice_softer",
      "voice_reset", "voice_status"]),
    ("pycaw",     "pip install pycaw comtypes",
     ["app_mute", "app_unmute", "app_volume_set", "app_volume_list"]),
    ("edge_tts",  "pip install edge-tts",
     ["tts_voice_set", "tts_voice_list"]),
    ("pyaudio",   "pip install pyaudio",
     ["record_voice_memo", "stop_voice_memo", "speaker_enroll",
      "speaker_identify", "whisper_transcribe_once"]),
    ("pygame",    "pip install pygame",
     ["play_last_memo", "play_memo"]),

    # Vision
    ("cv2",         "pip install opencv-python",
     ["gesture_mode_on", "screenshot_window", "ar_overlay_on", "auto_label_on"]),
    ("mediapipe",   "pip install mediapipe",
     ["gesture_mode_on", "practice_gesture", "gesture_record"]),
    ("insightface", "pip install insightface",
     ["i_am_master", "register_face", "presence_auto_pause_on"]),
    ("ultralytics", "pip install ultralytics",
     ["auto_label_on", "ar_overlay_on", "object_in_view"]),
    ("PIL",         "pip install Pillow",
     ["screenshot_full", "screenshot_window", "last_screenshot_to_clipboard"]),
    ("mss",         "pip install mss",
     ["screenshot_full"]),

    # NLP / ML
    ("sentence_transformers", "pip install sentence-transformers",
     ["doc_index_folder", "doc_query"]),
    ("transformers", "pip install transformers", []),
    ("spacy",        "pip install spacy && python -m spacy download en_core_web_sm",
     []),
    ("faster_whisper", "pip install faster-whisper",
     ["whisper_transcribe_once", "whisper_set_model"]),

    # Productivity
    ("pyperclip",   "pip install pyperclip",
     ["clipboard_copy", "clipboard_paste", "clipboard_say",
      "clipboard_stats", "clipboard_open_url", "translate_clipboard"]),
    ("feedparser",  "pip install feedparser",
     ["news_briefing"]),
    ("pytesseract", "pip install pytesseract",
     ["snip_ocr"]),

    # Windows-specific helpers
    ("win32com.client", "pip install pywin32",
     ["next_meeting", "todays_meetings", "this_week_meetings",
      "compose_email", "email_draft_blank"]),
    ("comtypes",    "pip install comtypes",
     ["app_mute", "app_volume_set"]),
    ("winsdk",      "pip install winsdk",
     ["notification_mirror_on", "last_notification"]),
    ("win10toast",  "pip install win10toast",
     []),

    # LLM
    ("ollama",      "install ollama runtime + 'ollama pull llama3.2'",
     ["ask_jarvis", "llm_status", "translate_to"]),
    ("argostranslate", "pip install argostranslate",
     ["translate_to", "translate_clipboard"]),
]


def _is_installed(mod: str) -> bool:
    """Check if a module imports without actually keeping it loaded."""
    try:
        spec = importlib.util.find_spec(mod)
        return spec is not None
    except Exception:
        return False


def list_deps() -> list[dict]:
    """Each entry: {dep, installed, fix, affected: [skill,...], affected_count}"""
    out: list[dict] = []
    for dep, fix, skills in _DEP_MAP:
        out.append({
            "dep":            dep,
            "installed":      _is_installed(dep),
            "fix":            fix,
            "affected":       skills,
            "affected_count": len(skills),
        })
    return sorted(out, key=lambda r: (r["installed"], -r["affected_count"], r["dep"]))


def missing_skills() -> dict:
    """Return {skill_name: [dep_name, ...]} for every skill that depends
    on a missing optional dep."""
    out: dict[str, list[str]] = {}
    for dep, _fix, skills in _DEP_MAP:
        if _is_installed(dep):
            continue
        for sk in skills:
            out.setdefault(sk, []).append(dep)
    return out


def health_score() -> int:
    """Return 0-100, weighted by how many skills are affected."""
    total = 0
    missing = 0
    for dep, _fix, skills in _DEP_MAP:
        weight = max(1, len(skills))
        total += weight
        if not _is_installed(dep):
            missing += weight
    if total == 0:
        return 100
    return max(0, int(round(100 * (1 - missing / total))))
