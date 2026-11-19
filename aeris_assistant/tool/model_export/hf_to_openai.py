"""Convert Oriserve/Whisper-Hindi2Hinglish-Swift (HF) → OpenAI-whisper checkpoint,
using the key map the authors ship (convert_hf2openai.json)."""
import glob, json, re, sys

import torch
from safetensors.torch import load_file

snap = glob.glob(sys.argv[1] + "/models--Oriserve--Whisper-Hindi2Hinglish-Swift/snapshots/*")[0]
out = sys.argv[2]
cfg = json.load(open(f"{snap}/config.json"))
rules = json.load(open(f"{snap}/convert_hf2openai.json"))
sd = load_file(f"{snap}/model.safetensors")

new = {}
unmapped = []
for k, v in sd.items():
    k2 = k[len("model."):] if k.startswith("model.") else k
    if k2 == "proj_out.weight":
        continue  # tied to the token embedding in OpenAI's layout
    for pat, rep in rules.items():
        if re.match(pat, k2):
            k2 = re.sub(pat, rep, k2)
            break
    else:
        unmapped.append(k2)
    new[k2] = v
print("unmapped:", unmapped)

dims = dict(
    n_mels=cfg["num_mel_bins"], n_audio_ctx=cfg["max_source_positions"], n_audio_state=cfg["d_model"],
    n_audio_head=cfg["encoder_attention_heads"], n_audio_layer=cfg["encoder_layers"],
    n_vocab=cfg["vocab_size"], n_text_ctx=cfg["max_target_positions"], n_text_state=cfg["d_model"],
    n_text_head=cfg["decoder_attention_heads"], n_text_layer=cfg["decoder_layers"],
)
print("dims:", dims)

import whisper
from whisper.model import ModelDimensions, Whisper

m = Whisper(ModelDimensions(**dims))
missing, unexpected = m.load_state_dict(new, strict=False)
print("missing:", missing)
print("unexpected:", unexpected)
torch.save({"dims": dims, "model_state_dict": m.state_dict()}, out)
print("saved", out)
