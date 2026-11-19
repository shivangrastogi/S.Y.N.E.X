# On-device models: how they were made and measured

All speech runs inside the app through sherpa-onnx (Apache-2.0). There are no Google or Microsoft services on the default path.

| Asset | What | Source / licence | Size |
|---|---|---|---|
| `assets/models/asr/*` | **Hinglish speech-to-text**: Oriserve `Whisper-Hindi2Hinglish-Swift` (a Whisper-base fine-tune that writes Hinglish in Latin script), converted to sherpa-onnx int8 | HF `Oriserve/Whisper-Hindi2Hinglish-Swift`, **Apache-2.0** (base: OpenAI Whisper, MIT) | 160 MB |
| `assets/models/vad/silero_vad.onnx` | Voice activity detection (when you stop talking) | Silero VAD, MIT | 0.6 MB |
| `assets/models/tts/*` | **JARVIS voice**: Supertonic 3 int8, male voice **sid 9**, speed 1.35, num_steps 6, `lang=hi` with Devanagari input (or `en`) | sherpa-onnx `sherpa-onnx-supertonic-3-tts-int8-2026-05-11`, **MIT** | 139 MB |

## Measured (2026-11-16)

Test set: 24 real commands × 2 Indian voices (Neerja, Prabhat) = 48 clips (`gen_testset.py`). The score counts **correct AERIS actions**, so the router has to do the same thing it does with the perfect text (`tool/eval_transcripts.dart`):

| Model | Correct actions | RTF (PC, 2 threads) |
|---|---|---|
| Whisper tiny (stock) | 16–19 / 48 | 0.10–0.13 |
| Whisper base (stock, auto / hi / en) | 23–27 / 48 | 0.15–0.18 |
| Moonshine tiny (English) | 12 / 48 | 0.03 |
| **Hinglish-Swift int8 (shipped) + `cleanTranscript`** | **45 / 48** | 0.22 |

Stock models often wrote Urdu or Japanese script for Hinglish. Swift writes "Ravi ko WhatsApp karo ki main late hoon" word-perfect.

Voice: Piper Lessac RTF 0.29 on PC, so it's usable on the phone. Kokoro `am_michael` RTF 1.8 was too slow, and was rejected.

Caveat: the test voices are neural Indian voices, not Shivang's real voice. Re-measure with real recordings.

## Rebuild the Hinglish model

Use a throwaway venv, not the desktop py3.10:

```
python -m venv venv && venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu
venv\Scripts\pip install "transformers<5" safetensors openai-whisper onnx onnxruntime huggingface_hub "sherpa-onnx==1.13.4"
# 1. download the HF model (snapshot_download), then
venv\Scripts\python hf_to_openai.py <hf_cache_dir> hinglish-swift-original.pt
# 2. sherpa's export script with two patches (already applied in export-onnx.patched.py):
#    - an extra --model choice "hinglish-swift" that loads ./hinglish-swift-original.pt
#    - torch.onnx.export forced to dynamo=False (torch ≥2.9 defaults to the new exporter)
venv\Scripts\python export-onnx.patched.py --model hinglish-swift
# 3. copy hinglish-swift-{encoder,decoder}.int8.onnx + hinglish-swift-tokens.txt
#    → assets/models/asr/{encoder.int8.onnx, decoder.int8.onnx, tokens.txt}
```

Note: sherpa-onnx **2.x** Python dropped the built-in eSpeak frontend (Piper then fails with "no frontend available"). The app pins **1.13.4**, so test with that version.

## Voice selection (2026-11-16)

These were rejected by ear: Piper Lessac (female), Alan, Ryan, Rohan and Pratham (Hindi), and every pitch-shifted "deep" variant ("I want natural"). Kokoro Hindi and Kitten were too slow (RTF > 1 on PC).

Supertonic 3 has 10 voices. The male ones were identified by measured pitch: sids 4–9, with 9 the deepest at 85 Hz and 6 at 89 Hz. Shivang chose **sid 9 at 1.35×**.

Speed on PC with 4 threads: about 1 s to make a short reply at 6 steps.
