"""Three-tier TTS — edge-tts (online) → pyttsx3 (offline) → SAPI5 via COM.

Each tier is independent: the module imports successfully even if pyttsx3 OR
edge_tts is missing, so a degraded environment still produces speech. The
SAPI5 path is a pure-ctypes/comtypes call, available on every Windows install
without any pip dependency — so the user always gets *some* voice output.
"""

import logging
import threading
import os
import re
import asyncio
import time
from typing import Optional

import pygame

log = logging.getLogger(__name__)

# Emoji / pictographs / symbols that a voice can't pronounce AND that crash the
# Windows cp1252 console/log stream ("'charmap' codec can't encode …"). Strip
# them before speaking or printing. Hinglish (Latin + Devanagari) is untouched.
_UNSPEAKABLE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoji, pictographs, symbols & extended
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U0001F1E6-\U0001F1FF"   # regional-indicator flags
    "\U00002190-\U000021FF"   # arrows
    "\U00002B00-\U00002BFF"   # misc symbols and arrows
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U00002022\U000025AA-\U000025FF"  # bullet + geometric shapes
    "]+",
    flags=re.UNICODE,
)


def _clean_for_speech(text: str) -> str:
    """Drop characters a TTS voice can't say and that break cp1252 output."""
    if not text:
        return text
    cleaned = _UNSPEAKABLE.sub("", text)
    # Collapse the whitespace an emoji removal can leave behind.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned or text

try:
    import edge_tts  # type: ignore
    _EDGE_OK = True
except Exception as _e:
    edge_tts = None
    _EDGE_OK = False
    log.info("[TTS] edge_tts unavailable: %s", _e)

try:
    import pyttsx3  # type: ignore
    _PYTTSX3_OK = True
except Exception as _e:
    pyttsx3 = None
    _PYTTSX3_OK = False
    log.info("[TTS] pyttsx3 unavailable: %s — falling back to SAPI5 over COM.", _e)


