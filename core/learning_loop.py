"""Continual learning store — turns real usage into training data.

The missing feedback→training bridge. ``core/feedback.py`` logs every
utterance + outcome to SQLite, but until now that data never flowed back
into the corpus: the neural model only ever saw hand-written patterns
from ``intents.json``. This module closes the loop:

    real usage (feedback_log.sqlite)
        │  harvest()                 — corrections + accepted utterances
        ▼
    data/learned_patterns.json      — provenance-tagged learned samples
        │  merged by intent_loader  — k-NN + exact-match see them at once
        ▼
    python -m core.train_intent     — neural model absorbs them (run by user)

Harvest rules (deliberately conservative — garbage in the corpus is worse
than a smaller corpus):

* ``corrected`` rows with a ``correct_intent`` are GOLD — the user
  explicitly told us the right answer.
* ``accepted`` rows are positives — the user let the action run. Rows at
  confidence ≥ 0.995 are skipped (exact-match fast path; the pattern is
  already in the corpus, zero new information).
* Everything is deduped against the live merged corpus AND against
  already-learned samples (normalised comparison). A repeat sighting
  bumps ``times_seen`` instead of duplicating.
* Un-feedback'd utterances are NOT harvested — ambiguous signals stay in
  the existing ``pending_patterns`` review queue (``core/review_cli.py``).

Harvest is an explicit pre-training step, not a background daemon:
merging new patterns changes the intents hash, which (by design) drops
the brain back to k-NN until the neural model is retrained. Running
harvest right before retraining keeps the neural model valid during
normal operation.

CLI:
    python -m core.learning_loop status     # what has AERIS learned / when to retrain
    python -m core.learning_loop harvest    # mine feedback DB -> learned_patterns.json
    python -m core.learning_loop list       # show learned samples per intent
    python -m core.learning_loop reject "<text>"          # never train on this
    python -m core.learning_loop approve "<text>"         # promote review -> auto
    python -m core.learning_loop teach "<text>" <intent>  # manual gold sample
    python -m core.learning_loop review-ai                # LLM-assisted review
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.atomic_io import write_atomic_json

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEARNED_PATH = os.path.join(_ROOT, "data", "learned_patterns.json")
FEEDBACK_DB_PATH = os.path.join(_ROOT, "data", "feedback_log.sqlite")

# Confidence at/above this means the exact-match fast path answered —
# the phrase is already a verbatim corpus pattern, nothing to learn.
_EXACT_MATCH_CONF = 0.995

# Accepted rows below this confidence are still queued, but as 'review'
# (not auto-trusted): the user accepted the action, yet the classifier
# was near its threshold — a mislabel here would poison the corpus.
_AUTO_TRUST_CONF = 0.60

# Guardrails on what a sample may look like.
_MIN_CHARS = 2
_MAX_CHARS = 200

# Retrain advisor: suggest a retrain once this many new samples pile up.
RETRAIN_ADVICE_AT = 15


@dataclass
class LearnedSample:
    text: str
    intent: str
    source: str                 # 'corrected' | 'accepted' | 'manual'
    status: str = "auto"        # 'auto' (trains) | 'review' | 'rejected'
    confidence: float = 0.0
    times_seen: int = 1
    first_seen: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict:
        return {
            "text": self.text, "intent": self.intent, "source": self.source,
            "status": self.status, "confidence": round(self.confidence, 4),
            "times_seen": self.times_seen,
            "first_seen": self.first_seen, "last_seen": self.last_seen,
        }

    @staticmethod
    def from_dict(d: dict) -> "LearnedSample":
        return LearnedSample(
            text=str(d.get("text", "")),
            intent=str(d.get("intent", "")),
            source=str(d.get("source", "manual")),
            status=str(d.get("status", "auto")),
            confidence=float(d.get("confidence", 0.0)),
            times_seen=int(d.get("times_seen", 1)),
            first_seen=str(d.get("first_seen", "")),
            last_seen=str(d.get("last_seen", "")),
        )


@dataclass
class HarvestReport:
    scanned: int = 0
    added: int = 0
    bumped: int = 0             # repeat sightings (times_seen += 1)
    skipped_known: int = 0      # already a corpus pattern
    skipped_exact: int = 0      # exact-match fast-path rows (conf 1.0)
    skipped_invalid: int = 0    # too short / too long / no intent
    new_watermark: int = 0
    by_intent: dict = field(default_factory=dict)


class LearningStore:
    """Owner of ``data/learned_patterns.json``. All writes are atomic."""

    def __init__(self, path: str = LEARNED_PATH,
                 db_path: str = FEEDBACK_DB_PATH):
        self.path = path
        self.db_path = db_path
        self._data = self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and "samples" in data:
                    return data
            except Exception as e:
                log.warning("[learn] could not read %s: %s", self.path, e)
        return {
            "version": 1,
            "meta": {
                "last_utterance_id": 0,
                "last_harvest_at": None,
                "trained_sample_count": 0,
                "last_trained_at": None,
            },
            "samples": [],
        }

    def save(self) -> None:
        write_atomic_json(self.path, self._data)

    # ------------------------------------------------------------------ #
    #  Views                                                              #
    # ------------------------------------------------------------------ #

    @property
    def samples(self) -> list[LearnedSample]:
        return [LearnedSample.from_dict(d) for d in self._data["samples"]]

    def as_intent_dict(self) -> dict[str, list[str]]:
        """{intent: [phrase, ...]} for every trainable ('auto') sample.

        This is what ``intent_loader.load_all_intents`` merges into the
        corpus — so k-NN, exact-match AND the neural trainer all see the
        learned phrases through the one canonical path.
        """
        out: dict[str, list[str]] = {}
        for s in self.samples:
            if s.status == "auto" and s.intent and s.text:
                out.setdefault(s.intent, []).append(s.text)
        return out

    def status(self) -> dict:
        samples = self.samples
        auto = [s for s in samples if s.status == "auto"]
        meta = self._data["meta"]
        new_since_train = max(0, len(auto) - int(meta.get("trained_sample_count", 0)))
        by_intent: dict[str, int] = {}
        for s in auto:
            by_intent[s.intent] = by_intent.get(s.intent, 0) + 1
        return {
            "total_samples": len(samples),
            "trainable_samples": len(auto),
            "review_samples": sum(1 for s in samples if s.status == "review"),
            "new_since_last_train": new_since_train,
            "retrain_recommended": new_since_train >= RETRAIN_ADVICE_AT,
            "last_harvest_at": meta.get("last_harvest_at"),
            "last_trained_at": meta.get("last_trained_at"),
            "by_intent": by_intent,
        }

    def mark_trained(self) -> None:
        """Stamp the store after a successful (promoted) training run so
        the retrain advisor counts only genuinely new samples."""
        auto = sum(1 for s in self.samples if s.status == "auto")
        self._data["meta"]["trained_sample_count"] = auto
        self._data["meta"]["last_trained_at"] = _now()
        self.save()

    # ------------------------------------------------------------------ #
    #  Harvest                                                            #
    # ------------------------------------------------------------------ #

    def harvest(self, known_intents: Optional[dict] = None) -> HarvestReport:
        """Mine feedback_log.sqlite for new learnable samples.

        ``known_intents``: pre-loaded merged intent dict (pass to skip a
        second skill discovery); loaded via ``intent_loader`` when omitted.
        Only rows past the stored watermark are scanned, so repeated
        harvests are cheap and idempotent.
        """
        report = HarvestReport()
        if not os.path.exists(self.db_path):
            log.info("[learn] no feedback DB at %s — nothing to harvest", self.db_path)
            return report

        if known_intents is None:
            from core.intent_loader import load_all_intents
            known_intents = load_all_intents()

        clean = _make_normalizer()
        known_norm = _corpus_normalized_set(known_intents, clean)
        intent_names = set(known_intents.keys())

        # Index existing learned samples by normalised text for dedupe.
        existing: dict[str, dict] = {}
        for raw in self._data["samples"]:
            existing[clean(raw.get("text", ""))] = raw

        watermark = int(self._data["meta"].get("last_utterance_id", 0))
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT id, raw_text, predicted_intent, confidence,
                       user_feedback, correct_intent
                FROM utterances
                WHERE id > ? AND user_feedback IN ('accepted', 'corrected')
                ORDER BY id
                """,
                (watermark,),
            ).fetchall()
        finally:
            conn.close()

        now = _now()
        for row in rows:
            report.scanned += 1
            report.new_watermark = max(report.new_watermark, int(row["id"]))

            if row["user_feedback"] == "corrected":
                intent = row["correct_intent"]
                source = "corrected"
                # A correction is gold regardless of model confidence.
                trust_auto = True
            else:
                intent = row["predicted_intent"]
                source = "accepted"
                conf = float(row["confidence"] or 0.0)
                if conf >= _EXACT_MATCH_CONF:
                    report.skipped_exact += 1
                    continue
                trust_auto = conf >= _AUTO_TRUST_CONF

            text = (row["raw_text"] or "").strip()
            if (not intent or intent not in intent_names
                    or not (_MIN_CHARS <= len(text) <= _MAX_CHARS)):
                report.skipped_invalid += 1
                continue

            key = clean(text)
            if not key:
                report.skipped_invalid += 1
                continue
            if key in known_norm:
                report.skipped_known += 1
                continue
            if key in existing:
                raw = existing[key]
                raw["times_seen"] = int(raw.get("times_seen", 1)) + 1
                raw["last_seen"] = now
                # A correction upgrades an unsure 'review' sample to gold.
                if source == "corrected" and raw.get("status") == "review":
                    raw["status"] = "auto"
                    raw["intent"] = intent
                    raw["source"] = "corrected"
                report.bumped += 1
                continue

            sample = LearnedSample(
                text=text, intent=intent, source=source,
                status="auto" if trust_auto else "review",
                confidence=float(row["confidence"] or 0.0),
                first_seen=now, last_seen=now,
            )
            self._data["samples"].append(sample.to_dict())
            existing[key] = self._data["samples"][-1]
            if sample.status == "auto":
                report.by_intent[intent] = report.by_intent.get(intent, 0) + 1
            report.added += 1

        if report.new_watermark:
            self._data["meta"]["last_utterance_id"] = max(
                watermark, report.new_watermark)
        self._data["meta"]["last_harvest_at"] = now
        self.save()
        return report

    # ------------------------------------------------------------------ #
    #  Manual curation                                                    #
    # ------------------------------------------------------------------ #

    def add_manual(self, text: str, intent: str) -> bool:
        """Directly teach a phrase→intent mapping (status 'auto')."""
        text = (text or "").strip()
        if not text or not intent:
            return False
        clean = _make_normalizer()
        key = clean(text)
        for raw in self._data["samples"]:
            if clean(raw.get("text", "")) == key:
                raw["intent"] = intent
                raw["status"] = "auto"
                raw["source"] = "manual"
                self.save()
                return True
        now = _now()
        self._data["samples"].append(LearnedSample(
            text=text, intent=intent, source="manual",
            first_seen=now, last_seen=now).to_dict())
        self.save()
        return True

    def set_status(self, text: str, status: str) -> bool:
        """Flip a sample between 'auto' / 'review' / 'rejected'."""
        if status not in ("auto", "review", "rejected"):
            raise ValueError(f"bad status {status!r}")
        clean = _make_normalizer()
        key = clean(text)
        for raw in self._data["samples"]:
            if clean(raw.get("text", "")) == key:
                raw["status"] = status
                self.save()
                return True
        return False


