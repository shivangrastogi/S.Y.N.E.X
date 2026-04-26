"""Sentiment classifier.

v1 wraps VADER (pure-Python, lexicon-based) and extends its lexicon with
common Hinglish positive/negative terms. Works decently on Romanized Hindi.

Upgrade path documented for C3+: swap `_classify` to a multilingual transformer
(e.g. `cardiffnlp/twitter-xlm-roberta-base-sentiment`) for true Hindi quality.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

NEUTRAL_BAND = 0.15


@dataclass
class Sentiment:
    label: str   # "positive" | "neutral" | "negative"
    score: float # -1.0 to 1.0 (compound)


# Hinglish booster lexicon — added on top of VADER's English vocabulary.
# Values are roughly compatible with VADER's own scale (-4 to +4).
_HINGLISH_LEX: dict[str, float] = {
    # Positive
    "accha": 2.0, "achha": 2.0, "acha": 1.8,
    "bahut": 0.5, "bohot": 0.5, "bhot": 0.5,
    "shaandar": 3.0, "shandar": 3.0,
    "shukriya": 2.0, "dhanyavaad": 2.0, "dhanyawaad": 2.0,
    "wah": 2.0, "wahh": 2.0,
    "behtareen": 3.0, "behtar": 1.5,
    "mast": 2.5, "ekdum": 1.0,
    "zabardast": 3.0, "kamaal": 2.5,
    "perfect": 2.5, "thik": 0.8, "theek": 0.8,
    "khush": 2.0, "khushi": 2.0,
    "pyaar": 2.0, "pyar": 2.0,
    # Negative
    "bakwaas": -3.0, "bakwas": -3.0,
    "ganda": -2.5, "gandi": -2.5, "gande": -2.5,
    "bekaar": -2.5, "bekar": -2.5,
    "kharab": -2.0, "kharaab": -2.0,
    "galat": -2.0, "galati": -1.5,
    "bura": -2.0, "buri": -2.0,
    "naraz": -2.5, "narazgi": -2.5,
    "frustrated": -2.5, "frustrate": -2.5,
    "irritate": -2.5, "irritated": -2.5,
    "boring": -2.0, "bor": -1.5,
    "dukhi": -2.5, "dukh": -2.0,
    "pareshan": -2.0,
    "nahi": -0.3,  # mild — "nahi" alone isn't strongly negative, but tilts
}


class SentimentAnalyzer:
    def __init__(self):
        self._vader = None
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._vader = SentimentIntensityAnalyzer()
            self._vader.lexicon.update(_HINGLISH_LEX)
            log.info("[Sentiment] VADER loaded with Hinglish lexicon extension.")
        except ImportError:
            log.info(
                "[Sentiment] vaderSentiment not installed; using fallback heuristic. "
                "Install with: pip install vaderSentiment"
            )

    def classify(self, text: str) -> Sentiment:
        if not text or not text.strip():
            return Sentiment(label="neutral", score=0.0)

        if self._vader is not None:
            score = float(self._vader.polarity_scores(text)["compound"])
        else:
            score = self._heuristic(text)

        if score >= NEUTRAL_BAND:
            label = "positive"
        elif score <= -NEUTRAL_BAND:
            label = "negative"
        else:
            label = "neutral"
        return Sentiment(label=label, score=round(score, 4))

    @staticmethod
    def _heuristic(text: str) -> float:
        """Tiny lexicon-based fallback when VADER isn't installed."""
        pos_words = {"good", "great", "thanks", "awesome", "love", "amazing",
                     "accha", "shukriya", "wah", "mast", "behtareen", "perfect",
                     "khush", "shaandar", "zabardast"}
        neg_words = {"bad", "terrible", "hate", "worst", "wrong", "stupid",
                     "bakwaas", "ganda", "bekaar", "galat", "bura", "kharab",
                     "naraz", "frustrated", "boring"}
        toks = text.lower().split()
        p = sum(1 for t in toks if t in pos_words)
        n = sum(1 for t in toks if t in neg_words)
        if p + n == 0:
            return 0.0
        return round((p - n) / (p + n), 4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = SentimentAnalyzer()
    cases = [
        "thank you yaar bahut accha kaam kiya",
        "yeh kya bakwaas hai",
        "chrome kholo",
        "this is amazing",
        "i hate this so much",
        "okay theek hai",
        "mast kaam kar rahe ho",
        "kuch samajh nahi aaya",
        "bahut kharab response tha",
        "shukriya bhai",
    ]
    for t in cases:
        r = s.classify(t)
        print(f"  {t!r:50s} -> {r.label:10s} ({r.score:+.3f})")
