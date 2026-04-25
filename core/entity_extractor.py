"""Layered entity extractor.

Slots are filled in this order; first hit wins per slot:

    1. Regex layer     — time, url, number, expression
    2. Gazetteer layer — app_name from data/entities.json
    3. spaCy NER       — person, date, time (optional; if spaCy not installed,
                          this layer is skipped silently)
    4. Residual span   — for free-form slots (query, content, expression,
                          message, person), strip the intent's trigger words
                          and the spans already consumed by earlier layers;
                          what remains becomes the slot value

Only slots listed in `required_entities` for the active intent are populated —
we don't waste cycles on slots the intent doesn't need.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

log = logging.getLogger(__name__)

# ---- Regex layer ------------------------------------------------------ #

_TIME_RE = re.compile(
    r"\b("
    r"\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.|baje|baj)"
    r"(?:\s+(?:subah|shaam|raat|dopahar|morning|afternoon|evening|night))?"
    r"|"
    r"(?:subah|shaam|raat|dopahar|morning|afternoon|evening|night)\s+"
    r"\d{1,2}(?:[:.]\d{2})?(?:\s*(?:am|pm|baje|baj))?"
    r")\b",
    re.IGNORECASE,
)

_URL_RE = re.compile(
    r"\b("
    r"(?:https?://)?[a-z0-9][a-z0-9\-]*"
    r"\.(?:com|in|net|org|io|co|gov|edu|ai|dev|xyz|app|me)"
    r"(?:/[^\s]*)?"
    r")\b",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"\b\d+\b")

# Math expression: at least one operator between numbers
_EXPRESSION_RE = re.compile(r"([\d.]+(?:\s*[+\-*/x×]\s*[\d.]+)+)")

# "with X" / "X ke saath" — name follows. Lookahead bounds the name span
# at common time/date markers so we don't slurp the rest of the sentence.
_PERSON_WITH_RE = re.compile(
    r"\b(?:with|ke\s+saath|ke\s+sath)\s+"
    r"([A-Za-z][\w]{1,20}(?:\s+[A-Za-z][\w]{1,20})?)"
    r"(?=\s+(?:at|pe|par|baje|on|kal|aaj|today|tomorrow|ko|ke)\b|$|[.,!?])",
    re.IGNORECASE,
)

_PUNCT_STRIP_RE = re.compile(r"[^\w\s+\-.:/%]")
_WS_RE = re.compile(r"\s+")


# ---- Per-intent residual configuration ------------------------------- #
# After all earlier layers run, whatever slot of the intent is still empty
# AND is listed here will receive the residual span (cleaned-up leftovers).

INTENT_RESIDUAL_SLOT: dict[str, str] = {
    "search_web": "query",
    "play_youtube": "query",
    "create_note": "content",
    "calculate": "expression",
    "open_website": "url",
    "set_reminder": "message",
    "schedule_meeting": "person",
}

# Per-intent trigger words to strip when computing the residual.
# Lowercase, single-token. Generous coverage of common Hinglish forms.
INTENT_TRIGGER_WORDS: dict[str, set[str]] = {
    "search_web": {
        "google", "search", "karo", "kar", "kardo", "internet", "pe", "par",
        "dhundo", "dhund", "dhundna", "online", "web", "browser", "mein", "me",
        "ke", "ko",
    },
    "play_youtube": {
        "youtube", "yt", "pe", "par", "chalao", "chala", "play", "video",
        "dekho", "dekhna", "dekh", "do", "search", "karo", "kar", "open",
        "watch", "ek", "ke", "ko", "mein",
    },
    "create_note": {
        "note", "likh", "likho", "save", "do", "karo", "kar", "banao", "bana",
        "create", "write", "down", "yeh", "ek", "lo", "kardo",
    },
    "calculate": {
        "calculate", "calculation", "karo", "kar", "compute", "do", "the",
        "math", "solve", "answer", "batao", "result", "kya", "hoga", "iska",
        "kitna", "ka",
    },
    "open_website": {
        "website", "open", "karo", "kar", "url", "browser", "mein", "kholo",
        "khol", "site", "page", "go", "to", "visit", "webpage", "link", "do",
    },
    "set_reminder": {
        "reminder", "set", "karo", "kar", "alarm", "lagao", "laga", "mujhe",
        "yaad", "dilao", "dila", "dilana", "remind", "me", "notification",
        "schedule", "pe", "par", "ek", "ke", "liye", "ko", "rakh", "rakho",
        "rakhna",
    },
    "schedule_meeting": {
        "meeting", "schedule", "karo", "kar", "book", "fix", "appointment",
        "lelo", "lagao", "ek", "organize", "set", "call", "arrange",
        "baithak", "kardo", "do",
    },
}


class EntityExtractor:
    """Public surface: ``extract(text, intent) -> {slot_name: value}``."""

    def __init__(self, entities_path: str, intents_path: str):
        self.entities_path = entities_path
        self.intents_path = intents_path
        self._load_gazetteer()
        self._load_intents()
        self._init_spacy()

    def _load_gazetteer(self) -> None:
        with open(self.entities_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.app_aliases: dict[str, list[str]] = data.get("app_name", {})

    def _load_intents(self) -> None:
        with open(self.intents_path, "r", encoding="utf-8") as f:
            self.intents: dict = json.load(f)

    def _init_spacy(self) -> None:
        try:
            import spacy  # type: ignore
            self.nlp = spacy.load("en_core_web_sm")
            log.info("[EntityExtractor] spaCy en_core_web_sm loaded.")
        except Exception as e:
            self.nlp = None
            log.info(
                f"[EntityExtractor] spaCy NER unavailable ({e.__class__.__name__}). "
                "Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )

    # ------------------------------------------------------------------ #
    #  Layer 1 — Regex                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _re_match(pattern: re.Pattern, text: str) -> Optional[tuple[str, tuple[int, int]]]:
        m = pattern.search(text)
        if not m:
            return None
        return (m.group(1).strip() if m.lastindex else m.group(0).strip(), m.span())

    # ------------------------------------------------------------------ #
    #  Layer 2 — Gazetteer                                                #
    # ------------------------------------------------------------------ #
    def _extract_app(self, text: str) -> Optional[tuple[str, tuple[int, int]]]:
        text_l = text.lower()
        # Sort aliases longest-first so "google chrome" wins over "chrome"
        best: Optional[tuple[str, tuple[int, int], int]] = None
        for canonical, aliases in self.app_aliases.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = r"\b" + re.escape(alias.lower()) + r"\b"
                m = re.search(pattern, text_l)
                if m and (best is None or len(alias) > best[2]):
                    best = (canonical, m.span(), len(alias))
                    break  # next canonical
        if best is None:
            return None
        return best[0], best[1]

    # ------------------------------------------------------------------ #
    #  Layer 3 — spaCy NER (optional)                                     #
    # ------------------------------------------------------------------ #
    def _extract_ner(self, text: str) -> dict[str, tuple[str, tuple[int, int]]]:
        if not self.nlp:
            return {}
        out: dict[str, tuple[str, tuple[int, int]]] = {}
        try:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "DATE", "TIME") and ent.label_ not in out:
                    out[ent.label_] = (ent.text, (ent.start_char, ent.end_char))
        except Exception as e:
            log.warning(f"[EntityExtractor] spaCy parse failed: {e}")
        return out

    # ------------------------------------------------------------------ #
    #  Layer 4 — Residual span                                            #
    # ------------------------------------------------------------------ #
    def _extract_residual(
        self, text: str, intent: str, used_spans: list[tuple[int, int]],
    ) -> Optional[str]:
        masked = list(text)
        for start, end in used_spans:
            for i in range(max(0, start), min(end, len(masked))):
                masked[i] = " "
        s = "".join(masked)
        s = _PUNCT_STRIP_RE.sub(" ", s).lower()
        s = _WS_RE.sub(" ", s).strip()

        triggers = INTENT_TRIGGER_WORDS.get(intent, set())
        tokens = [t for t in s.split() if t and t not in triggers]
        residual = " ".join(tokens).strip()
        return residual or None

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #
    def extract(self, text: str, intent: str) -> dict[str, str]:
        if not text:
            return {}
        intent_cfg = self.intents.get(intent, {})
        required = set(intent_cfg.get("required_entities", []))
        if not required:
            return {}

        out: dict[str, str] = {}
        used_spans: list[tuple[int, int]] = []

        # Layer 1 — regex (only for slots the intent needs)
        if "time" in required:
            r = self._re_match(_TIME_RE, text)
            if r:
                out["time"] = r[0]; used_spans.append(r[1])
        if "url" in required:
            r = self._re_match(_URL_RE, text)
            if r:
                url = r[0]
                if not url.lower().startswith(("http://", "https://")):
                    url = "https://" + url
                out["url"] = url; used_spans.append(r[1])
        if "expression" in required:
            r = self._re_match(_EXPRESSION_RE, text)
            if r:
                out["expression"] = r[0]; used_spans.append(r[1])
        if "number" in required:
            r = self._re_match(_NUMBER_RE, text)
            if r:
                out["number"] = r[0]; used_spans.append(r[1])

        # Layer 2 — gazetteer
        if "app_name" in required:
            r = self._extract_app(text)
            if r:
                out["app_name"] = r[0]; used_spans.append(r[1])

        # Layer 3a — "with X" person shortcut (works without spaCy)
        if "person" in required and "person" not in out:
            m = _PERSON_WITH_RE.search(text)
            if m:
                out["person"] = m.group(1).strip()
                used_spans.append(m.span(1))

        # Layer 3b — spaCy NER
        if self.nlp:
            ner = self._extract_ner(text)
            if "person" in required and "person" not in out and "PERSON" in ner:
                v, sp = ner["PERSON"]
                out["person"] = v; used_spans.append(sp)
            if "time" in required and "time" not in out and "TIME" in ner:
                v, sp = ner["TIME"]
                out["time"] = v; used_spans.append(sp)
            if "date" in required and "date" not in out and "DATE" in ner:
                v, sp = ner["DATE"]
                out["date"] = v; used_spans.append(sp)

        # Layer 4 — residual span fills the intent's free-form slot
        residual_slot = INTENT_RESIDUAL_SLOT.get(intent)
        if residual_slot and residual_slot in required and residual_slot not in out:
            r = self._extract_residual(text, intent, used_spans)
            if r:
                out[residual_slot] = r

        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ex = EntityExtractor(
        entities_path=os.path.join(_here, "data", "entities.json"),
        intents_path=os.path.join(_here, "data", "intents.json"),
    )
    cases = [
        ("youtube pe arijit ka latest gaana chala do", "play_youtube"),
        ("5 baje shaam ko milk lena yaad dilana", "set_reminder"),
        ("chrome kholo", "open_app"),
        ("google chrome open karo", "open_app"),
        ("https://github.com/foo kholo", "open_website"),
        ("github.com kholo", "open_website"),
        ("12 + 7 * 3 calculate karo", "calculate"),
        ("with shivang at 5 pm meeting lagao", "schedule_meeting"),
        ("note kar do meeting at 6 pm", "create_note"),
        ("python tutorial google pe search karo", "search_web"),
        ("weather batao", "get_weather"),
    ]
    for text, intent in cases:
        out = ex.extract(text, intent)
        print(f"  {text!r:55s} [{intent:18s}] -> {out}")
