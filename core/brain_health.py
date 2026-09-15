"""Brain health monitor — AERIS's self-awareness about its own intelligence.

One place that answers: *how well is the brain routing, is it getting
better generation over generation, and is a retrain due?* Everything the
continual-learning loop produces is folded into a single report:

    feedback_log.sqlite      → acceptance / correction rates, confusion pairs,
                               low-confidence hotspots, chat-fallback rate
    learned_patterns.json    → how much new knowledge is waiting to be trained
    train_history.json       → generation-over-generation golden/val trend
    intent_neural/           → live model lineage + hash-drift (neural vs k-NN)

Consumers:
    * ``python -m core.brain_health``            — CLI report (+ report card)
    * ``skills/learning_skill.py``               — voice: "brain health"
    * ``python -m core.retrain``                 — pre/post pipeline report

Composite ``health_score`` (0-100, documented so it's debuggable):
    50%  acceptance rate over the window (accepted / all feedback)
    25%  latest known golden accuracy
    15%  neural router active (hash matches; k-NN-only = 0)
    10%  1 - correction rate over the window
Missing components are dropped and the remaining weights renormalised —
a fresh install without feedback isn't "0 health", it's "unknown,
weighted by what we do know".
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDBACK_DB_PATH = os.path.join(_ROOT, "data", "feedback_log.sqlite")
LIVE_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")
CARD_DIR = os.path.join(_ROOT, "data", "report_card")

# Advisor triggers.
RETRAIN_AT_NEW_SAMPLES = 15
CORRECTION_SPIKE_MIN = 3       # corrections in window to call it a spike
LOW_CONF_AVG = 0.65
LOW_CONF_MIN_N = 3


@dataclass
class HealthReport:
    window_days: int
    generated_at: str = ""
    # usage window
    utterances_window: int = 0
    accepted: int = 0
    corrected: int = 0
    cancelled: int = 0
    chat_fallbacks: int = 0
    acceptance_rate: Optional[float] = None       # accepted / feedbacked
    correction_rate: Optional[float] = None
    # trouble spots (all-time unless noted)
    confusion_pairs: list = field(default_factory=list)   # [{from,to,n}]
    correction_hotspots: list = field(default_factory=list)  # [{intent,n}]
    low_conf_hotspots: list = field(default_factory=list)    # [{intent,avg_conf,n}]
    # learning store
    learned_trainable: int = 0
    learned_review: int = 0
    new_since_train: int = 0
    # model + lineage
    generation: Optional[int] = None
    model_trained_at: Optional[str] = None
    best_val_acc: Optional[float] = None
    golden_acc: Optional[float] = None
    neural_active: Optional[bool] = None          # None = could not determine
    trend: list = field(default_factory=list)     # [{generation,golden,val,at,mode}]
    # verdicts
    health_score: Optional[int] = None
    retrain_recommended: bool = False
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------- #
#  Collection                                                             #
# ---------------------------------------------------------------------- #

def collect(window_days: int = 7,
            db_path: str = FEEDBACK_DB_PATH,
            live_dir: str = LIVE_DIR,
            check_hash: bool = True) -> HealthReport:
    """Build the full report. ``check_hash=False`` skips the corpus-hash
    comparison (which triggers skill discovery) for contexts that can't
    afford it — ``neural_active`` is then reported as None."""
    r = HealthReport(window_days=window_days,
                     generated_at=datetime.now().isoformat(timespec="seconds"))
    _collect_usage(r, db_path)
    _collect_learning(r)
    _collect_model(r, live_dir, check_hash)
    _score(r)
    _advise(r)
    return r


def _collect_usage(r: HealthReport, db_path: str) -> None:
    if not os.path.exists(db_path):
        return
    since = (datetime.now() - timedelta(days=r.window_days)) \
        .isoformat(timespec="seconds")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        log.warning("[health] cannot open feedback DB: %s", e)
        return
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n,
                   SUM(CASE WHEN user_feedback = 'accepted'  THEN 1 ELSE 0 END) AS acc,
                   SUM(CASE WHEN user_feedback = 'corrected' THEN 1 ELSE 0 END) AS cor,
                   SUM(CASE WHEN user_feedback = 'cancelled' THEN 1 ELSE 0 END) AS can,
                   SUM(CASE WHEN action_taken = 'chat_fallback' THEN 1 ELSE 0 END) AS chat
            FROM utterances WHERE timestamp >= ?
            """, (since,)).fetchone()
        r.utterances_window = int(row["n"] or 0)
        r.accepted = int(row["acc"] or 0)
        r.corrected = int(row["cor"] or 0)
        r.cancelled = int(row["can"] or 0)
        r.chat_fallbacks = int(row["chat"] or 0)
        feedbacked = r.accepted + r.corrected + r.cancelled
        if feedbacked:
            r.acceptance_rate = round(r.accepted / feedbacked, 4)
            r.correction_rate = round((r.corrected + r.cancelled) / feedbacked, 4)

        # Confusion pairs — every correction ever is a labelled arrow
        # "model said X, user meant Y". All-time: they're rare and precious.
        r.confusion_pairs = [
            {"from": row2["predicted_intent"], "to": row2["correct_intent"],
             "n": int(row2["n"])}
            for row2 in conn.execute(
                """
                SELECT predicted_intent, correct_intent, COUNT(*) AS n
                FROM utterances
                WHERE user_feedback = 'corrected'
                  AND correct_intent IS NOT NULL AND predicted_intent IS NOT NULL
                GROUP BY predicted_intent, correct_intent
                ORDER BY n DESC LIMIT 10
                """)
        ]
        r.correction_hotspots = [
            {"intent": row2["predicted_intent"], "n": int(row2["n"])}
            for row2 in conn.execute(
                """
                SELECT predicted_intent, COUNT(*) AS n
                FROM utterances
                WHERE user_feedback IN ('corrected', 'cancelled')
                  AND predicted_intent IS NOT NULL
                GROUP BY predicted_intent ORDER BY n DESC LIMIT 8
                """)
        ]
        r.low_conf_hotspots = [
            {"intent": row2["predicted_intent"],
             "avg_conf": round(float(row2["avg_conf"]), 3), "n": int(row2["n"])}
            for row2 in conn.execute(
                """
                SELECT predicted_intent, AVG(confidence) AS avg_conf,
                       COUNT(*) AS n
                FROM utterances
                WHERE predicted_intent IS NOT NULL AND timestamp >= ?
                GROUP BY predicted_intent
                HAVING n >= ? AND avg_conf < ?
                ORDER BY avg_conf ASC LIMIT 8
                """, (since, LOW_CONF_MIN_N, LOW_CONF_AVG))
        ]
    except Exception as e:
        log.warning("[health] usage mining failed: %s", e)
    finally:
        conn.close()


