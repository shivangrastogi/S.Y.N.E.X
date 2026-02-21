# BACKEND/core/listener/speech_listener.py
import os
import speech_recognition as sr
from mtranslate import translate
from colorama import Fore, init

init(autoreset=True)


class SpeechListener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self._failures = 0

        # 🔑 KEY IMPROVEMENTS
        self.recognizer.energy_threshold = 3000
        self.recognizer.dynamic_energy_threshold = True

        # Allow thinking pauses
        self.recognizer.pause_threshold = 1.2
        self.recognizer.non_speaking_duration = 0.8

        # Optional device selection via env
        try:
            device_env = os.getenv("MIC_DEVICE_INDEX")
            self.device_index = int(device_env) if device_env is not None else None
        except Exception:
            self.device_index = None

    def _reset_recognizer(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 3000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.2
        self.recognizer.non_speaking_duration = 0.8

    def _to_english(self, text: str) -> str:
        """Return English text. Translate Hindi to English."""

        # Keywords where translation breaks meaning
        NO_TRANSLATE_KEYWORDS = [
            "youtube",
            "play",
            "search",
            "song",
            "video",
            "whatsapp",
            "message",
            "call",
            "open",
            "send"
        ]

        if any(word in text.lower() for word in NO_TRANSLATE_KEYWORDS):
            return text  # 🔥 KEEP ORIGINAL

        # If the text contains Hindi characters, translate to English
        if any('\u0900' <= ch <= '\u097F' for ch in text):
            try:
                return translate(text, "en-us")
            except Exception as e:
                print(Fore.RED + f"[Translation Error] {e}")
                return text

        try:
            return translate(text, "en-us")
        except Exception as e:
            print(Fore.RED + f"[Translation Error] {e}")
            return text

    def listen(self, timeout=6, phrase_time_limit=8, max_attempts=3) -> str:
        """
        Listens once and returns recognized English text.
        Returns empty string on failure.
        """
        attempts = 0
        while attempts < max_attempts:
            try:
                with sr.Microphone(device_index=self.device_index) as source:
                    print(Fore.LIGHTGREEN_EX + "🎙 Listening...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)

                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=timeout,
                            phrase_time_limit=phrase_time_limit
                        )

                        print(Fore.LIGHTYELLOW_EX + "🧠 Recognizing...")

                        raw_text = ""
                        for lang in ("en-IN", "en-US", "hi-IN"):
                            try:
                                raw_text = self.recognizer.recognize_google(
                                    audio,
                                    language=lang
                                ).lower()
                                if raw_text:
                                    break
                            except sr.UnknownValueError:
                                continue

                        if not raw_text:
                            self._failures += 1
                            if self._failures >= 3:
                                self._failures = 0
                                self._reset_recognizer()
                            return ""

                        english = self._to_english(raw_text)
                        print(Fore.BLUE + f"🎧 Heard: {english}")
                        self._failures = 0
                        return english.strip()

                    except sr.WaitTimeoutError:
                        print(Fore.RED + "⏱ Listening timeout")
                        self._failures += 1
                        return ""

                    except sr.UnknownValueError:
                        print(Fore.RED + "❓ Could not understand audio")
                        self._failures += 1
                        attempts += 1
                        continue

                    except sr.RequestError as e:
                        print(Fore.RED + f"🌐 Speech API error: {e}")
                        self._failures += 1
                        return ""
            except OSError as e:
                print(Fore.RED + f"🎤 Microphone error: {e}")
                return "__MIC_BUSY__"
            except Exception:
                attempts += 1
                continue

        return ""
