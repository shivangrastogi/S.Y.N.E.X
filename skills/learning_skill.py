"""Voice/chat access to the continual-learning loop.

"kya seekha tumne" — AERIS apni learning ka hisaab deta hai: kitne naye
phrases usage se seekhe, retrain due hai ya nahi, brain health score kya
hai, kaunsa intent confuse ho raha hai.

Read-only by design: harvest/train yahan se trigger NAHI hota (wo
deliberate CLI ritual hai — ``python -m core.retrain``) — bolne se sirf
status milta hai, side effects nahi.

Examples:
    "kya seekha tumne"        -> learning_status
    "learning status"         -> learning_status
    "retrain due hai kya"     -> learning_status
    "brain health"            -> brain_health
    "apni accuracy batao"     -> brain_health
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="learning_status",
    description="Report what AERIS has learned from usage and whether a retrain is due.",
    patterns=[
        "learning status", "learning report", "learning loop status",
        "kya seekha", "kya seekha tumne", "naya kya seekha",
        "kitna seekh liya", "kitna seekha ab tak",
        "what did you learn", "what have you learned",
        "retrain status", "retrain due hai kya", "training status",
    ],
    required_entities=[],
)
def learning_status(slots: dict) -> str:
    try:
        from core.learning_loop import LearningStore, RETRAIN_ADVICE_AT
        s = LearningStore().status()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[learning_status] failed: %s", e)
        return "Learning store abhi read nahi ho paya, sir."

    if not s["total_samples"]:
        return ("Abhi tak usage se kuch naya nahi seekha, sir. Jaise-jaise aap "
                "commands use karenge, main phrases apne aap jama karta jaunga.")

    parts = [f"Ab tak maine usage se {s['trainable_samples']} naye phrases "
             f"seekhe hain, sir"]
    top = sorted(s["by_intent"].items(), key=lambda kv: -kv[1])[:3]
    if top:
        parts.append("sabse zyada " +
                     ", ".join(f"{k.replace('_', ' ')} ({v})" for k, v in top))
    if s["review_samples"]:
        parts.append(f"{s['review_samples']} review mein hain")
    msg = ". ".join([", ".join(parts)]) + "."
    if s["retrain_recommended"]:
        msg += (f" {s['new_since_last_train']} naye samples jama ho gaye hain — "
                "retrain due hai. Terminal se `python -m core.retrain` "
                "chala dijiye.")
    else:
        need = max(0, RETRAIN_ADVICE_AT - s["new_since_last_train"])
        msg += f" Retrain abhi due nahi — {need} aur samples pe recommend karunga."
    return msg


@skill(
    name="brain_health",
    description="AERIS's brain health report: router state, accuracy, generation trend, retrain advice.",
    patterns=[
        "brain health", "brain report", "brain ki health", "brain score",
        "brain ka report card", "model health", "health report",
        "dimaag kaisa hai", "how smart are you",
        "accuracy kya hai", "apni accuracy batao", "brain kitna accurate hai",
        "report card dikhao",
    ],
    required_entities=[],
)
def brain_health(slots: dict) -> str:
    try:
        from core.brain_health import collect, speak_summary
        r = collect(window_days=30)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[brain_health] failed: %s", e)
        return "Brain health report abhi nahi bana paya, sir."

    msg = speak_summary(r)
    if r.confusion_pairs:
        c = r.confusion_pairs[0]
        msg += (f" Sabse zyada confusion {c['from'].replace('_', ' ')} aur "
                f"{c['to'].replace('_', ' ')} ke beech hai.")
    return msg
