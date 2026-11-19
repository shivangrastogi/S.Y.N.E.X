"""Hinglish voice bake-off — every candidate reads the SAME ~20 s paragraph.

Run inside the separate lab environment (never AERIS's own Python):
    C:\\Users\\Shivang\\tts_lab\\.venv\\Scripts\\python tool\\voice_lab\\hinglish_samples.py supertonic kokoro

Writes WAVs to ../voice_samples_hinglish/ (outside build/, which `flutter clean`
wipes). Each engine gets the script it handles best: Roman Hinglish where the
model reads it, Devanagari (with English words transliterated) where it only
reads Hindi script — the file name says which.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.normpath(os.path.join(APP, "..", "voice_samples_hinglish"))

# What AERIS really says: alarm, reminder, weather, a missed call, an offer.
TEXT_ROMAN = (
    "Namaste Shivang! Main AERIS hoon, aapka personal assistant. "
    "Kal subah saat baje ka alarm laga diya hai, aur das baje wali meeting ka reminder bhi set kar diya. "
    "Waise aaj bahar kaafi garmi hai, toh paani peete rehna. "
    "Ravi ka call aaya tha, maine bata diya ki aap thodi der mein call back karoge. "
    "Aur kuch chahiye toh bas bol dena."
)
TEXT_DEVANAGARI = (
    "नमस्ते शिवांग! मैं एरिस हूँ, आपका पर्सनल असिस्टेंट। "
    "कल सुबह सात बजे का अलार्म लगा दिया है, और दस बजे वाली मीटिंग का रिमाइंडर भी सेट कर दिया। "
    "वैसे आज बाहर काफ़ी गर्मी है, तो पानी पीते रहना। "
    "रवि का कॉल आया था, मैंने बता दिया कि आप थोड़ी देर में कॉल बैक करोगे। "
    "और कुछ चाहिए तो बस बोल देना।"
)


def save(name: str, audio: np.ndarray, rate: int, made_in: float) -> None:
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}.wav")
    sf.write(path, np.asarray(audio, dtype=np.float32), rate)
    secs = len(audio) / rate
    print(f"  {name}.wav  {secs:5.1f} s of speech, made in {made_in:5.1f} s on this laptop (CPU)")


def supertonic() -> None:
    """AERIS's current voice (male 9, 1.0x, 8 steps, 'en' mode, Devanagari) — the reference."""
    import sherpa_onnx as so

    tts_dir = os.path.join(APP, "assets", "models", "tts")
    f = lambda n: os.path.join(tts_dir, n)
    tts = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
        supertonic=so.OfflineTtsSupertonicModelConfig(
            duration_predictor=f("duration_predictor.int8.onnx"), text_encoder=f("text_encoder.int8.onnx"),
            vector_estimator=f("vector_estimator.int8.onnx"), vocoder=f("vocoder.int8.onnx"),
            tts_json=f("tts.json"), unicode_indexer=f("unicode_indexer.bin"), voice_style=f("voice.bin")),
        num_threads=4)))
    config = so.GenerationConfig()
    config.sid, config.speed, config.num_steps = 9, 1.0, 8
    config.extra = {"lang": "en"}
    start = time.time()
    audio = tts.generate(TEXT_DEVANAGARI, config)
    save("00_CURRENT_Supertonic_male9_devanagari", np.array(audio.samples), audio.sample_rate, time.time() - start)


def kokoro() -> None:
    """Kokoro-82M Hindi voices (hm_ = Hindi male, hf_ = Hindi female)."""
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="h", repo_id="hexgrad/Kokoro-82M")
    for voice in ["hm_omega", "hm_psi", "hf_alpha", "hf_beta"]:
        start = time.time()
        chunks = [audio.numpy() for _, _, audio in pipeline(TEXT_DEVANAGARI, voice=voice, speed=1.0)]
        save(f"kokoro_{voice}_devanagari", np.concatenate(chunks), 24000, time.time() - start)


def parler() -> None:
    """AI4Bharat Indic Parler-TTS (0.9B, Apache-2.0): named Indian speakers,
    voice described in words. Slow on a CPU — this is a quality reference."""
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer

    model_id = "ai4bharat/indic-parler-tts"
    model = ParlerTTSForConditionalGeneration.from_pretrained(model_id)
    text_tokenizer = AutoTokenizer.from_pretrained(model_id)
    description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)
    for speaker in ["Rohit", "Aman", "Divya"]:
        description = (f"{speaker} speaks at a moderate pace with a clear, warm and friendly tone. "
                       "The recording is very clear and close-sounding, with no background noise.")
        start = time.time()
        with torch.no_grad():
            audio = model.generate(
                input_ids=description_tokenizer(description, return_tensors="pt").input_ids,
                prompt_input_ids=text_tokenizer(TEXT_DEVANAGARI, return_tensors="pt").input_ids,
            )
        save(f"parler_{speaker}_devanagari", audio.cpu().numpy().squeeze(), model.config.sampling_rate, time.time() - start)


ENGINES = {"supertonic": supertonic, "kokoro": kokoro, "parler": parler}

if __name__ == "__main__":
    for engine in sys.argv[1:] or ENGINES:
        print(f"── {engine}")
        try:
            ENGINES[engine]()
        except Exception as error:  # one engine failing must not stop the others
            print(f"  FAILED: {error!r}")
    print(f"\nSamples in {OUT}")
