"""Persistent user memory.

Long-term store of facts the user told the assistant about themselves.
JSON-backed, survives restart. Detects natural-language "remember" patterns
and writes automatically.

The brain pipeline calls `detect_and_store(text)` BEFORE intent classification:
if the text matches a memory-setting pattern, the fact is saved and an ack
string is returned (and the rest of the pipeline is skipped for that turn).
This makes "remember"-style commands a higher-priority kind of intent.

Storage shape (`data/user_memory.json`):
    {
      "facts": {
        "name": {"value": "Shivang", "set_at": "...", "source": "user_said"}
      },
      "notes": [
        {"text": "buy milk on tuesdays", "set_at": "..."}
      ],
      "preferences": {
        "language": "hinglish"
      }
    }
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


# Common end-of-name boundary: a name span ends at one of these markers
# so we don't slurp the rest of the sentence into it.
_NAME_BOUNDARY = (
    r"(?=\s+(?:and|aur|please|but|nice|right|ok|haan|hai|to|se|ka|ke|ki)\b"
    r"|$|[.,!?])"
)

# Hindi/English copulas and discourse particles that must NOT be captured as
# part of a name span. Without this, "mera naam shivang hai" greedily captures
# "shivang hai" as a two-word name (the boundary `$` is satisfied at end-of-string).
_NAME_BLOCKLIST = (
    r"(?!(?:hai|tha|thi|hain|hoon|ho|ki|ka|ke|se|to|please|nice|"
    r"right|ok|haan|bhi|bhai|sir|jarvis|aur|and|but)\b)"
)


# (key, regex, kind, ack_template)
#   kind="single"   → save as fact[key] = group(1)
#   kind="favorite" → save as fact[f"favorite_{group(1)}"] = group(2)
#   kind="note"     → append to notes list
#
# Convention: every alternation in the prefix consumes only words; the
# required whitespace before the capture group lives OUTSIDE the alternation
# as a single trailing `\s+`. This avoids the easy bug of one alternative
# eating its trailing space and another not.
_DETECTORS: list[tuple[str, re.Pattern[str], str, str]] = [
    # ---- Name ----
    # Captures up to two name words. The negative-lookahead BLOCKLIST stops
    # the optional second word from eating Hindi copulas like "hai" / "hoon".
    (
        "name",
        re.compile(
            r"(?:my name is|mera naam(?:\s+hai)?|main hoon)\s+"
            + _NAME_BLOCKLIST
            + r"([a-zA-Z][a-zA-Z]{1,20}(?:\s+"
            + _NAME_BLOCKLIST
            + r"[a-zA-Z][a-zA-Z]{1,20})?)"
            + _NAME_BOUNDARY,
            re.IGNORECASE,
        ),
        "single",
        "Got it, {value}. Nice to meet you.",
    ),

    # ---- Location ----
    (
        "location",
        re.compile(
            r"(?:i live in|i'?m from|"
            r"main rehta hoon(?:\s+in)?|main rehti hoon(?:\s+in)?|"
            r"main hoon from)\s+"
            r"([a-zA-Z][a-zA-Z\s]{1,30}?)"
            + _NAME_BOUNDARY,
            re.IGNORECASE,
        ),
        "single",
        "Noted - aap rehte hain {value} mein.",
    ),

    # ---- Employer ----
    (
        "employer",
        re.compile(
            r"(?:i work at|i work for|"
            r"main kaam karta hoon (?:at|in|for)|"
            r"main kaam karti hoon (?:at|in|for))\s+"
            r"([a-zA-Z][\w\s.&'-]{1,40}?)"
            + _NAME_BOUNDARY,
            re.IGNORECASE,
        ),
        "single",
        "Got it - aap kaam karte hain {value} mein.",
    ),

    # ---- Favorite (English-order: "favourite X is Y") ----
    (
        "_favorite",
        re.compile(
            r"(?:my (?:favou?rite|fav)|mera (?:favou?rite|fav))\s+"
            r"(\w+)\s+(?:is|hai)\s+"
            r"([a-zA-Z][\w\s.&'-]{1,40}?)"
            + _NAME_BOUNDARY,
            re.IGNORECASE,
        ),
        "favorite",
        "Cool, aapka favourite {category} {value} hai.",
    ),

    # ---- Favorite (Hinglish-order: "favourite X Y hai") ----
    (
        "_favorite_hinglish",
        re.compile(
            r"mera (?:favou?rite|fav)\s+"
            r"(\w+)\s+"
            r"([a-zA-Z][\w\s.&'-]{1,40}?)"
            r"\s+hai\b",
            re.IGNORECASE,
        ),
        "favorite",
        "Cool, aapka favourite {category} {value} hai.",
    ),

    # ---- Free-form remember ----
    (
        "_note",
        re.compile(
            r"(?:remember (?:that|ki)?|yaad rakho?(?:\s+(?:ki|that))?|"
            r"yaad rakhna(?:\s+(?:ki|that))?)\s+(.{3,200})$",
            re.IGNORECASE,
        ),
        "note",
        "Yaad rakh liya, sir.",
    ),
]


def _titlecase_clean(s: str) -> str:
    """Trim, collapse whitespace, title-case names/locations."""
    s = re.sub(r"\s+", " ", s.strip())
    return s.title()


class UserMemory:
    def __init__(self, path: str):
        self.path = path
        self._data: dict = {"facts": {}, "notes": [], "preferences": {}}
        self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                loaded.setdefault("facts", {})
                loaded.setdefault("notes", [])
                loaded.setdefault("preferences", {})
                self._data = loaded
        except Exception as e:
            log.warning(f"[Memory] Load failed ({e}); starting fresh.")

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def get(self, key: str) -> Optional[str]:
        fact = self._data["facts"].get(key)
        return fact["value"] if fact else None

    def set(self, key: str, value: str, source: str = "user_said") -> None:
        self._data["facts"][key] = {
            "value": value,
            "set_at": datetime.now().isoformat(timespec="seconds"),
            "source": source,
        }
        self._save()

    def add_note(self, text: str) -> None:
        self._data["notes"].append({
            "text": text,
            "set_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._save()

    def all_facts(self) -> dict[str, str]:
        """Flat {key: value} for prompt injection (e.g. into LLM system msg)."""
        return {k: v["value"] for k, v in self._data["facts"].items()}

    def all_notes(self) -> list[str]:
        return [n["text"] for n in self._data["notes"]]

    def get_preference(self, key: str, default=None):
        return self._data["preferences"].get(key, default)

    def set_preference(self, key: str, value) -> None:
        self._data["preferences"][key] = value
        self._save()

    # ------------------------------------------------------------------ #
    #  Natural-language recall                                            #
    # ------------------------------------------------------------------ #

    def detect_and_recall(self, text: str) -> Optional[str]:
        """Scan for memory-recall patterns. If matched, return the answer string.

        Examples it handles:
            "what's my name"        → "Aapka name Shivang hai."
            "mera naam kya hai"     → same
            "what do you know about me" → comma-list of all facts
        """
        if not text or not text.strip():
            return None

        # "what's my X" / "what is my X"
        m = re.search(r"\b(?:what'?s|what is)\s+my\s+(\w+)\b", text, re.IGNORECASE)
        if m:
            return self._recall_key(m.group(1).lower())

        # "mera X kya hai" / "meri X kya hai"
        m = re.search(r"\bmer[ai]\s+(\w+)\s+kya\s+hai\b", text, re.IGNORECASE)
        if m:
            return self._recall_key(m.group(1).lower())

        # "tell me my X" / "mujhe mera X batao"
        m = re.search(r"\btell me my\s+(\w+)\b|\bmujhe mer[ai]\s+(\w+)\s+batao\b",
                      text, re.IGNORECASE)
        if m:
            key = (m.group(1) or m.group(2) or "").lower()
            if key:
                return self._recall_key(key)

        # Generic "what do you know about me" / "mere baare mein kya jaante ho"
        if re.search(r"\b(?:what|kya)\s+(?:do you|aap)\s+know\s+about\s+(?:me|mere|mujhe)\b", text, re.IGNORECASE) \
                or re.search(r"\bmere baare mein kya jaante\b", text, re.IGNORECASE):
            facts = self.all_facts()
            if not facts:
                return "Aapke baare mein abhi kuch nahi pata, sir. Batao to yaad rakhunga."
            lines = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in facts.items())
            return f"Aapke baare mein ye pata hai: {lines}."

        return None

    # Map Hindi/Hinglish question keys onto the canonical English fact keys
    # we actually store under.
    _KEY_ALIASES: dict[str, str] = {
        "naam": "name",
        "ghar": "location",
        "shahar": "location",
        "city": "location",
        "kaam": "employer",
        "company": "employer",
        "office": "employer",
        "job": "employer",
    }

    def _recall_key(self, key: str) -> str:
        canonical = self._KEY_ALIASES.get(key, key)
        v = self.get(canonical) or self.get(f"favorite_{canonical}")
        if v:
            return f"Aapka {key} {v} hai."
        return f"Mujhe aapka {key} pata nahi hai abhi."

    # ------------------------------------------------------------------ #
    #  Natural-language detection                                         #
    # ------------------------------------------------------------------ #

    def detect_and_store(self, text: str) -> Optional[str]:
        """Scan for memory-setting patterns. If matched, store and return ack.

        Returns None if no memory pattern matched — caller should then proceed
        with normal intent classification.
        """
        if not text or not text.strip():
            return None

        for key, pattern, kind, ack in _DETECTORS:
            m = pattern.search(text)
            if not m:
                continue

            if kind == "single":
                value = _titlecase_clean(m.group(1))
                if not value:
                    continue
                self.set(key, value)
                return ack.format(value=value)

            if kind == "favorite":
                category = m.group(1).lower().strip()
                value = _titlecase_clean(m.group(2))
                if not category or not value:
                    continue
                self.set(f"favorite_{category}", value)
                return ack.format(category=category, value=value)

            if kind == "note":
                note_text = m.group(1).strip()
                if not note_text:
                    continue
                self.add_note(note_text)
                return ack

        return None


if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Use a temp file so the smoke test doesn't pollute real user data
    tmp = os.path.join(tempfile.gettempdir(), "_jarvis_memory_smoke.json")
    if os.path.exists(tmp):
        os.remove(tmp)

    mem = UserMemory(tmp)

    cases = [
        "hello my name is shivang",
        "my name is bob smith",
        "i live in new delhi please",
        "i work at google",
        "my favourite browser is chrome",
        "remember that i need to buy milk on tuesdays",
        "main hoon shaurya",
        "mera favourite gaana shape of you hai",
        "weather batao",  # no memory pattern — should return None
        "chrome kholo",   # ditto
    ]
    for t in cases:
        ack = mem.detect_and_store(t)
        print(f"  {t!r:55s} -> {ack!r}")

    print()
    print("Persisted facts:", mem.all_facts())
    print("Persisted notes:", mem.all_notes())

    # Reload from disk to prove persistence
    mem2 = UserMemory(tmp)
    print()
    print("After reload, facts:", mem2.all_facts())
    print("After reload, name :", mem2.get("name"))
