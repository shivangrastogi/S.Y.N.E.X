"""Voice memos — record short audio clips, play back, list, delete.

Captures via pyaudio (16 kHz mono PCM) → wav file in ``data/notes/audio/``.
Playback through pygame.mixer. Each memo named ``memo_YYYYmmdd_HHMMSS.wav``.

Recording runs on a daemon thread so the user's voice command isn't
blocked while the mic is open. Auto-stops at the configured duration or
when ``stop_voice_memo`` is invoked.

Skills:
  * ``record_voice_memo``  — start recording (default 10s)
  * ``stop_voice_memo``    — stop early
  * ``play_last_memo``     — play the most recent memo
  * ``play_memo <name>``   — play by partial name match
  * ``list_voice_memos``   — list recent memos
  * ``delete_last_memo``   — delete the most recent memo
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parents[1]
_MEMO_DIR = _HERE / "data" / "notes" / "audio"


# Audio params
_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2     # 16-bit PCM
_CHUNK = 1024
_DEFAULT_DURATION_S = 10
_MAX_DURATION_S = 120


# Recording state (process-wide; only one recording at a time)
_REC_LOCK = threading.RLock()
_REC_STATE: dict = {
    "active": False,
    "started_at": 0.0,
    "duration_s": 0,
    "filename": None,
    "stop_event": None,
    "thread": None,
}


def _ensure_dir() -> None:
    _MEMO_DIR.mkdir(parents=True, exist_ok=True)


def _list_files() -> list[Path]:
    if not _MEMO_DIR.is_dir():
        return []
    return sorted([p for p in _MEMO_DIR.iterdir()
                   if p.is_file() and p.suffix.lower() == ".wav"],
                  key=lambda p: p.stat().st_mtime)


def _parse_duration(text: str, default: int = _DEFAULT_DURATION_S) -> int:
    if not text:
        return default
    m = re.search(r"\b(\d+)\s*(s|sec|secs|seconds?|min|minute|minutes)?\b",
                  text, re.IGNORECASE)
    if not m:
        return default
    n = int(m.group(1))
    unit = (m.group(2) or "seconds").lower()
    if unit.startswith(("m", "min")):
        n *= 60
    return max(1, min(_MAX_DURATION_S, n))


def _record_loop(filename: Path, duration_s: int, stop_event: threading.Event) -> None:
    """Worker thread — open mic, write PCM to file, close on stop event."""
    try:
        import pyaudio  # type: ignore
    except Exception as e:
        log.warning("[voice_memo] pyaudio import failed: %s", e)
        return
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pa.get_format_from_width(_SAMPLE_WIDTH),
                         channels=_CHANNELS, rate=_RATE,
                         input=True, frames_per_buffer=_CHUNK)
    except Exception as e:
        log.warning("[voice_memo] open mic failed: %s", e)
        return
    try:
        frames: list[bytes] = []
        deadline = time.monotonic() + duration_s
        while not stop_event.is_set() and time.monotonic() < deadline:
            try:
                data = stream.read(_CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                log.debug("[voice_memo] read err: %s", e)
                break
        try:
            with wave.open(str(filename), "wb") as wf:
                wf.setnchannels(_CHANNELS)
                wf.setsampwidth(_SAMPLE_WIDTH)
                wf.setframerate(_RATE)
                wf.writeframes(b"".join(frames))
        except Exception as e:
            log.warning("[voice_memo] wav write failed: %s", e)
    finally:
        try: stream.stop_stream()
        except Exception: pass
        try: stream.close()
        except Exception: pass
        try: pa.terminate()
        except Exception: pass
        with _REC_LOCK:
            _REC_STATE["active"] = False


# ── record_voice_memo ──────────────────────────────────────────────


@skill(
    name="record_voice_memo",
    description="Record a short voice memo via the mic (default 10s, max 120s). "
                "Saved as WAV under data/notes/audio/.",
    patterns=[
        "record voice memo", "voice memo record karo", "record memo",
        "start recording", "ek memo record karo",
        "voice note record", "audio note",
        "record 30 second memo", "memo record karo",
        "start voice recording",
    ],
    required_entities=[],
)
def record_voice_memo(slots: dict) -> str:
    with _REC_LOCK:
        if _REC_STATE["active"]:
            return "Already recording — 'stop voice memo' bolo to band karo."
    text = slots.get("raw_text") or slots.get("text") or ""
    duration = _parse_duration(text)
    _ensure_dir()
    fname = _MEMO_DIR / f"memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    stop_evt = threading.Event()
    th = threading.Thread(target=_record_loop, args=(fname, duration, stop_evt),
                          daemon=True, name="VoiceMemo")
    with _REC_LOCK:
        _REC_STATE.update({
            "active": True,
            "started_at": time.monotonic(),
            "duration_s": duration,
            "filename": fname,
            "stop_event": stop_evt,
            "thread": th,
        })
    th.start()
    return (f"Recording {duration}s memo → {fname.name}. "
            f"'stop voice memo' to end early.")


# ── stop_voice_memo ────────────────────────────────────────────────


@skill(
    name="stop_voice_memo",
    description="Stop an in-progress voice memo recording.",
    patterns=[
        "stop voice memo", "stop recording", "memo stop karo",
        "recording band karo", "stop memo",
        "voice memo band karo", "stop the memo",
    ],
    required_entities=[],
)
def stop_voice_memo(_slots: dict) -> str:
    with _REC_LOCK:
        if not _REC_STATE["active"]:
            return "Koi recording chal raha nahi tha."
        evt = _REC_STATE.get("stop_event")
        fname = _REC_STATE.get("filename")
    if evt is not None:
        evt.set()
    # Wait briefly for the worker to flush the file.
    th = _REC_STATE.get("thread")
    if th is not None:
        th.join(timeout=2.0)
    return f"Stopped — saved to {fname.name if fname else '(unknown)'}."


# ── play_last_memo / play_memo ─────────────────────────────────────


def _play_file(path: Path) -> str:
    try:
        import pygame  # type: ignore
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        # Don't block the brain thread on playback — just kick it off.
        return f"Playing {path.name} (ctrl+c not needed; runs in background)."
    except Exception as e:
        return f"Playback fail: {e}"


@skill(
    name="play_last_memo",
    description="Play the most recently recorded voice memo.",
    patterns=[
        "play last memo", "play last voice memo", "last memo chalao",
        "last memo play karo", "memo sunao", "last memo sunao",
        "play recent memo", "last voice note play",
    ],
    required_entities=[],
)
def play_last_memo(_slots: dict) -> str:
    files = _list_files()
    if not files:
        return "Koi memo nahi mila — pehle 'record voice memo' bolo."
    return _play_file(files[-1])


@skill(
    name="play_memo",
    description="Play a memo by partial filename match (e.g. timestamp prefix).",
    patterns=[
        "play memo", "play voice memo", "memo chalao",
        "play memo named", "voice note chalao",
    ],
    required_entities=[],
)
def play_memo(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = re.sub(r"^(?:please\s+)?"
                   r"(?:play|chalao|sunao|voice\s+note\s+chalao|"
                   r"play\s+voice\s+memo|play\s+memo|memo\s+chalao)\s*",
                   "", text.strip(), flags=re.IGNORECASE).strip(" :,.?\"'")
    files = _list_files()
    if not files:
        return "Koi memo file nahi mili."
    if not query:
        return play_last_memo({})
    matches = [p for p in files if query.lower() in p.name.lower()]
    if not matches:
        return f"'{query}' jaisi memo nahi mili."
    return _play_file(matches[-1])


# ── list_voice_memos ───────────────────────────────────────────────


@skill(
    name="list_voice_memos",
    description="List the most recent voice memos with timestamps.",
    patterns=[
        "list memos", "list voice memos", "show memos",
        "memos dikhao", "kaunse memos hain", "voice notes list",
        "list voice notes", "all memos",
    ],
    required_entities=[],
)
def list_voice_memos(_slots: dict) -> str:
    files = _list_files()
    if not files:
        return "Koi memo nahi hai."
    tail = files[-10:]
    lines = [f"{len(tail)} most recent memo(s):"]
    for p in tail:
        mt = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = max(1, p.stat().st_size // 1024)
        lines.append(f"  • {mt}  {p.name}  ({size_kb} KB)")
    return "\n".join(lines)


# ── delete_last_memo ───────────────────────────────────────────────


@skill(
    name="delete_last_memo",
    description="Delete the most recently recorded voice memo.",
    patterns=[
        "delete last memo", "last memo delete karo", "remove last memo",
        "discard last memo", "last memo hatao",
    ],
    required_entities=[],
)
def delete_last_memo(_slots: dict) -> str:
    files = _list_files()
    if not files:
        return "Koi memo delete karne ko hai hi nahi."
    p = files[-1]
    try:
        p.unlink()
        return f"Deleted: {p.name}"
    except Exception as e:
        return f"Delete fail: {e}"
