"""Dialogue context — the memory BETWEEN turns that makes AERIS conversational.

Before this module, every utterance was understood in isolation: the brain
got zero knowledge of the previous turn, so natural follow-ups failed:

    "open chrome"          → open_app(chrome)          ✔
    "ab isko band karo"    → close_app(???)            ✘ asks "kaunsa app?"

    "weather in mumbai"    → weather_for_city(mumbai)  ✔
    "aur delhi ka?"        → low confidence            ✘ "samajh nahi paaya"

Two mechanisms fix this, both HIGH-PRECISION by design (a wrong guess is
worse than a clarifying question):

1. **Pronoun entity injection** (`ContextResolver.inject`)
   When the classified intent needs a slot the extractor couldn't find,
   AND the utterance contains a pronoun (isko / usko / it / this ...),
   AND the previous turn produced a compatible entity — fill the slot
   from context instead of asking.

2. **Elliptical follow-up rescue** (`ContextResolver.followup_intent`)
   When the brain is UNSURE about a short verb-less segment, but the
   segment carries an entity of a type the previous intent used —
   re-issue the previous intent with the swapped entity.

Both are consulted from ``JarvisMainEngine._process_segment`` and apply
identically to typed and spoken input (they share that path).

The state is deliberately small and in-RAM: conversation context is a
*working* memory measured in minutes, unlike the knowledge graph /
semantic memory which persist facts. ``FRESH_WINDOW_S`` makes stale
context expire so "isko band karo" an hour later never closes the wrong
app.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

# Context older than this is never used for resolution. Conversational
# follow-ups happen within seconds; three minutes is already generous.
FRESH_WINDOW_S = 180.0

# Slots that can sensibly carry across turns. Times, amounts and free-form
# message bodies must never leak from a previous command into a new one.
CARRYABLE_SLOTS = {"app_name", "city", "query", "url", "person", "topic"}

# Pronoun cues (English + Hinglish). NOTE: "use"/"is"/"us" are excluded on
# purpose — they collide with common English words ("use chrome",
# "is it raining", "tell us") and precision beats recall here.
_PRONOUNS = {
    "it", "this", "that", "these", "those", "them",
    "isko", "usko", "ise", "isse", "usse", "isey", "usey",
    "yeh", "ye", "woh", "wo", "inko", "unko", "iska", "uska",
}

# A follow-up segment must be SHORT and verb-less. If any of these action
# verbs appear, the user is issuing a fresh command, not an ellipsis.
_ACTION_VERBS = {
    "open", "close", "kholo", "band", "karo", "chalao", "play", "stop",
    "set", "start", "kill", "launch", "search", "find", "show", "batao",
    "sunao", "bolo", "likho", "add", "create", "delete", "remove", "mute",
    "lock", "snap", "maximize", "minimize", "screenshot", "translate",
}

_WORD_RE = re.compile(r"[a-zA-Zऀ-ॿ]+")


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def has_pronoun(text: str) -> bool:
    return any(t in _PRONOUNS for t in _tokens(text))


def _is_destructive(intent: Optional[str]) -> bool:
    """Would acting on a guessed target here be irreversible?

    Imported lazily and defensively: this module is deliberately dependency-
    free (pure stdlib) so it stays trivially testable, and a missing
    `confirm_gate` must not disable pronoun resolution entirely. Failing
    *closed* would be worse than the bug this guards — so on error we fall
    back to "not destructive" and the existing confirm gate still stands
    between the user and the action.
    """
    if not intent:
        return False
    try:
        from core.confirm_gate import needs_confirmation
        return bool(needs_confirmation(intent))
    except Exception as e:  # pragma: no cover - defensive
        log.debug("[context] destructive check unavailable: %s", e)
        return False


def looks_elliptical(text: str) -> bool:
    """Short, verb-less fragment — the shape of a follow-up.

    "aur delhi ka?" ✔   "what about tomorrow" ✔
    "open notepad"  ✘ (verb)   "search ai in brave" ✘ (verb + long)
    """
    toks = _tokens(text)
    if not toks or len(toks) > 5:
        return False
    return not any(t in _ACTION_VERBS for t in toks)


@dataclass
class DialogueState:
    """Rolling record of the most recent *executed* turn."""

    last_intent: Optional[str] = None
    last_entities: dict = field(default_factory=dict)
    last_user_text: str = ""
    last_reply: str = ""
    ts: float = 0.0

    def note(self, intent: str, entities: dict, user_text: str,
             reply: str = "") -> None:
        """Record an executed turn. Internal keys (raw_text etc.) are
        stripped so only real slots participate in resolution."""
        self.last_intent = intent
        self.last_entities = {
            k: v for k, v in (entities or {}).items()
            if k in CARRYABLE_SLOTS and v
        }
        self.last_user_text = user_text or ""
        self.last_reply = reply or ""
        self.ts = time.monotonic()

    def note_reply(self, reply: str) -> None:
        """Update just the last spoken reply (recall/memory turns)."""
        self.last_reply = reply or ""

    def fresh(self, window_s: float = FRESH_WINDOW_S) -> bool:
        return self.last_intent is not None and \
            (time.monotonic() - self.ts) <= window_s


class ContextResolver:
    """Pure logic — no engine references, fully unit-testable."""

    def __init__(self, state: Optional[DialogueState] = None):
        self.state = state or DialogueState()

    # ── 1. pronoun → entity injection ────────────────────────────────
    def inject(self, entities: dict, intent: str,
               required: list[str], text: str) -> dict:
        """Fill missing required slots from context when the utterance
        points at them with a pronoun. Mutates + returns ``entities``.

        **Never injects into a destructive intent.** This module's rule is
        that a wrong guess is worse than a clarifying question, and that is
        most true when the action cannot be undone: "isko delete kar do"
        resolving its target from a pronoun and the previous turn means an
        irreversible action aimed by inference. Asking "kaunsa?" costs a
        sentence; guessing costs the file.

        (``intent`` was accepted and ignored until 2026-09-01 — the parameter
        was there, the check was not. See §6.34.)
        """
        if not self.state.fresh() or not required:
            return entities
        if not has_pronoun(text):
            return entities
        if _is_destructive(intent):
            log.info("[context] refusing pronoun-injection into destructive "
                     "intent %r — asking instead", intent)
            return entities
        for slot in required:
            if entities.get(slot):
                continue                      # extractor already found it
            if slot not in CARRYABLE_SLOTS:
                continue                      # never carry time/amount/body
            carried = self.state.last_entities.get(slot)
            if carried:
                entities[slot] = carried
                entities["_context_injected"] = slot
                log.info("[context] injected %s=%r from previous turn "
                         "(pronoun in %r)", slot, carried, text)
        return entities

    # ── 2. elliptical follow-up rescue ───────────────────────────────
    def followup_intent(self, text: str, brain_confident: bool,
                        new_entities: dict) -> Optional[tuple[str, dict]]:
        """If ``text`` looks like an ellipsis of the previous turn,
        return (last_intent, merged_entities); else None.

        ``new_entities`` must be the extractor's output for ``text``
        run against the PREVIOUS intent (the caller does that pass).
        Only fires when the brain itself was NOT confident — a confident
        classification always wins over context guessing.
        """
        if brain_confident or not self.state.fresh():
            return None
        if not looks_elliptical(text):
            return None
        swapped = {
            k: v for k, v in (new_entities or {}).items()
            if k in CARRYABLE_SLOTS and v
            and v != self.state.last_entities.get(k)
        }
        if not swapped:
            return None                       # nothing new to swap in
        merged = dict(self.state.last_entities)
        merged.update(swapped)
        merged["_context_followup"] = self.state.last_intent
        log.info("[context] follow-up %r → repeat %s with %s",
                 text, self.state.last_intent, swapped)
        return self.state.last_intent, merged


# Object pronouns that may be textually REWRITTEN to the context entity
# before classification. Subset of _PRONOUNS: only forms that grammatically
# stand in for the object ("isko band karo", "close it"), never subject/
# question forms ("yeh kya hai" must NOT become "notepad kya hai" — hence
# yeh/ye/woh/wo are excluded).
_REWRITE_PRONOUNS = {
    "it", "isko", "usko", "ise", "isse", "usse", "isey", "usey",
    "inko", "unko",
}


def rewrite_pronoun(text: str, state: DialogueState) -> Optional[str]:
    """Substitute an object pronoun with the previous turn's entity BEFORE
    the brain classifies, so routing itself lands on the right intent.

    Real failure this fixes: after "open notepad", the utterance
    "ab isko band karo" classified confidently as tab_close (a blind
    Ctrl+W at the focused window!) instead of close_app(notepad). Slot
    injection can't help when the wrong intent needs no slots — the
    text itself must carry the referent.

    Guards (all must hold):
      * context fresh + previous turn produced exactly ONE carryable entity
      * the text contains an ACTION verb (commands only; questions like
        "yeh kya hai" are never rewritten)
      * exactly one rewritable pronoun token in the text
    Returns the rewritten text, or None if any guard fails.
    """
    if not state.fresh():
        return None
    carried = [v for k, v in state.last_entities.items() if v]
    if len(carried) != 1:
        return None                    # ambiguous or no referent
    toks = _tokens(text)
    if not any(t in _ACTION_VERBS for t in toks):
        return None                    # not a command
    hits = [t for t in toks if t in _REWRITE_PRONOUNS]
    if len(hits) != 1:
        return None
    pattern = re.compile(r"\b" + re.escape(hits[0]) + r"\b", re.IGNORECASE)
    rewritten = pattern.sub(str(carried[0]), text, count=1)
    if rewritten == text:
        return None
    log.info("[context] pronoun rewrite: %r → %r", text, rewritten)
    return rewritten


# ── elliptical analogy rewrite ───────────────────────────────────────
# Filler tokens stripped from a follow-up fragment to isolate its payload:
# "aur delhi ka?" → payload "delhi".
_FILLERS = {
    "aur", "and", "or", "ya", "ka", "ki", "ke", "ko", "me", "mein",
    "what", "whats", "about", "how", "kya", "kaisa", "kaisi", "wala",
    "for", "in", "at", "of", "the", "a", "an", "batao", "bhi",
}
# Payloads that are chit-chat, never referents — hard stoplist.
_CHITCHAT = {
    "thanks", "thank", "shukriya", "dhanyavad", "ok", "okay", "yes", "no",
    "haan", "nahi", "hello", "hi", "hey", "bye", "good", "nice", "great",
    "hmm", "acha", "accha", "theek", "hai", "sahi", "wow", "cool",
}
# A fragment must contain one of these follow-up markers (or end in '?')
# to qualify — "thank you" has none and is never treated as a follow-up.
_MARKERS = {"aur", "and", "or", "ya", "about", "ka", "ki", "ke", "wala"}


def analogy_rewrite(text: str, state: DialogueState) -> Optional[str]:
    """Rebuild an elliptical follow-up as a FULL utterance by substituting
    its payload into the previous turn's text:

        prev:  "weather in mumbai"   (city=mumbai)
        text:  "aur delhi ka?"       → payload "delhi"
        out:   "weather in delhi"

    The rewritten sentence re-enters the normal pipeline, so this works
    for every skill regardless of whether it reads slots or parses the
    raw text itself. Returns None unless ALL guards pass.
    """
    if not state.fresh() or not state.last_user_text:
        return None
    if not looks_elliptical(text):
        return None
    toks = _tokens(text)
    stripped = (text or "").strip()
    if not (any(t in _MARKERS for t in toks) or stripped.endswith("?")):
        return None                          # no follow-up shape
    payload = [t for t in toks if t not in _FILLERS]
    if not payload or len(payload) > 3:
        return None
    if any(t in _CHITCHAT for t in payload):
        return None
    if any(t in _PRONOUNS for t in payload):
        return None                          # pronouns are rewrite_pronoun's job
    payload_str = " ".join(payload)

    # Find the span in the previous utterance being swapped out.
    # Preferred anchor: an entity value the extractor recorded. Fallback
    # (extractor found nothing — common for city/query slots): the
    # trailing prepositional object of the previous sentence, e.g.
    # "weather IN MUMBAI" / "search FOR AI NEWS" / "MUMBAI ka mausam".
    prev = state.last_user_text
    prev_low = prev.lower()
    anchors: list[str] = [
        str(v).lower() for v in state.last_entities.values()
        if v and str(v).lower() in prev_low
    ]
    if not anchors:
        m = re.search(r"\b(?:in|for|at|of)\s+([a-z][a-z\s.\-']{0,30})\s*[?.!]*\s*$",
                      prev_low)
        if m:
            anchors.append(m.group(1).strip())
        else:
            m = re.search(r"^\s*([a-z][a-z\s.\-']{0,30}?)\s+(?:ka|ki|ke|mein|me)\b",
                          prev_low)
            if m:
                anchors.append(m.group(1).strip())
    for ov in anchors:
        if ov and ov != payload_str:
            idx = prev_low.index(ov)
            rewritten = prev[:idx] + payload_str + prev[idx + len(ov):]
            log.info("[context] analogy rewrite: %r + %r → %r",
                     prev, text, rewritten)
            return rewritten
    return None


# ── chit-chat gate ───────────────────────────────────────────────────
# Conversational markers that essentially never appear in device commands:
# emotions, opinions, address terms, questions about the assistant itself.
# Measured on this brain (k-NN only, neural inactive): commands score
# 0.77–1.00, chit-chat 0.49–0.85 — overlapping zones, so confidence alone
# cannot separate them. These markers can: an utterance carrying one must
# clear a HIGH confidence bar (0.90) to dispatch a skill; otherwise it
# belongs to the conversation fallback (embedded LLM).
_CHAT_MARKERS = {
    # address / vibe
    "yaar", "bro", "dost", "buddy",
    # feelings & states
    "feel", "feeling", "bored", "boring", "sad", "lonely", "tired",
    "thak", "thaka", "pareshan", "tension", "stress", "stressed",
    "happy", "khush", "udaas", "mann",
    # opinion / reflection
    "khayal", "opinion", "soch", "sochta", "sochti", "zindagi",
    "motivate", "motivation", "interesting",
    # about the assistant
    "tumhe", "tumhara", "tumhari", "tera", "teri", "tujhe", "tum",
    # conversational openers / asks
    "suna", "kahani", "story", "joke", "chutkula",
}
_CHAT_BIGRAMS = (
    "how are you", "kaise ho", "kaisa lag", "meaning of", "kya karoon",
    "kya karu", "tell me something", "kuch batao", "do you", "are you",
    "can you feel", "what do you think",
)

# Skill dispatch bar for chat-flagged utterances. Exact-match (1.0) and
# very confident classifications still win — "mood today" stays a skill.
CHAT_GATE_CONFIDENCE = 0.90


def is_chatty(text: str) -> bool:
    """True when the utterance reads as conversation, not a command."""
    if not text:
        return False
    low = f" {text.strip().lower()} "
    if any(f" {m} " in low or low.strip().startswith(m + " ")
           for m in _CHAT_MARKERS):
        return True
    return any(b in low for b in _CHAT_BIGRAMS)


# "What did you (just) say?" — answer from the last reply, no skill needed.
_SAY_AGAIN = {
    "what did you say", "what did you just say", "say that again",
    "kya bola", "kya bola tumne", "kya kaha", "kya kaha tumne",
    "phir se bolo", "dobara bolo", "wapas bolo", "repeat that",
}


def say_again_reply(text: str, state: DialogueState) -> Optional[str]:
    t = (text or "").strip().lower().rstrip("?!. ")
    if t in _SAY_AGAIN and state.last_reply:
        return state.last_reply
    return None
