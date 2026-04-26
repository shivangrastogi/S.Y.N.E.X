"""Top-K disambiguation prompt + answer routing.

When the brain's top-1 and top-2 predictions are very close in vote share AND
the top-1 is not overwhelmingly confident, asking the user is better than
guessing wrong. This module owns:

    1. The "is this a close call?" decision
    2. The Hinglish prompt text
    3. Parsing the user's answer back to a chosen intent

It does NOT own state (that lives in `state_manager`) or executor wiring
(that lives in `main_engine`).
"""

from __future__ import annotations

from typing import Optional

from core.intent_classifier import Prediction


# Tunables
CLOSE_CALL_DELTA = 0.05         # top-1 minus top-2 must be smaller than this
HIGH_CONFIDENCE_FLOOR = 0.85    # but if top-1 cosine ≥ this, never ask anyway


# Default human-readable names per intent. Override via __init__ for custom.
_DEFAULT_PRETTY = {
    "open_app": "open an app",
    "close_app": "close an app",
    "get_weather": "weather check karna",
    "play_music": "music play karna",
    "stop_music": "music band karna",
    "set_reminder": "reminder set karna",
    "get_time": "time batao",
    "take_screenshot": "screenshot",
    "search_web": "Google search",
    "system_info": "system info",
    "volume_up": "volume badhana",
    "volume_down": "volume kam karna",
    "volume_mute": "mute karna",
    "lock_screen": "screen lock",
    "shutdown_system": "computer band",
    "calculate": "calculation",
    "create_note": "note banana",
    "greet": "greeting",
    "schedule_meeting": "meeting schedule",
    "play_youtube": "YouTube play",
    "open_website": "website kholna",
}


class Disambiguator:
    def __init__(self, intent_pretty_names: Optional[dict] = None):
        self._pretty = dict(_DEFAULT_PRETTY)
        if intent_pretty_names:
            self._pretty.update(intent_pretty_names)

    # ------------------------------------------------------------------ #
    #  Detection                                                          #
    # ------------------------------------------------------------------ #

    def is_close_call(self, pred: Prediction) -> bool:
        """True iff top-1 is not dominant AND top-2 is competitive."""
        if pred.intent is None:
            return False
        if len(pred.top3) < 2:
            return False
        # top3 entries are (intent_name, vote_share)
        top1_share = pred.top3[0][1]
        top2_share = pred.top3[1][1]
        if pred.confidence >= HIGH_CONFIDENCE_FLOOR:
            return False
        return (top1_share - top2_share) < CLOSE_CALL_DELTA

    # ------------------------------------------------------------------ #
    #  Prompt + parse                                                     #
    # ------------------------------------------------------------------ #

    def pretty_name(self, intent_id: str) -> str:
        if intent_id in self._pretty:
            return self._pretty[intent_id]
        return intent_id.replace("_", " ").lower()

    def prompt(self, pred: Prediction) -> str:
        a = self.pretty_name(pred.top3[0][0])
        b = self.pretty_name(pred.top3[1][0])
        return (f"Aap '{a}' karna chahte hain ya '{b}'? "
                f"Pehla bolo ya doosra, ya naam batao.")

    def parse_answer(self, text: str, pred: Prediction) -> Optional[str]:
        """Map a user's disambig reply to one of the candidate intents.

        Recognised forms:
            "1" / "first" / "pehla" / "pehli" / "ek"     → top-1
            "2" / "second" / "doosra" / "dusra" / "do"   → top-2
            "<intent_id>"                                → that intent
            substring of pretty_name                     → that intent
        """
        if not text or not text.strip():
            return None
        t = text.lower().strip()

        if t in {"1", "first", "pehla", "pehli", "ek", "one"}:
            return pred.top3[0][0]
        if t in {"2", "second", "doosra", "dusra", "do", "two"}:
            return pred.top3[1][0]
        if len(pred.top3) >= 3 and t in {"3", "third", "teesra", "tisra", "teen", "three"}:
            return pred.top3[2][0]

        # Match by intent id (substring)
        for intent_id, _ in pred.top3:
            if intent_id in t:
                return intent_id
            pretty = self.pretty_name(intent_id).lower()
            # Match if any non-trivial word from the pretty name appears in user text
            for word in pretty.split():
                if len(word) >= 4 and word in t:
                    return intent_id
        return None


if __name__ == "__main__":
    from core.intent_classifier import Prediction
    d = Disambiguator()

    # Construct synthetic close-call prediction
    pred = Prediction(
        intent="open_app",
        confidence=0.72,
        top3=[("open_app", 0.42), ("close_app", 0.40), ("open_website", 0.18)],
        raw_text="chrome",
        normalized_text="chrome",
    )

    print(f"is_close_call: {d.is_close_call(pred)}")
    print(f"prompt       : {d.prompt(pred)}")

    for ans in ["1", "pehla", "doosra", "open app", "close_app", "no idea"]:
        chosen = d.parse_answer(ans, pred)
        print(f"  answer={ans!r:15s} -> chosen={chosen!r}")

    # Now test a non-close-call (top-1 dominant)
    dominant = Prediction(
        intent="open_app",
        confidence=0.95,
        top3=[("open_app", 0.92), ("close_app", 0.05), ("open_website", 0.03)],
        raw_text="chrome kholo",
        normalized_text="chrome kholo",
    )
    print(f"\ndominant case is_close_call: {d.is_close_call(dominant)}")
