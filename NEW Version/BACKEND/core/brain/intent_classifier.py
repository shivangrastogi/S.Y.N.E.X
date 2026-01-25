# BACKEND/core/brain/intent_classifier.py

import json
import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_DIR = os.path.join(BACKEND_ROOT, "DATA", "models", "intent_xlm_roberta_1")

class IntentClassifier:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(IntentClassifier, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        if not os.path.isdir(MODEL_DIR):
            raise RuntimeError(
                f"Intent model folder not found: {MODEL_DIR}. "
                "Please ensure models are available."
            )

        label_map_path = os.path.join(MODEL_DIR, "label_map.json")
        if not os.path.isfile(label_map_path):
            raise RuntimeError(
                f"Label map not found: {label_map_path}."
            )

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_DIR,
            use_fast=False,
            fix_mistral_regex=True,
            local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_DIR,
            local_files_only=True
        )
        self.model.eval()

        with open(label_map_path, "r", encoding="utf-8") as f:
            self.label_map = json.load(f)

        self.id_to_label = {v: k for k, v in self.label_map.items()}

    def predict(self, text: str):
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True
        )

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=1)
        confidence, pred = torch.max(probs, dim=1)

        return self.id_to_label[pred.item()], confidence.item()