# ---------------------------------------------------------------------- #
#  Helpers                                                                #
# ---------------------------------------------------------------------- #

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _make_normalizer():
    """Return a text→canonical-key callable. Falls back to a plain
    casefold+squeeze if the HinglishNormalizer can't import (e.g. Colab
    bundle without its data files)."""
    try:
        from core.normalizer import HinglishNormalizer
        norm = HinglishNormalizer()
        return lambda t: norm.clean(t or "")
    except Exception:
        return lambda t: " ".join((t or "").lower().split())


def _corpus_normalized_set(intents: dict, clean) -> set[str]:
    out: set[str] = set()
    for cfg in intents.values():
        for p in cfg.get("patterns", []):
            out.add(clean(p))
    return out


# ---------------------------------------------------------------------- #
#  CLI                                                                    #
# ---------------------------------------------------------------------- #

def _cli_status(store: LearningStore) -> None:
    s = store.status()
    print("AERIS learning-loop status")
    print(f"  learned samples : {s['total_samples']} total  "
          f"({s['trainable_samples']} trainable, {s['review_samples']} in review)")
    print(f"  last harvest    : {s['last_harvest_at'] or 'never'}")
    print(f"  last train mark : {s['last_trained_at'] or 'never'}")
    print(f"  new since train : {s['new_since_last_train']}")
    if s["by_intent"]:
        print("  per intent:")
        for k in sorted(s["by_intent"], key=lambda k: -s["by_intent"][k]):
            print(f"    {k:28s} {s['by_intent'][k]}")
    if s["retrain_recommended"]:
        print("\n  >> RETRAIN RECOMMENDED — run:")
        print("     python -m core.learning_loop harvest   (refresh first)")
        print("     python -m core.train_intent            (incremental by default)")
    else:
        print("\n  Keep using AERIS — retrain suggested at "
              f"{RETRAIN_ADVICE_AT}+ new samples.")


