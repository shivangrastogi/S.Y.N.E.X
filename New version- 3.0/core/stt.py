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

    def listen(self):
        """
        Listens and returns transcribed text.
        Tries Google SR (en-IN) first for Hinglish support, 
        falls back to Vosk if offline.
        """
        with self.microphone as source:
            print("Listening...")
            try:
                # 1. Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 2. Listen for audio
                audio_data = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
                
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

if __name__ == "__main__":
    # Quick test
    stt = STT()
    print("Speak now (Hinglish supported)...")
    print(f"Recognized: {stt.listen()}")
