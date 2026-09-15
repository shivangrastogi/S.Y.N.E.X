"""Audio-file transcription — local whisper, koi cloud nahi.

"audio transcribe karo C:\\recs\\meeting.wav" → poora text, aur lambi
transcripts data/notes mein save. Backend = core/stt_whisper
(faster-whisper, fully offline). Engine install na ho to saaf-saaf batata
hai — kabhi kisi API par nahi girta. (Ye Shivang ke curated LIVE voice
stack se alag hai — wo Google en-IN STT hi rahega; ye sirf FILES ke liye
hai.)
"""
from __future__ import annotations

import logging
import os
import re
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)

_PATH_RE = re.compile(r"[A-Za-z]:[\\\/][^\"'\n]+|~[\\\/][^\"'\n]+")
_AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac",
              ".wma", ".webm", ".mp4"}
_SPOKEN_CAP = 400          # TTS ke liye itna hi bolo; poora note mein


@skill(
    name="transcribe_file",
    description="Transcribe an audio file to text with the LOCAL whisper engine (offline).",
    patterns=[
        "transcribe file", "audio transcribe karo",
        "recording transcribe karo", "is audio ko text banao",
        "audio file ka text nikalo", "audio ka transcript do",
    ],
    required_entities=[],
)
def transcribe_file(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _PATH_RE.search(text)
    if not m:
        return ("Kaunsi audio file, sir? Path do — jaise: 'audio "
                "transcribe karo C:\\recs\\meeting.wav'.")
    path = os.path.expanduser(m.group(0).strip().rstrip(".") )
    if not os.path.isfile(path):
        return f"File nahi mili: {path}"
    if os.path.splitext(path)[1].lower() not in _AUDIO_EXT:
        return "Ye audio file nahi lagti (wav/mp3/m4a/flac… chahiye)."

    try:
        from core.stt_whisper import get_whisper_engine
        eng = get_whisper_engine()
    except Exception as e:
        return f"Whisper engine load nahi hua: {e}"
    if not eng.is_available():
        return ("Offline transcription ke liye faster-whisper chahiye — "
                "ek baar `pip install faster-whisper` chala do; uske baad "
                "sab kuch bina internet ke chalega.")

    t0 = time.time()
    out = eng.transcribe(path)
    if not out or not out.strip():
        return "Transcription se kuch nahi nikla — audio khaali ya unclear hai."
    out = out.strip()
    dt = time.time() - t0

    saved = ""
    if len(out) > _SPOKEN_CAP:
        try:
            notes_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "notes")
            os.makedirs(notes_dir, exist_ok=True)
            name = ("transcript_"
                    + os.path.splitext(os.path.basename(path))[0][:40]
                    + time.strftime("_%Y%m%d-%H%M%S") + ".txt")
            fp = os.path.join(notes_dir, name)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(out)
            saved = f"  (poora transcript: data/notes/{name})"
        except Exception as e:
            log.debug("[transcribe] note save failed: %s", e)
    spoken = out[:_SPOKEN_CAP] + ("…" if len(out) > _SPOKEN_CAP else "")
    return f"{spoken}{saved}  [{dt:.0f}s]"
