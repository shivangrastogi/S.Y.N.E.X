"""Make a Hinglish/English command test set as 16 kHz mono WAVs (2 Indian voices)."""
import asyncio, io, json, os, sys

import edge_tts
import numpy as np
import soundfile as sf

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

COMMANDS = [
    "kal subah 6:30 ka alarm laga do",
    "10 minute ka timer lagao",
    "torch on karo",
    "torch band karo",
    "Ravi ko WhatsApp karo ki main late hoon",
    "Mummy ko call karo",
    "YouTube kholo",
    "battery kitni hai",
    "time kya hua",
    "aaj ki date kya hai",
    "12 into 8",
    "yaad rakho ki meri car B2 mein parked hai",
    "meri car kahan park ki thi",
    "good morning",
    "bas",
    "set an alarm for 7 am tomorrow",
    "what time is it",
    "open WhatsApp",
    "call Ravi",
    "shaam 7 baje ka alarm",
    "Papa ko message bhejo ki 5 minute mein aa raha hoon",
    "search best biryani near me",
    "kaise ho",
    "500 ka 20 percent",
]
VOICES = ["en-IN-NeerjaNeural", "en-IN-PrabhatNeural"]


def resample(x, sr, to=16000):
    if sr == to:
        return x
    n = int(round(len(x) * to / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


async def main():
    items = []
    for vi, v in enumerate(VOICES):
        for i, c in enumerate(COMMANDS):
            buf = b""
            async for ch in edge_tts.Communicate(c, v).stream():
                if ch["type"] == "audio":
                    buf += ch["data"]
            x, sr = sf.read(io.BytesIO(buf), dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            x = resample(x, sr)
            name = f"{vi}_{i:02d}.wav"
            sf.write(os.path.join(OUT, name), x, 16000)
            items.append({"file": name, "text": c, "voice": v})
    json.dump(items, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print("made", len(items))


asyncio.run(main())