class TTS:
    def __init__(self, voice="en-IN-NeerjaNeural"):
        self.voice = voice
        self.rate = "+0%"
        self.pitch = "+0Hz"

        self.audio_dir = "data/audio_cache"
        os.makedirs(self.audio_dir, exist_ok=True)
        self.temp_file = os.path.join(self.audio_dir, "speech.mp3")

        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                log.warning("[TTS] pygame mixer init failed: %s", e)

        # Offline fallback. Lazy init so a hang in SAPI5 init doesn't
        # block the SpeakWorker startup — speak() will try again on demand.
        self.offline_engine = None
        self._pyttsx3_init_failed = False

        # Barge-in support: set from ANOTHER thread (the voice service's
        # capture loop, or a GUI stop button) to cut playback short. Playback
        # blocks, so interruption cannot be polite — it has to be a flag the
        # play loop checks and a mixer call that takes effect immediately.
        self._stop_evt = threading.Event()
        self._speaking = threading.Event()

    # ── public API ────────────────────────────────────────────────

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def stop(self) -> bool:
        """Cut playback short. Safe to call from any thread, and safe to call
        when nothing is playing (returns False).

        This is what makes barge-in possible: without it the user talking over
        AERIS had no way to shut it up, because `speak()` blocks until the
        audio finishes.
        """
        if not self._speaking.is_set():
            return False
        self._stop_evt.set()
        try:
            pygame.mixer.music.stop()
        except Exception as e:
            log.debug("[TTS] mixer stop raised: %s", e)
        eng = self.offline_engine
        if eng is not None:
            try:
                eng.stop()          # pyttsx3 tier
            except Exception as e:
                log.debug("[TTS] pyttsx3 stop raised: %s", e)
        return True

    def speak(self, text: str):
        """Try Edge-TTS first, then pyttsx3, then native SAPI5 via COM."""
        if not text:
            return
        # A new utterance clears any interruption left by the previous one,
        # or the first barge-in would silence everything said afterwards.
        self._stop_evt.clear()
        self._speaking.set()
        try:
            return self._speak_inner(text)
        finally:
            self._speaking.clear()

    def _speak_inner(self, text: str):
        # Strip emoji/symbols: a voice can't say them and they crash the
        # Windows cp1252 console/log stream ('charmap' codec can't encode …).
        text = _clean_for_speech(text)
        if not text:
            return
        try:
            print(f"Jarvis: {text}")
        except UnicodeEncodeError:
            # Last-resort guard if some exotic glyph slips through the filter.
            print("Jarvis:", text.encode("ascii", "ignore").decode())

        # Tier 1: Edge-TTS (online, neural voice). Skipped when missing or
        # when it raised last time within this process and stays unhealthy.
        if _EDGE_OK and self._try_edge_tts(text):
            return

        # Tier 2: pyttsx3 (offline, SAPI5 wrapper).
        if _PYTTSX3_OK and self._try_pyttsx3(text):
            return

        # Tier 3: native SAPI5 via COM — no pip deps required.
        if self._try_sapi5(text):
            return

        log.warning("[TTS] every TTS path failed — install pyttsx3 or check audio device.")

    # ── tier helpers ──────────────────────────────────────────────

    def _try_edge_tts(self, text: str) -> bool:
        try:
            # Resolve the live voice once so the cache key matches what we'd
            # actually synthesise (the TTS skill can change voice per-call).
            voice = _live_tts_voice() or self.voice

            # Phrase cache: short, repeated acks ("Done.", "Yes sir.") replay
            # from disk with no network round-trip. Best-effort — any cache
            # hiccup just falls through to a normal synth.
            from core import tts_cache
            cached = None
            try:
                cached = tts_cache.lookup(self.audio_dir, text, voice,
                                          self.rate, self.pitch)
            except Exception:
                cached = None
            if cached:
                self._play_file(cached)
                return True

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._generate_audio(text, voice))
            finally:
                loop.close()

            play_path = self.temp_file
            if tts_cache.is_cacheable(text):
                try:
                    play_path = tts_cache.store(self.audio_dir, self.temp_file,
                                                text, voice, self.rate, self.pitch)
                    tts_cache.prune(self.audio_dir)
                except Exception:
                    play_path = self.temp_file

            self._play_file(play_path)
            return True
        except Exception as e:
            log.info("[TTS] edge-tts failed (%s) — trying offline.", e)
            return False

    def _play_file(self, path: str) -> None:
        """Load + play an mp3 through pygame and block until it finishes —
        or until `stop()` interrupts it (barge-in)."""
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if self._stop_evt.is_set():
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                break
            time.sleep(0.05)
        pygame.mixer.music.unload()

    async def _generate_audio(self, text, voice=None):
        # Live voice override — reads ``tts_voice`` from settings each call
        # so the multi-language TTS skill takes effect immediately. The
        # caller may pass an already-resolved ``voice`` so the cache key and
        # the synthesised audio agree.
        if voice is None:
            voice = _live_tts_voice() or self.voice
        communicate = edge_tts.Communicate(
            text, voice, rate=self.rate, pitch=self.pitch
        )
        await communicate.save(self.temp_file)

    def _try_pyttsx3(self, text: str) -> bool:
        if self._pyttsx3_init_failed:
            return False
        try:
            if self.offline_engine is None:
                self.offline_engine = pyttsx3.init()
            # Apply live settings each call so voice_tuning skills
            # (speak slower / louder / etc.) take effect immediately.
            rate, vol = _live_voice_settings()
            try:
                self.offline_engine.setProperty("rate", rate)
                self.offline_engine.setProperty("volume", vol)
            except Exception:
                pass
            self.offline_engine.say(text)
            self.offline_engine.runAndWait()
            return True
        except Exception as e:
            log.info("[TTS] pyttsx3 failed (%s) — trying SAPI5.", e)
            self._pyttsx3_init_failed = True
            return False

    def _try_sapi5(self, text: str) -> bool:
        """Native Windows SAPI5 via COM. Works on any Windows box without
        extra pip packages — the COM CLSID is part of the OS.

        Applies live voice settings (speech_rate → SAPI Rate; voice_volume
        → SAPI Volume) so the voice_tuning skill changes are reflected on
        every utterance.
        """
        rate_wpm, vol = _live_voice_settings()
        # SAPI Rate is -10..+10 (relative). 175 wpm ≈ Rate 0.
        sapi_rate = max(-10, min(10, int(round((rate_wpm - 175) / 20))))
        sapi_vol = max(0, min(100, int(round(vol * 100))))
        try:
            import comtypes.client  # type: ignore
        except Exception:
            try:
                import win32com.client as _wc  # type: ignore
                voice = _wc.Dispatch("SAPI.SpVoice")
                try:
                    voice.Rate = sapi_rate
                    voice.Volume = sapi_vol
                except Exception:
                    pass
                voice.Speak(text)
                return True
            except Exception as e:
                log.warning("[TTS] SAPI5 via win32com unavailable: %s", e)
                return False
        try:
            voice = comtypes.client.CreateObject("SAPI.SpVoice")
            try:
                voice.Rate = sapi_rate
                voice.Volume = sapi_vol
            except Exception:
                pass
            voice.Speak(text)
            return True
        except Exception as e:
            log.warning("[TTS] SAPI5 via comtypes failed: %s", e)
            return False


def _live_voice_settings() -> tuple[int, float]:
    """Read current speech_rate (wpm, 80..350) and voice_volume (0..1) from
    the settings store. Falls back to (175, 1.0) when settings missing or
    the import fails (early-boot edge case)."""
    try:
        from core import settings as _settings
        rate = int(_settings.get("speech_rate") or 175)
        vol = float(_settings.get("voice_volume", 1.0) or 1.0)
        return max(80, min(350, rate)), max(0.0, min(1.0, vol))
    except Exception:
        return 175, 1.0


def _live_tts_voice() -> Optional[str]:
    """Read the optional ``tts_voice`` override from settings.

    Falsy (None / empty) means "use the TTS constructor default".
    Used by the multi-language TTS skill to switch voices on the fly
    without restarting the engine.
    """
    try:
        from core import settings as _settings
        v = _settings.get("tts_voice")
    except Exception:
        return None
    v = (v or "").strip()
    return v or None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    TTS().speak("Hello, this is Jarvis. Main Hinglish bol sakta hoon.")
