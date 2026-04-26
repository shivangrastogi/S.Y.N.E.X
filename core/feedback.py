"""Reward-shaped continual learning — the "RL" piece, framed as a contextual bandit.

Three responsibilities:

    1. **Log every utterance + outcome** to SQLite for later inspection and
       active labelling.
    2. **Learn per-intent acceptance thresholds** by exponential moving average
       of a reward signal (+1 accepted, -1 corrected/cancelled, 0 ignored).
       This *is* the policy — the brain looks up `get_threshold(intent)` at
       predict time instead of using a fixed 0.5.
    3. **Queue low-confidence utterances** so the user can later approve them
       as new patterns for an existing intent (or a brand-new one). Approved
       patterns are appended to `intents.json`; the brain's k-NN index
       auto-rebuilds on next boot because the file hash changed.

Why "contextual bandit" not "RL":
    - One-shot decision per utterance (no sequential state).
    - Reward is observed immediately (or within a short timeout window).
    - Action space is small ({execute, disambig, fallback}).
    Pure RL machinery (Q-learning, policy gradients) would be overkill;
    a per-arm EMA over reward is the correct, well-known tool.

This module is standalone and side-effect-free aside from its DB and the
optional `intents.json` mutation in `approve_pattern()`. C9 wires it into
`main_engine.run()`.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


# ---- EMA / threshold tuning constants -------------------------------- #
ALPHA = 0.1                 # EMA smoothing factor
DEFAULT_THRESHOLD = 0.5     # initial accept threshold for any new intent
MIN_THRESHOLD = 0.40        # never drift below this — keep some standard
MAX_THRESHOLD = 0.90        # never drift above this — avoid total refusal
DRIFT_DOWN_AFTER_SAMPLES = 5
DRIFT_DOWN_REWARD_GATE = 0.5
DRIFT_UP_REWARD_GATE = -0.2


_FEEDBACK_TO_REWARD: dict[str, int] = {
    "accepted":  +1,
    "corrected": -1,
    "cancelled": -1,
    "ignored":    0,
}


# ---- Schema ---------------------------------------------------------- #
_DDL = """
CREATE TABLE IF NOT EXISTS utterances (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    raw_text          TEXT NOT NULL,
    normalized_text   TEXT,
    predicted_intent  TEXT,
    confidence        REAL,
    top3_json         TEXT,
    sentiment_label   TEXT,
    sentiment_score   REAL,
    action_taken      TEXT,
    user_feedback     TEXT,
    correct_intent    TEXT,
    reward            INTEGER
);

