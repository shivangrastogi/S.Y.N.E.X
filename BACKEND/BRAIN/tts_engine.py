# tts_engine.py
import os
import threading
from DATA.TTS_MINIMAL.utils.synthesizer import Synthesizer

class TTSEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSEngine, cls).__new__(cls)
                cls._instance._initialize(*args, **kwargs)
            return cls._instance

    def _initialize(self, base_dir=r"D:\JARVIS_v1.0\BACKEND\DATA\SPEAK MODAL\local_tts_modal", device="cpu"):
        tts_model_path = os.path.join(base_dir, "tts_models--en--ljspeech--fast_pitch", "model_file.pth")
        tts_config_path = os.path.join(base_dir, "tts_models--en--ljspeech--fast_pitch", "config.json")
        vocoder_model_path = os.path.join(base_dir, "vocoder_models--en--ljspeech--hifigan_v2", "model_file.pth")
        vocoder_config_path = os.path.join(base_dir, "vocoder_models--en--ljspeech--hifigan_v2", "config.json")

        # you may want to expose device selection here (cuda vs cpu)
        self.synthesizer = Synthesizer(
            tts_checkpoint=tts_model_path,
            tts_config_path=tts_config_path,
            vocoder_checkpoint=vocoder_model_path,
            vocoder_config=vocoder_config_path,
            use_cuda=False
        )
        # warm up optionally (small phrase)
        try:
            self.synthesizer.tts("Initializing.")
        except Exception:
            pass

    def synthesize(self, text: str, **kwargs):
        """Generate audio waveform; kwargs can include speed, speaker, etc. depending on model."""
        if not text or not text.strip():
            return None
        return self.synthesizer.tts(text, **kwargs)

    def save(self, wav, output_path: str):
        self.synthesizer.save_wav(wav, output_path)




