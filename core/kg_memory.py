"""Knowledge-graph memory — persistent (subject, predicate, object) triples.

Stores facts the user dictates: "Sara is my sister", "I live in Mumbai",
"My birthday is on March fifteenth". Each statement is parsed into one or
more triples and persisted to ``data/knowledge_graph.json``. Later
queries ("who is Sara", "where do I live") walk the triple set to find
the right object.

Parsing strategy:
  1. Regex patterns for common English/Hinglish shapes — covers the
     vast majority of statements ("X is Y", "X lives in Y",
     "X works at Y", "Sara's number is Z")
  2. spaCy NER (optional) for entities the regex misses

Triple format::
    {"s": "sara", "p": "is_my", "o": "sister", "raw": "Sara is my sister"}

Public API:
    kg = get_kg()
    kg.add_triple(s, p, o, raw=None)
    kg.add_statement("Sara is my sister") -> list[triple]    # parse + add
    kg.facts_about(subject) -> list[triple]
    kg.query(question) -> Optional[str]                       # best-effort answer
    kg.forget(subject) -> int                                 # triples removed
    kg.all_triples() -> list[triple]
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_STORE_PATH = _ROOT / "data" / "knowledge_graph.json"


# Statement patterns — each returns one (subject, predicate, object) tuple.
# Order matters: more-specific patterns first.
_STATEMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "Sara is my sister" / "Mom is my mother"
    (re.compile(r"^(?P<s>[\w.\-' ]+?)\s+is\s+my\s+(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "is_my"),
    # "I live in Mumbai" / "Main rehta hoon Mumbai mein"
    (re.compile(r"^(?:i\s+live|main\s+rehta\s+(?:hoon|hu))\s+(?:in\s+|me\s+|mein\s+)?(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "lives_in"),
    # "I work at X" / "main kaam karta hoon X mein"
    (re.compile(r"^(?:i\s+work|main\s+kaam\s+karta\s+(?:hoon|hu))\s+(?:at\s+|in\s+|me\s+|mein\s+)(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "works_at"),
    # "My birthday is March 15" / "My birthday is on March 15"
    (re.compile(r"^my\s+birthday\s+is\s+(?:on\s+)?(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "birthday_is"),
    # "Sara's number is 9999999999"
    (re.compile(r"^(?P<s>[\w.\-' ]+?)'?s\s+(?P<p>phone|number|email|address|birthday)\s+is\s+(?P<o>[\w.\-'@: /]+?)$",
                re.IGNORECASE), None),
    # "X likes Y" / "X loves Y"
    (re.compile(r"^(?P<s>[\w.\-' ]+?)\s+(?:likes?|loves?)\s+(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "likes"),
    # Generic "X is Y"
    (re.compile(r"^(?P<s>[\w.\-' ]+?)\s+is\s+(?:a\s+|an\s+|the\s+)?(?P<o>[\w.\-' ]+?)$",
                re.IGNORECASE), "is"),
]


# Self-statement detection — "I am X", "my name is X", "I'm X"
_SELF_RE = re.compile(
    r"^(?:i\s+am|my\s+name\s+is|i'm|main\s+(?:hu|hoon))\s+(?P<o>[\w.\-' ]+?)$",
    re.IGNORECASE,
)


def _norm(token: str) -> str:
    """Lowercase, collapse whitespace, strip trailing punctuation."""
    return re.sub(r"\s+", " ", (token or "").strip(" .,?!:;'\"")).lower()


def _strip_lead_verb(text: str) -> str:
    """Drop 'remember that ...' / 'note that ...' prefixes."""
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:remember(?:\s+that)?|note(?:\s+that)?|store(?:\s+that)?|"
        r"save(?:\s+that)?|yaad\s+(?:rakho|rakh\s+lo))\s*[,:]?\s*",
        "", (text or "").strip(), flags=re.IGNORECASE,
    ).strip(" .?,\"'")


class KnowledgeGraph:
    def __init__(self):
        self._lock = threading.RLock()
        self._triples: list[dict] = self._load()

    # ── persistence ───────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not _STORE_PATH.exists():
            return []
        try:
            with open(_STORE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [t for t in raw
                    if isinstance(t, dict) and "s" in t and "p" in t and "o" in t]
        except Exception as e:
            log.warning("[kg_memory] load failed: %s", e)
            return []

    def _save(self) -> None:
        try:
            _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._triples, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("[kg_memory] save failed: %s", e)

    # ── parsing + add ─────────────────────────────────────────────

    def add_triple(self, s: str, p: str, o: str,
                   raw: Optional[str] = None) -> dict:
        triple = {"s": _norm(s), "p": _norm(p), "o": _norm(o), "raw": raw or ""}
        with self._lock:
            # Dedup on (s, p, o).
            for existing in self._triples:
                if (existing["s"], existing["p"], existing["o"]) == \
                        (triple["s"], triple["p"], triple["o"]):
                    return existing
            self._triples.append(triple)
            self._save()
        return triple

    def add_statement(self, text: str,
                      default_subject: str = "user") -> list[dict]:
        """Parse a free-form statement into one or more triples + persist."""
        text = _strip_lead_verb(text)
        if not text:
            return []
        added: list[dict] = []
        # Self-statement special case: "I am Shivang" / "my name is X"
        m = _SELF_RE.match(text)
        if m:
            added.append(self.add_triple(default_subject, "is", m.group("o"), raw=text))
            return added
        for pat, default_pred in _STATEMENT_PATTERNS:
            m = pat.match(text)
            if not m:
                continue
            groups = m.groupdict()
            s = groups.get("s") or default_subject
            p = groups.get("p") or default_pred or "fact"
            o = groups["o"]
            if s and p and o:
                added.append(self.add_triple(s, p, o, raw=text))
                return added
        # Fallback: store as (subject=default, p=raw_fact, o=text)
        added.append(self.add_triple(default_subject, "remembers", text, raw=text))
        return added

    # ── query ─────────────────────────────────────────────────────

    def facts_about(self, subject: str) -> list[dict]:
        s = _norm(subject)
        with self._lock:
            return [t for t in self._triples if t["s"] == s]

    def query(self, question: str) -> Optional[str]:
        """Best-effort QA — supports "who is X", "where do I live",
        "what's my X". Returns the matching object string, or None."""
        if not question:
            return None
        q = question.strip().lower()
        # "who is X"
        m = re.search(r"who\s+is\s+(?P<x>[\w.\-' ]+?)\?*$", q)
        if m:
            subj = _norm(m.group("x"))
            with self._lock:
                facts = [t for t in self._triples
                         if t["s"] == subj and t["p"] in ("is", "is_my")]
            if facts:
                return ", ".join(f["o"] for f in facts)
            return None
        # "where do I live" / "where am I living"
        if re.search(r"where\s+(?:do|am)\s+i\s+(?:live|living)", q):
            with self._lock:
                facts = [t for t in self._triples
                         if t["s"] == "user" and t["p"] == "lives_in"]
            return facts[0]["o"] if facts else None
        # "where do I work"
        if re.search(r"where\s+(?:do|am)\s+i\s+work", q):
            with self._lock:
                facts = [t for t in self._triples
                         if t["s"] == "user" and t["p"] == "works_at"]
            return facts[0]["o"] if facts else None
        # "what do I like" / "mujhe kya pasand hai" — fact_bridge stores
        # conversational likes as (user, likes, X); surface them all.
        if re.search(r"what\s+do\s+i\s+(?:like|love)|mujhe\s+kya\s+pasand", q):
            with self._lock:
                facts = [t for t in self._triples
                         if t["s"] == "user" and t["p"] == "likes"]
            return ", ".join(f["o"] for f in facts) if facts else None
        # "what am I learning" / "main kya seekh raha hoon"
        if re.search(r"what\s+am\s+i\s+learning|main\s+kya\s+seekh", q):
            with self._lock:
                facts = [t for t in self._triples
                         if t["s"] == "user" and t["p"] == "learning"]
            return ", ".join(f["o"] for f in facts) if facts else None
        # "what is my X" / "what's my X" / "mera X kya hai"
        m = re.search(r"what(?:'s|\s+is)\s+my\s+(?P<x>[\w.\-' ]+?)\??$", q)
        if m:
            slot = _norm(m.group("x"))
            with self._lock:
                # Try p == slot (e.g. p=birthday_is) or p ends with _is / _are
                for t in self._triples:
                    if t["s"] == "user" and t["p"] in (slot, f"{slot}_is",
                                                        f"is_my_{slot}"):
                        return t["o"]
                    if t["p"] == f"{slot}_is" and t["s"] == "user":
                        return t["o"]
            return None
        # "X's Y" — "Sara's number"
        m = re.search(r"(?P<s>[\w.\-' ]+?)'?s\s+(?P<p>phone|number|email|address|birthday)", q)
        if m:
            subj = _norm(m.group("s"))
            slot = _norm(m.group("p"))
            with self._lock:
                for t in self._triples:
                    if t["s"] == subj and t["p"] == slot:
                        return t["o"]
        return None

    # ── housekeeping ──────────────────────────────────────────────

    def forget(self, subject: str) -> int:
        s = _norm(subject)
        with self._lock:
            before = len(self._triples)
            self._triples = [t for t in self._triples if t["s"] != s]
            removed = before - len(self._triples)
            if removed:
                self._save()
        return removed

    def all_triples(self) -> list[dict]:
        with self._lock:
            return list(self._triples)

    def clear(self) -> int:
        with self._lock:
            n = len(self._triples)
            self._triples = []
            self._save()
        return n


_DEFAULT: Optional[KnowledgeGraph] = None


def get_kg() -> KnowledgeGraph:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = KnowledgeGraph()
    return _DEFAULT