CREATE TABLE IF NOT EXISTS intent_thresholds (
    intent           TEXT PRIMARY KEY,
    accept_threshold REAL NOT NULL,
    sample_count     INTEGER NOT NULL DEFAULT 0,
    avg_reward       REAL NOT NULL DEFAULT 0.0,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_patterns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    utterance_id  INTEGER REFERENCES utterances(id),
    raw_text      TEXT NOT NULL,
    top3_json     TEXT,
    queued_at     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_patterns(status);
CREATE INDEX IF NOT EXISTS idx_utterances_intent ON utterances(predicted_intent);
"""


@dataclass
class IntentThreshold:
    intent: str
    accept_threshold: float
    sample_count: int
    avg_reward: float
    updated_at: str


@dataclass
class PendingPattern:
    id: int
    utterance_id: Optional[int]
    raw_text: str
    top3: list[tuple[str, float]]
    queued_at: str
    status: str


class FeedbackStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, isolation_level=None,  # autocommit
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_DDL)

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ #
    #  Utterance logging                                                  #
    # ------------------------------------------------------------------ #

    def log_utterance(
        self,
        raw_text: str,
        normalized_text: str,
        predicted_intent: Optional[str],
        confidence: float,
        top3: list[tuple[str, float]],
        sentiment_label: str,
        sentiment_score: float,
        action_taken: str,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO utterances
            (timestamp, raw_text, normalized_text, predicted_intent, confidence,
             top3_json, sentiment_label, sentiment_score, action_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                raw_text,
                normalized_text,
                predicted_intent,
                float(confidence),
                json.dumps(top3),
                sentiment_label,
                float(sentiment_score),
                action_taken,
            ),
        )
        return int(cur.lastrowid)

    def record_feedback(
        self,
        utterance_id: int,
        feedback: str,
        correct_intent: Optional[str] = None,
    ) -> None:
        """Apply user feedback to a previously logged utterance.

        Side effects:
          - writes user_feedback, correct_intent, reward into the row
          - updates the per-intent threshold for the original predicted intent
            via EMA on reward
          - if correct_intent is provided AND differs from predicted_intent,
            also updates the threshold for the *correct* intent (positive
            sample) so the right intent rises in confidence over time
        """
        if feedback not in _FEEDBACK_TO_REWARD:
            raise ValueError(f"Unknown feedback label: {feedback!r}")
        reward = _FEEDBACK_TO_REWARD[feedback]

        row = self._conn.execute(
            "SELECT predicted_intent FROM utterances WHERE id = ?", (utterance_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"utterance_id {utterance_id} not found")
        predicted_intent: Optional[str] = row["predicted_intent"]

        self._conn.execute(
            "UPDATE utterances SET user_feedback = ?, correct_intent = ?, reward = ? "
            "WHERE id = ?",
            (feedback, correct_intent, reward, utterance_id),
        )

        # Threshold update: punish the predicted intent (if any), reward the
        # corrected one (if different and provided).
        if predicted_intent:
            self._apply_reward(predicted_intent, reward)
        if correct_intent and correct_intent != predicted_intent:
            self._apply_reward(correct_intent, +1)

    # ------------------------------------------------------------------ #
    #  Thresholds (the policy)                                            #
    # ------------------------------------------------------------------ #

    def get_threshold(self, intent: str) -> float:
        row = self._conn.execute(
            "SELECT accept_threshold FROM intent_thresholds WHERE intent = ?",
            (intent,),
        ).fetchone()
        if row is None:
            return DEFAULT_THRESHOLD
        return float(row["accept_threshold"])

    def get_intent_stats(self, intent: str) -> Optional[IntentThreshold]:
        row = self._conn.execute(
            "SELECT * FROM intent_thresholds WHERE intent = ?", (intent,)
        ).fetchone()
        if row is None:
            return None
        return IntentThreshold(
            intent=row["intent"],
            accept_threshold=row["accept_threshold"],
            sample_count=row["sample_count"],
            avg_reward=row["avg_reward"],
            updated_at=row["updated_at"],
        )

    def _apply_reward(self, intent: str, reward: int) -> None:
        cur = self.get_intent_stats(intent)
        if cur is None:
            avg = float(reward)
            count = 1
            threshold = DEFAULT_THRESHOLD
        else:
            avg = (1 - ALPHA) * cur.avg_reward + ALPHA * float(reward)
            count = cur.sample_count + 1
            threshold = cur.accept_threshold

        # Drift: only adjust threshold once we have a meaningful avg
        if avg < DRIFT_UP_REWARD_GATE:
            threshold = min(MAX_THRESHOLD, threshold + 0.02)
        elif avg > DRIFT_DOWN_REWARD_GATE and count >= DRIFT_DOWN_AFTER_SAMPLES:
            threshold = max(MIN_THRESHOLD, threshold - 0.01)

        now = datetime.now().isoformat(timespec="seconds")
        self._conn.execute(
            """
            INSERT INTO intent_thresholds (intent, accept_threshold, sample_count, avg_reward, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(intent) DO UPDATE SET
                accept_threshold = excluded.accept_threshold,
                sample_count     = excluded.sample_count,
                avg_reward       = excluded.avg_reward,
                updated_at       = excluded.updated_at
            """,
            (intent, round(threshold, 4), count, round(avg, 4), now),
        )

    # ------------------------------------------------------------------ #
    #  Pending patterns (active learning queue)                           #
    # ------------------------------------------------------------------ #

    def queue_low_confidence(
        self,
        utterance_id: Optional[int],
        raw_text: str,
        top3: list[tuple[str, float]],
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO pending_patterns (utterance_id, raw_text, top3_json, queued_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (
                utterance_id,
                raw_text,
                json.dumps(top3),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return int(cur.lastrowid)

    def pending_patterns(self) -> list[PendingPattern]:
        rows = self._conn.execute(
            "SELECT * FROM pending_patterns WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [self._row_to_pending(r) for r in rows]

    @staticmethod
    def _row_to_pending(row: sqlite3.Row) -> PendingPattern:
        try:
            top3 = json.loads(row["top3_json"]) if row["top3_json"] else []
        except json.JSONDecodeError:
            top3 = []
        return PendingPattern(
            id=row["id"],
            utterance_id=row["utterance_id"],
            raw_text=row["raw_text"],
            top3=top3,
            queued_at=row["queued_at"],
            status=row["status"],
        )

    def approve_pattern(self, pending_id: int, intent_name: str,
                        intents_json_path: str) -> bool:
        """Append the pending utterance to intents.json under `intent_name`,
        then mark the pending row approved. Returns False if intent unknown.

        The brain's k-NN index will rebuild on next boot because the
        intents.json hash changes.
        """
        row = self._conn.execute(
            "SELECT raw_text, status FROM pending_patterns WHERE id = ?",
            (pending_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"pending_id {pending_id} not found")
        if row["status"] != "pending":
            log.info(f"[Feedback] pending_id {pending_id} already {row['status']}.")
            return False
        raw_text: str = row["raw_text"]

        with open(intents_json_path, "r", encoding="utf-8") as f:
            intents = json.load(f)

        if intent_name not in intents:
            log.warning(f"[Feedback] intent {intent_name!r} not found in intents.json")
            return False

        patterns: list = intents[intent_name].setdefault("patterns", [])
        if raw_text not in patterns:
            patterns.append(raw_text)
            with open(intents_json_path, "w", encoding="utf-8") as f:
                json.dump(intents, f, indent=4, ensure_ascii=False)

        self._conn.execute(
            "UPDATE pending_patterns SET status = 'approved' WHERE id = ?",
            (pending_id,),
        )
        return True

    def skip_pattern(self, pending_id: int) -> None:
        self._conn.execute(
            "UPDATE pending_patterns SET status = 'skipped' WHERE id = ?",
            (pending_id,),
        )

    def reject_pattern(self, pending_id: int) -> None:
        self._conn.execute(
            "UPDATE pending_patterns SET status = 'rejected' WHERE id = ?",
            (pending_id,),
        )

    # ------------------------------------------------------------------ #
    #  Stats / dashboard                                                  #
    # ------------------------------------------------------------------ #

    def stats(self) -> dict:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM utterances").fetchone()
        n_utterances = int(row["n"])
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM pending_patterns WHERE status = 'pending'"
        ).fetchone()
        n_pending = int(row["n"])
        rows = self._conn.execute(
            "SELECT * FROM intent_thresholds ORDER BY intent"
        ).fetchall()
        thresholds = [
            {
                "intent": r["intent"],
                "threshold": round(r["accept_threshold"], 3),
                "samples": r["sample_count"],
                "avg_reward": round(r["avg_reward"], 3),
            }
            for r in rows
        ]
        return {
            "utterances_logged": n_utterances,
            "patterns_pending_review": n_pending,
            "intent_thresholds": thresholds,
        }


if __name__ == "__main__":
    import tempfile

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    tmp_db = os.path.join(tempfile.gettempdir(), "_jarvis_feedback_smoke.sqlite")
    if os.path.exists(tmp_db):
        os.remove(tmp_db)

    fb = FeedbackStore(tmp_db)

    print("== Initial threshold for unknown intent ==")
    print(f"  open_app threshold = {fb.get_threshold('open_app')}  (default)")

    print()
    print("== Simulate 10 successful executions of open_app ==")
    for i in range(10):
        uid = fb.log_utterance(
            raw_text="chrome kholo",
            normalized_text="chrome kholo",
            predicted_intent="open_app",
            confidence=0.92,
            top3=[("open_app", 0.85), ("close_app", 0.10), ("open_website", 0.05)],
            sentiment_label="neutral",
            sentiment_score=0.0,
            action_taken="executed",
        )
        fb.record_feedback(uid, "accepted")
    s = fb.get_intent_stats("open_app")
    print(f"  open_app -> threshold={s.accept_threshold}, samples={s.sample_count}, avg_reward={s.avg_reward}")
    assert s.accept_threshold < DEFAULT_THRESHOLD, "Expected threshold to drift DOWN after positives"

    print()
    print("== Simulate 3 corrections on play_music ==")
    for i in range(3):
        uid = fb.log_utterance(
            raw_text="random thing",
            normalized_text="random thing",
            predicted_intent="play_music",
            confidence=0.55,
            top3=[("play_music", 0.45), ("greet", 0.30), ("set_reminder", 0.25)],
            sentiment_label="neutral",
            sentiment_score=0.0,
            action_taken="executed",
        )
        fb.record_feedback(uid, "corrected", correct_intent="open_app")
    s = fb.get_intent_stats("play_music")
    print(f"  play_music -> threshold={s.accept_threshold}, samples={s.sample_count}, avg_reward={s.avg_reward}")
    assert s.accept_threshold > DEFAULT_THRESHOLD, "Expected threshold to drift UP after negatives"

    print()
    print("== Pending pattern queue ==")
    uid = fb.log_utterance(
        raw_text="bhai mujhe coffee chahiye",
        normalized_text="bhai mujhe coffee chahiye",
        predicted_intent=None,
        confidence=0.32,
        top3=[("greet", 0.32), ("create_note", 0.20), ("set_reminder", 0.18)],
        sentiment_label="neutral",
        sentiment_score=0.0,
        action_taken="chat_fallback",
    )
    pid = fb.queue_low_confidence(uid, "bhai mujhe coffee chahiye",
                                   [("greet", 0.32), ("create_note", 0.20), ("set_reminder", 0.18)])
    print(f"  queued pending_id={pid}")
    pending = fb.pending_patterns()
    print(f"  pending count: {len(pending)}")
    for p in pending:
        print(f"    [{p.id}] {p.raw_text!r}  top3={p.top3}")

    print()
    print("== Final stats ==")
    for k, v in fb.stats().items():
        print(f"  {k}: {v}")

    fb.close()
    print()
    print("Smoke OK.")
