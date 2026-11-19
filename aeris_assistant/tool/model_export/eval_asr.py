"""Transcribe the test set with several on-device models; dump transcripts + timing."""
import json, os, sys, time

import numpy as np
import sherpa_onnx
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
M = sys.argv[1]   # models dir
T = sys.argv[2]   # testset dir
OUT = sys.argv[3]
items = json.load(open(os.path.join(T, "index.json")))


def whisper(size, lang, int8=True):
    d = os.path.join(M, f"sherpa-onnx-whisper-{size}")
    q = ".int8" if int8 else ""
    return sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=f"{d}/{size}-encoder{q}.onnx",
        decoder=f"{d}/{size}-decoder{q}.onnx",
        tokens=f"{d}/{size}-tokens.txt",
        language=lang, task="transcribe", num_threads=2)


def moonshine():
    d = os.path.join(M, "sherpa-onnx-moonshine-tiny-en-quantized-2026-02-27")
    files = os.listdir(d)
    print("moonshine files:", files)
    pick = lambda k: os.path.join(d, next(f for f in files if f.startswith(k)))
    kw = dict(tokens=pick("tokens"), num_threads=2)
    if any(f.startswith("encoder_model") for f in files):  # v2 layout
        return sherpa_onnx.OfflineRecognizer.from_moonshine_v2(
            encoder=pick("encoder_model"), decoder=pick("decoder_model_merged"), **kw)
    return sherpa_onnx.OfflineRecognizer.from_moonshine(
        preprocessor=pick("preprocess"), encoder=pick("encode"),
        uncached_decoder=pick("uncached_decode"), cached_decoder=pick("cached_decode"), **kw)


CONFIGS = {
    "whisper-tiny-auto": lambda: whisper("tiny", ""),
    "whisper-tiny-en": lambda: whisper("tiny", "en"),
    "whisper-base-auto": lambda: whisper("base", ""),
    "whisper-base-en": lambda: whisper("base", "en"),
    "whisper-base-hi": lambda: whisper("base", "hi"),
    "whisper-tiny-hi": lambda: whisper("tiny", "hi"),
    "moonshine-tiny-en": moonshine,
    "swift-int8-en": lambda: whisper("hinglish-swift", "en"),
    "swift-int8g-en": lambda: whisper("hinglish-g", "en"),
    "swift-int8-auto": lambda: whisper("hinglish-swift", ""),
}
only = sys.argv[4].split(",") if len(sys.argv) > 4 else list(CONFIGS)
results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
for name in only:
    try:
        rec = CONFIGS[name]()
    except Exception as e:
        print(name, "FAILED to load:", e)
        continue
    rows, audio_s, t0 = [], 0.0, time.time()
    for it in items:
        x, sr = sf.read(os.path.join(T, it["file"]), dtype="float32")
        audio_s += len(x) / sr
        s = rec.create_stream()
        s.accept_waveform(sr, x)
        rec.decode_stream(s)
        rows.append({"ref": it["text"], "hyp": s.result.text.strip(), "voice": it["voice"]})
    el = time.time() - t0
    results[name] = {"rtf": el / audio_s, "rows": rows}
    print(f"{name:20s} RTF={el / audio_s:.3f}  e.g. {rows[0]['hyp']!r} | {rows[4]['hyp']!r}")
json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
