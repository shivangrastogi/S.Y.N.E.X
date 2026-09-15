import os
import json
import queue
import time
import threading
import speech_recognition as sr
from vosk import Model as VoskModel, KaldiRecognizer

class STT:
    def __init__(self, model_path="data/models/vosk-model"):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.energy_threshold = 1000
        self.recognizer.pause_threshold = 0.8
        self.microphone = sr.Microphone()
        
        self.model_path = model_path
        self.vosk_model = None
        
        # Load Vosk in background
        threading.Thread(target=self._init_vosk, daemon=True).start()

    def _init_vosk(self):
        if os.path.exists(self.model_path):
            try:
                self.vosk_model = VoskModel(self.model_path)
            except:
                pass

    def listen(self, prefer_offline: bool = False):
        """
        Listens and returns transcribed text.
        Tries Google SR (en-IN) first for Hinglish support,
        falls back to Vosk if offline.

        ``prefer_offline=True`` flips that order and transcribes locally
        first. The voice service passes it while AERIS is SLEEPING: the mic
        is still open, but the room's audio should not be shipped to Google
        merely to check whether anyone said "wake up".

        It is a *preference*, not a guarantee — if Vosk returns nothing we
        still fall through to Google, exactly as
        ``ContinuousVoiceEngine._transcribe`` has always done, so a wake word
        isn't lost when the offline model under-recognises. That trade is the
        tuned voice stack's, and this mirrors it rather than inventing a
        stricter rule.
        """
        with self.microphone as source:
            print("Listening...")
            try:
                # 1. Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 2. Listen for audio
                audio_data = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)

                # 2b. Asleep: try the local model first (see docstring).
                if prefer_offline and self.vosk_model:
                    local = self._transcribe_offline(audio_data)
                    if local:
                        return local

                # 3. Try Online Transcription (Hinglish)
                try:
                    text = self.recognizer.recognize_google(audio_data, language="en-IN").lower()
                    return text
                except sr.UnknownValueError:
                    return ""
                except (sr.RequestError, Exception):
                    # 4. Fallback to Offline Transcription
                    print("Offline mode: Using Vosk...")
                    return self._transcribe_offline(audio_data)

            except sr.WaitTimeoutError:
                return ""
            except Exception as e:
                print(f"STT Error: {e}")
                return ""

    def _transcribe_offline(self, audio_data):
        if not self.vosk_model:
            return ""
        try:
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            rec = KaldiRecognizer(self.vosk_model, 16000)
            rec.AcceptWaveform(raw_data)
            res = json.loads(rec.FinalResult())
            return res.get("text", "").lower()
        except:
            return ""

    # ------------------------------------------------------------------ #
    #  Streaming mode (Vosk partial results — live transcription)         #
    # ------------------------------------------------------------------ #

    def listen_streaming(self, on_partial=None, on_final=None,
                         max_silence_chunks: int = 8,
                         sample_rate: int = 16000):
        """Stream mic audio through Vosk, firing on_partial/on_final callbacks.

        on_partial(text) — called repeatedly while user speaks
        on_final(text)   — called once when silence is detected, then returns

        Uses the offline Vosk model so it works without internet. Falls back
        to ``listen()`` if the model isn't loaded yet.
        """
        if not self.vosk_model:
            text = self.listen()
            if on_final:
                on_final(text)
            return text

        try:
            import pyaudio
        except ImportError:
            text = self.listen()
            if on_final:
                on_final(text)
            return text

        rec = KaldiRecognizer(self.vosk_model, sample_rate)
        rec.SetWords(True)

        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16, channels=1,
            rate=sample_rate, input=True,
            frames_per_buffer=4000,
        )
        stream.start_stream()

        # Endpointing policy lives in core.vad_stream so it's unit-tested and
        # shared with the voice engine's streaming path.
        from core.vad_stream import Endpointer
        ep = Endpointer(max_silence_chunks=max_silence_chunks)
        final_text = ""
        try:
            while True:
                data = stream.read(4000, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result()).get("text", "")
                    dec = ep.update(res, is_final=True)
                else:
                    res = json.loads(rec.PartialResult()).get("partial", "")
                    dec = ep.update(res)
                    if dec.changed and on_partial:
                        on_partial(dec.text)
                if dec.finalize:
                    final_text = dec.text
                    break
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

        if on_final:
            on_final(final_text)
        return final_text


if __name__ == "__main__":
    # Quick test
    stt = STT()
    print("Speak now (Hinglish supported)...")
    print(f"Recognized: {stt.listen()}")
