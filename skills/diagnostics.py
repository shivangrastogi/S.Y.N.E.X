"""Diagnostics skill — answer "kya kya kaam kar raha hai?"

Probes every subsystem that has caused silent failures in the past and
reports each as OK / DEGRADED / MISSING with a one-line fix hint.
Covers the exact bugs the user hit recently:

  * pyttsx3 missing            → TTS silent
  * pycaw missing              → volume gesture noop
  * spaCy missing              → fewer entities extracted
  * mediapipe missing          → gesture engine disabled
  * camera unavailable         → vision/gesture engines disabled
  * huggingface offline        → encoder load hangs the splash

Returns a multi-line plain-text report. Each line ends in [OK], [WARN], or
[MISS] so it's easy to skim and the GUI's logs panel can color-code it.
"""
from __future__ import annotations

import importlib
import logging
import os
import platform
import sys
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _check_module(name: str, fix: str) -> str:
    try:
        importlib.import_module(name)
        return f"  {name:18s} [OK]"
    except ImportError:
        return f"  {name:18s} [MISS]  →  {fix}"
    except Exception as e:
        return f"  {name:18s} [WARN]  →  {type(e).__name__}: {e}"


def _check_camera() -> str:
    try:
        import cv2  # type: ignore
    except Exception as e:
        return f"  camera             [MISS]  →  pip install opencv-python ({e})"
    # Open / release the default device once. Don't actually pull frames.
    cap = cv2.VideoCapture(0, getattr(cv2, "CAP_DSHOW", 700))
    try:
        if cap.isOpened():
            return "  camera             [OK]"
        return "  camera             [WARN]  →  device 0 didn't open (in use / no webcam?)"
    finally:
        cap.release()


def _check_hf_offline_mode() -> str:
    offline = os.environ.get("HF_HUB_OFFLINE") == "1"
    cache_dir = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub"
    )
    model = "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
    cached = os.path.isdir(os.path.join(cache_dir, model))
    if offline and cached:
        return "  hf encoder cache   [OK]    (offline mode + cache present)"
    if not offline and cached:
        return "  hf encoder cache   [WARN]  →  set HF_HUB_OFFLINE=1 for instant boot"
    if offline and not cached:
        return "  hf encoder cache   [WARN]  →  offline but no cache; run online once"
    return "  hf encoder cache   [WARN]  →  fresh install — first boot downloads ~120 MB"


def _check_pycaw_volume() -> str:
    try:
        from pycaw.pycaw import AudioUtilities  # type: ignore
        sp = AudioUtilities.GetSpeakers()
        _ = getattr(sp, "EndpointVolume", None)
        return "  pycaw (volume)     [OK]"
    except ImportError:
        return "  pycaw (volume)     [MISS]  →  pip install pycaw comtypes (volume gesture uses VK_VOLUME_UP/DOWN fallback)"
    except Exception as e:
        return f"  pycaw (volume)     [WARN]  →  {type(e).__name__}: {e}"


def _check_tts_paths() -> list[str]:
    rows = []
    try:
        import edge_tts  # type: ignore  # noqa: F401
        rows.append("  edge-tts           [OK]    (needs internet)")
    except ImportError:
        rows.append("  edge-tts           [MISS]  →  pip install edge-tts")
    try:
        import pyttsx3  # type: ignore  # noqa: F401
        rows.append("  pyttsx3            [OK]    (offline SAPI5 wrapper)")
    except ImportError:
        rows.append("  pyttsx3            [MISS]  →  pip install pyttsx3 (SAPI5 fallback still works)")
    # SAPI5 native — always present on Windows.
    if platform.system() == "Windows":
        try:
            import comtypes.client  # type: ignore  # noqa: F401
            rows.append("  SAPI5 (native)     [OK]    (always-available fallback)")
        except ImportError:
            try:
                import win32com.client  # type: ignore  # noqa: F401
                rows.append("  SAPI5 (native)     [OK]    (via win32com)")
            except ImportError:
                rows.append("  SAPI5 (native)     [WARN]  →  no comtypes/pywin32; native SAPI5 unreachable")
    return rows


@skill(
    name="diagnostics",
    description="Full health check — probe TTS, gesture, vision, brain subsystems and report each as OK/MISSING with a fix hint.",
    patterns=[
        "diagnose", "diagnostics", "run diagnostics", "self check",
        "self test", "health check", "system check", "kya kya kaam kar raha hai",
        "are you ok", "are you working", "sab thik hai kya",
        "what's broken", "kya broken hai", "status check", "doctor",
        "jarvis check yourself", "diagnose yourself", "report card",
    ],
    required_entities=[],
)
def diagnostics(_slots: dict) -> str:
    rows: list[str] = [f"AERIS diagnostics — {platform.system()} {platform.release()}, Python {sys.version_info.major}.{sys.version_info.minor}"]

    rows.append("")
    rows.append("── Speech ────────────────────────────")
    rows.extend(_check_tts_paths())

    rows.append("")
    rows.append("── Audio (volume gesture / mic mute) ─")
    rows.append(_check_pycaw_volume())

    rows.append("")
    rows.append("── Vision / gesture ─────────────────")
    rows.append(_check_module("cv2",          "pip install opencv-python"))
    rows.append(_check_module("mediapipe",    "pip install mediapipe"))
    rows.append(_check_module("insightface",  "pip install insightface  (for master-user face gate)"))
    rows.append(_check_module("ultralytics",  "pip install ultralytics  (for auto-label / object detect)"))
    rows.append(_check_camera())

    # Face gate summary
    try:
        from core.face_gate import explain as _gate_explain
        rows.append(f"  {_gate_explain()}")
    except Exception as e:
        rows.append(f"  face gate         [WARN]  →  {e}")

    rows.append("")
    rows.append("── Brain / NLP ──────────────────────")
    rows.append(_check_module("sentence_transformers", "pip install sentence-transformers"))
    rows.append(_check_module("sklearn",              "pip install scikit-learn"))
    rows.append(_check_module("transformers",         "pip install transformers"))
    rows.append(_check_module("spacy",                "pip install spacy && python -m spacy download en_core_web_sm"))
    rows.append(_check_hf_offline_mode())

    rows.append("")
    rows.append("── STT / wake-word ──────────────────")
    rows.append(_check_module("vosk",              "pip install vosk"))
    rows.append(_check_module("speech_recognition", "pip install SpeechRecognition"))
    rows.append(_check_module("pyaudio",           "pip install pyaudio"))

    rows.append("")
    rows.append("── Optional skill deps ──────────────")
    rows.append(_check_module("pyperclip",   "pip install pyperclip      (clipboard skill)"))
    rows.append(_check_module("feedparser",  "pip install feedparser     (news skill)"))
    rows.append(_check_module("pytesseract", "pip install pytesseract    (snip-OCR)"))
    rows.append(_check_module("mss",         "pip install mss            (screenshot capture)"))
    rows.append(_check_module("ultralytics", "pip install ultralytics    (YOLOv8 object detect)"))

    miss = sum(1 for r in rows if "[MISS]" in r)
    warn = sum(1 for r in rows if "[WARN]" in r)
    okc  = sum(1 for r in rows if "[OK]"   in r)
    rows.append("")
    rows.append(f"Summary: {okc} OK · {warn} WARN · {miss} MISS")
    return "\n".join(rows)