def _collect_learning(r: HealthReport) -> None:
    try:
        from core.learning_loop import LearningStore
        s = LearningStore().status()
        r.learned_trainable = s["trainable_samples"]
        r.learned_review = s["review_samples"]
        r.new_since_train = s["new_since_last_train"]
    except Exception as e:
        log.warning("[health] learning store unavailable: %s", e)


def _collect_model(r: HealthReport, live_dir: str, check_hash: bool) -> None:
    meta_p = os.path.join(live_dir, "metadata.json")
    if os.path.exists(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
            r.generation = meta.get("generation", 1)
            r.model_trained_at = meta.get("trained_at")
            r.best_val_acc = meta.get("best_val_acc")
            r.golden_acc = meta.get("golden_acc")
        except Exception:
            pass

    # Neural-vs-kNN: does the saved hash still match the live merged corpus?
    # Pure-JSON check — no torch. Triggers skill discovery (idempotent).
    if check_hash:
        labels_p = os.path.join(live_dir, "labels.json")
        try:
            with open(labels_p, "r", encoding="utf-8") as f:
                saved = json.load(f).get("intents_hash")
            if saved:
                from core.intent_loader import intents_hash
                r.neural_active = (saved == intents_hash())
            else:
                r.neural_active = False
        except FileNotFoundError:
            r.neural_active = False
        except Exception as e:
            log.warning("[health] hash check failed: %s", e)

    # Golden accuracy fallback: newest golden report card for the live model.
    if r.golden_acc is None:
        r.golden_acc = _latest_card_accuracy()

    # Generation trend from lineage.
    try:
        from core.model_registry import history
        for e in history():
            if e.get("event") == "promote":
                r.trend.append({
                    "generation": e.get("generation"),
                    "golden": e.get("golden_acc"),
                    "val": e.get("best_val_acc"),
                    "mode": e.get("mode"),
                    "at": e.get("at"),
                })
    except Exception:
        pass


def _latest_card_accuracy() -> Optional[float]:
    try:
        cards = sorted(
            (f for f in os.listdir(CARD_DIR)
             if f.startswith("intent_eval_") and f.endswith(".json")),
            reverse=True)
        for name in cards:
            with open(os.path.join(CARD_DIR, name), "r", encoding="utf-8") as f:
                d = json.load(f)
            # Only trust cards scored against the LIVE dir (not staging/knn).
            if str(d.get("model", "")).rstrip("\\/").endswith("intent_neural"):
                return d.get("accuracy")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------- #
#  Scoring + advice                                                       #
# ---------------------------------------------------------------------- #

def _score(r: HealthReport) -> None:
    parts: list[tuple[float, float]] = []   # (weight, value 0..1)
    if r.acceptance_rate is not None:
        parts.append((0.50, r.acceptance_rate))
    if r.golden_acc is not None:
        parts.append((0.25, float(r.golden_acc)))
    if r.neural_active is not None:
        parts.append((0.15, 1.0 if r.neural_active else 0.0))
    if r.correction_rate is not None:
        parts.append((0.10, 1.0 - r.correction_rate))
    if not parts:
        return
    total_w = sum(w for w, _ in parts)
    r.health_score = int(round(100 * sum(w * v for w, v in parts) / total_w))


def _advise(r: HealthReport) -> None:
    if r.neural_active is False:
        r.reasons.append("corpus hash drifted — brain is on k-NN fallback")
    if r.new_since_train >= RETRAIN_AT_NEW_SAMPLES:
        r.reasons.append(
            f"{r.new_since_train} new learned samples since last train")
    if r.corrected + r.cancelled >= CORRECTION_SPIKE_MIN:
        r.reasons.append(
            f"{r.corrected + r.cancelled} corrections/cancels in the last "
            f"{r.window_days}d")
    r.retrain_recommended = bool(r.reasons)


# ---------------------------------------------------------------------- #
#  Rendering                                                              #
# ---------------------------------------------------------------------- #

def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def format_report(r: HealthReport) -> str:
    lines = ["AERIS brain health", "=" * 44]
    score = "—" if r.health_score is None else f"{r.health_score}/100"
    lines.append(f"health score    : {score}")
    router = {True: "NEURAL (hash ok)", False: "k-NN FALLBACK (hash drifted)",
              None: "unknown"}[r.neural_active]
    lines.append(f"router          : {router}")
    if r.generation:
        lines.append(f"live model      : gen {r.generation}  "
                     f"val={_pct(r.best_val_acc)}  golden={_pct(r.golden_acc)}  "
                     f"({r.model_trained_at})")
    lines.append(f"last {r.window_days}d usage  : {r.utterances_window} utterances  "
                 f"acceptance={_pct(r.acceptance_rate)}  "
                 f"corrections={r.corrected + r.cancelled}  "
                 f"chat-fallbacks={r.chat_fallbacks}")
    lines.append(f"learned store   : {r.learned_trainable} trainable "
                 f"(+{r.learned_review} in review), "
                 f"{r.new_since_train} new since last train")
    if r.trend:
        lines.append("generations     :")
        for t in r.trend[-6:]:
            lines.append(f"    gen {t['generation']:>3}  golden={_pct(t['golden'])}  "
                         f"val={_pct(t['val'])}  {t['mode'] or ''}  {t['at'] or ''}")
    if r.confusion_pairs:
        lines.append("confusions      :")
        for c in r.confusion_pairs[:5]:
            lines.append(f"    {c['from']} -> {c['to']}  x{c['n']}")
    if r.low_conf_hotspots:
        lines.append("low-conf intents:")
        for h in r.low_conf_hotspots[:5]:
            lines.append(f"    {h['intent']}  avg={h['avg_conf']}  n={h['n']}")
    lines.append("")
    if r.retrain_recommended:
        lines.append("RETRAIN RECOMMENDED:")
        for why in r.reasons:
            lines.append(f"  - {why}")
        lines.append("  run: python -m core.retrain")
    else:
        lines.append("No retrain needed — keep using AERIS.")
    return "\n".join(lines)


def speak_summary(r: HealthReport) -> str:
    """2-3 short Hinglish sentences for the voice/chat surface."""
    bits = []
    if r.health_score is not None:
        bits.append(f"Brain health {r.health_score} out of 100 hai, sir.")
    if r.neural_active is False:
        bits.append("Abhi main k-NN fallback pe chal raha hoon — "
                    "neural model retrain ka wait kar raha hai.")
    elif r.generation:
        bits.append(f"Generation {r.generation} neural model active hai"
                    + (f", golden accuracy {_pct(r.golden_acc)}."
                       if r.golden_acc is not None else "."))
    if r.acceptance_rate is not None:
        bits.append(f"Pichhle {r.window_days} din mein acceptance "
                    f"{_pct(r.acceptance_rate)} rahi.")
    if r.retrain_recommended:
        bits.append(f"Retrain due hai — {r.reasons[0]}.")
    return " ".join(bits) or "Abhi report banane ke liye kaafi data nahi hai, sir."


# ---------------------------------------------------------------------- #
#  Initiative source — the proactive "retrain due" nudge                  #
# ---------------------------------------------------------------------- #

NUDGE_COOLDOWN_S = 24 * 3600
_NUDGE_STAMP = os.path.join(CARD_DIR, ".retrain_nudge_stamp")


def _nudged_recently() -> bool:
    try:
        return (time.time() - os.path.getmtime(_NUDGE_STAMP)) < NUDGE_COOLDOWN_S
    except OSError:
        return False


def initiative_candidates() -> list:
    """Initiative-engine source: at most one 'retrain due' OFFER per day.

    Salience is tuned to land in the engine's offer band (never autonomous
    act — training stays a user ritual). Registered in
    ``initiative_engine.get_engine``; silence on any failure.
    """
    try:
        if _nudged_recently():
            return []
        r = collect(window_days=7)
        if not r.retrain_recommended:
            return []
        from core.initiative_engine import Initiative
        os.makedirs(CARD_DIR, exist_ok=True)
        with open(_NUDGE_STAMP, "w") as f:
            f.write(str(time.time()))
        if r.new_since_train:
            text = (f"Sir, maine usage se {r.new_since_train} naye phrases "
                    "seekh rakhe hain — retrain due hai. Free ho to terminal "
                    "se `python -m core.retrain` chala dijiye.")
        else:
            text = ("Sir, brain abhi k-NN fallback pe hai — "
                    "`python -m core.retrain` se neural model refresh ho jayega.")
        return [Initiative(
            text=text, kind="retrain_due", action="notify_user",
            importance=0.5, timeliness=0.6, confidence=0.9, openness=0.5,
            source_id="learning:retrain_due", requested_level=2,
        )]
    except Exception as e:
        log.debug("[health] initiative source failed: %s", e)
        return []


def write_card(r: HealthReport) -> str:
    os.makedirs(CARD_DIR, exist_ok=True)
    path = os.path.join(
        CARD_DIR, f"brain_health_{time.strftime('%Y%m%d-%H%M%S')}.json")
    from core.atomic_io import write_atomic_json
    write_atomic_json(path, r.to_dict())
    return path


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    days = 7
    as_json = "--json" in argv
    if "--days" in argv:
        try:
            days = int(argv[argv.index("--days") + 1])
        except (IndexError, ValueError):
            pass
    r = collect(window_days=days)
    if as_json:
        print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(format_report(r))
    print(f"\nreport card: {write_card(r)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