def _cli_harvest(store: LearningStore) -> None:
    r = store.harvest()
    print("Harvest complete.")
    print(f"  scanned {r.scanned} feedback rows  ->  "
          f"+{r.added} new, {r.bumped} repeat-bumped")
    print(f"  skipped: {r.skipped_known} already-known, "
          f"{r.skipped_exact} exact-match, {r.skipped_invalid} invalid")
    if r.by_intent:
        for k, v in sorted(r.by_intent.items(), key=lambda kv: -kv[1]):
            print(f"    +{v}  {k}")
    _cli_status(store)


def _cli_list(store: LearningStore) -> None:
    samples = store.samples
    if not samples:
        print("No learned samples yet. Use AERIS, then: "
              "python -m core.learning_loop harvest")
        return
    by_intent: dict[str, list[LearnedSample]] = {}
    for s in samples:
        by_intent.setdefault(s.intent, []).append(s)
    for intent in sorted(by_intent):
        print(f"\n{intent}:")
        for s in by_intent[intent]:
            flag = {"auto": " ", "review": "?", "rejected": "x"}[s.status]
            print(f"  [{flag}] {s.text!r}  ({s.source}, seen {s.times_seen}x, "
                  f"conf {s.confidence:.2f})")


def ai_suggest(text: str, intent: str, examples: list[str]
               ) -> tuple[Optional[bool], str]:
    """Ask the embedded LLM whether ``text`` belongs to ``intent``.

    Returns (True/False, why) — or (None, reason) when no verdict is
    possible (LLM offline / bad output). Suggestion only: the caller
    (an interactive human) always has the final word.
    """
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return None, "LLM offline"
        ex = "; ".join(repr(e) for e in examples[:3]) or "(none)"
        raw = llm.chat_json([
            {"role": "system",
             "content": ('You label Hinglish voice-assistant phrases. Reply '
                         'with ONE JSON object only: {"match": true|false, '
                         '"why": "<short reason>"}')},
            {"role": "user",
             "content": (f"Phrase: {text!r}\nProposed intent: {intent}\n"
                         f"Example phrases of this intent: {ex}\n"
                         f"Does the phrase mean the same kind of request?")},
        ], max_tokens=80)
        from core.tool_router import _extract_json
        obj = _extract_json(raw or "") or {}
        if "match" not in obj:
            return None, "no verdict"
        return bool(obj["match"]), str(obj.get("why", ""))[:100]
    except Exception as e:
        return None, f"LLM error: {e}"


