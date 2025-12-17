# BRAIN/NLU/NLU_Core.py

import os
import json
import torch
from transformers import XLMRobertaTokenizer, XLMRobertaForSequenceClassification

from CORE.Utils.DataPath import get_model_path
from CORE.Utils.Logger import log_error

# ---------------------------------------------------------
# Model path (your FINAL trained model)
# ---------------------------------------------------------
MODEL_DIR = get_model_path("NLU_MODELS", "intent_xlm_roberta_final")

tokenizer = None
model = None
id2label = None
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model():
    """
    Loads tokenizer, model, and label map safely.
    """
    global tokenizer, model, id2label

    try:
        if not os.path.exists(MODEL_DIR):
            raise FileNotFoundError(f"Model directory not found: {MODEL_DIR}")

        # Load tokenizer
        tokenizer = XLMRobertaTokenizer.from_pretrained(MODEL_DIR)

        # Load model
        model = XLMRobertaForSequenceClassification.from_pretrained(MODEL_DIR)
        model.to(device)
        model.eval()

        # Load label map
        label_map_path = os.path.join(MODEL_DIR, "label_map.json")
        if not os.path.exists(label_map_path):
            raise FileNotFoundError("label_map.json not found in model directory")

        with open(label_map_path, "r", encoding="utf-8") as f:
            label_map = json.load(f)

        # Reverse mapping: id -> label
        id2label = {int(v): k for k, v in label_map.items()}

        print("✅ JARVIS Brain 1 (XLM-RoBERTa NLU) loaded successfully.")

    except Exception as e:
        log_error(f"NLU Initialization failed: {e}")
        print(f"❌ FATAL ERROR loading NLU model: {e}")
        tokenizer = None
        model = None
        id2label = None


# Load model immediately on import
_load_model()


# ---------------------------------------------------------
# Public API used by Jarvis
# ---------------------------------------------------------
def get_intent(command: str):
    """
    Predicts intent from user command.

    Returns:
        intent (str | None)
        entities (dict)   -> kept for compatibility (empty for now)
        confidence (float)
    """

    if not command or not model or not tokenizer or not id2label:
        return None, {}, 0.0

    try:
        inputs = tokenizer(
            command,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=64
        )

        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        logits = outputs.logits
        probs = torch.softmax(logits, dim=1)

        confidence, pred_id = torch.max(probs, dim=1)

        intent = id2label.get(pred_id.item(), None)

        return intent, {}, float(confidence.item())

    except Exception as e:
        log_error(f"NLU inference error: {e}")
        return intent, {}, 0.0