def _cli_review_ai(store: LearningStore) -> None:
    review = [s for s in store.samples if s.status == "review"]
    if not review:
        print("Review queue khali hai — sab samples resolved.")
        return
    try:
        from core.intent_loader import load_all_intents
        intents = load_all_intents()
    except Exception:
        intents = {}
    print(f"{len(review)} sample(s) in review. AI suggestion ke saath — "
          f"final word aapka.\n")
    for s in review:
        examples = (intents.get(s.intent) or {}).get("patterns", [])
        verdict, why = ai_suggest(s.text, s.intent, examples)
        sug_txt = {True: "APPROVE", False: "REJECT", None: "no suggestion"}[verdict]
        print("─" * 56)
        print(f"  text   : {s.text!r}")
        print(f"  intent : {s.intent}  (conf {s.confidence:.2f}, "
              f"seen {s.times_seen}x)")
        print(f"  AI     : {sug_txt} — {why}")
        try:
            ans = input("  [a]pprove / [r]eject / [s]kip / Enter=AI / [q]uit > "
                        ).strip().lower()
        except EOFError:
            break
        if ans == "q":
            break
        if ans == "" and verdict is not None:
            ans = "a" if verdict else "r"
        if ans == "a":
            store.set_status(s.text, "auto")
            print("  -> approved (trains on next retrain)")
        elif ans == "r":
            store.set_status(s.text, "rejected")
            print("  -> rejected")
        else:
            print("  -> skipped")
    print("\nDone. `python -m core.learning_loop status` se summary dekho.")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = argv[1] if len(argv) > 1 else "status"
    store = LearningStore()
    if cmd == "status":
        _cli_status(store)
    elif cmd == "harvest":
        _cli_harvest(store)
    elif cmd == "list":
        _cli_list(store)
    elif cmd == "reject" and len(argv) > 2:
        ok = store.set_status(argv[2], "rejected")
        print("Rejected — will never train on it." if ok else "No such sample.")
        return 0 if ok else 1
    elif cmd == "approve" and len(argv) > 2:
        ok = store.set_status(argv[2], "auto")
        print("Approved — trains on next retrain." if ok else "No such sample.")
        return 0 if ok else 1
    elif cmd == "teach" and len(argv) > 3:
        ok = store.add_manual(argv[2], argv[3])
        print(f"Learned: {argv[2]!r} -> {argv[3]}" if ok else "Invalid input.")
        return 0 if ok else 1
    elif cmd == "review-ai":
        _cli_review_ai(store)
    else:
        print(__doc__.split("CLI:")[-1])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
