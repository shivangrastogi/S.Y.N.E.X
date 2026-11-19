"""NLU + MEMORY tasks — the brain's "understanding" jobs, beside the normal TURN.

One model, three task heads chosen by the system prompt:

  TURN    (brain/prompt.py)  every conversation turn → the 5-type contract
  NLU     analyse one user message →
            {"intent":..,"act":..,"slots":[{"k":..,"v":..}],"keywords":[..],
             "lang":..,"sentiment":..,"emotion":..}
  MEMORY  read a short conversation → {"facts":[..]}: lasting things worth
            remembering, copied in the user's own words (or [] if none)

TURN stays lean (latency on the phone); the app calls NLU/MEMORY only when it
needs analysis (e.g. after a conversation, to update memory).

NLU targets are derived *exactly* from labelled data wherever possible: a TURN
record's tool call already says the intent and the slots. Sentiment/emotion for
commands is neutral by construction; for chat it comes from the teacher's
labels, checked against fixed label sets. Keywords are computed, not invented.
Stdlib only.
"""
from __future__ import annotations

import json
import re

from .contract import load_tools
from .langmix import lang_label

ACTS = ("command", "question", "statement", "social")
SENTIMENTS = ("positive", "neutral", "negative")
EMOTIONS = ("none", "happy", "excited", "grateful", "curious", "sad", "lonely", "stressed",
            "tired", "angry", "confused", "bored")
LANGS = ("english", "hinglish", "hindi_roman", "devanagari")

# Intents that aren't a tool: what the user wants when they're not commanding.
CHAT_INTENTS = (
    "chat.greeting", "chat.how_are_you", "chat.goodbye", "chat.thanks", "chat.about_aeris", "chat.smalltalk",
    "chat.joke", "chat.opinion", "chat.advice", "chat.support", "chat.compliment", "chat.complaint",
    "chat.affirm", "chat.deny", "question.knowledge", "question.live_info", "request.complex",
    "request.unsupported", "task.multi_app",
)
_ESC = {"knowledge": "question.knowledge", "live_info": "question.live_info",
        "complex": "request.complex", "no_tool": "request.unsupported"}


def intents(tools: dict | None = None) -> list[str]:
    tools = tools or load_tools()
    return list(tools) + list(CHAT_INTENTS)


# ── keywords: content words + slot spans (computed, never generated) ──────
_STOP = set("""a an the is am are was were be to of in on at for with and or but so it this that i me my you your he she
we they them his her our please can could would will just ok okay hey hi hello yaar bhai na naa hai hain ho hoon tha thi
the ka ki ke ko se mein me mai main kya kyun kaise kahan kab ye yeh wo woh aur ya par pe to toh bhi hi bas abhi zara
karo kar karna karne do de dena lo le lena raha rahi rahe gaya gayi gaye mujhe mera meri mere tum tera tumhara aap aapka
jo jab tab agar haan nahi nahin mat koi kuch sab ek do""".split())
_WORD = re.compile(r"[A-Za-z][A-Za-z']+|\d[\d:.]*")


def keywords(text: str, spans: list[str] = (), k: int = 6) -> list[str]:
    """Slot spans first (whole), then distinct content words in order."""
    out, seen = [], set()
    for s in spans:
        if s and s.lower() not in seen:
            out.append(s)
            seen.add(s.lower())
            seen.update(w.lower() for w in s.split())
    for w in _WORD.findall(text or ""):
        lw = w.lower()
        if lw in _STOP or lw in seen or len(lw) < 3 and not lw[0].isdigit():
            continue
        out.append(w)
        seen.add(lw)
    return out[:k]


def _act_for(text: str, intent: str) -> str:
    if intent in ("chat.greeting", "chat.goodbye", "chat.thanks", "chat.how_are_you", "chat.compliment"):
        return "social"
    if intent.startswith("question.") or text.rstrip().endswith("?"):
        return "question"
    if "." not in intent:  # a tool
        return "command"
    return "statement"


def canonical(nlu: dict) -> str:
    order = ["intent", "act", "slots", "keywords", "lang", "sentiment", "emotion"]
    return json.dumps({k: nlu[k] for k in order if k in nlu}, ensure_ascii=False, separators=(",", ":"))


def from_turn(record: dict, tools: dict | None = None) -> list[dict]:
    """NLU records from a labelled TURN record: one per user turn whose next
    assistant turn reveals the intent (tool_call / ask / escalate / plan)."""
    tools = tools or load_tools()
    msgs = record.get("messages", [])
    out = []
    for i, m in enumerate(msgs[:-1]):
        if m["role"] != "user" or msgs[i + 1]["role"] != "assistant":
            continue
        text, a = m["content"], msgs[i + 1]["content"]
        t = a.get("type")
        slots: list[dict] = []
        if t == "tool_call" and len(a["calls"]) == 1:
            call = a["calls"][0]
            intent = call["name"]
            for k, v in call["args"].items():
                if isinstance(v, str) and v.lower() in text.lower():
                    slots.append({"k": k, "v": v})
        elif t == "ask" and a.get("pending") in tools:
            intent = a["pending"]
        elif t == "escalate":
            intent = _ESC.get(a.get("reason"), "question.knowledge")
        elif t == "plan":
            intent = "task.multi_app"
        else:
            continue  # replies get NLU from teacher labels (sentiment/emotion matter there)
        nlu = {"intent": intent, "act": _act_for(text, intent), "slots": slots,
               "keywords": keywords(text, [s["v"] for s in slots]), "lang": lang_label(text),
               "sentiment": "neutral", "emotion": "none"}
        out.append({"task": "nlu", "id": f"{record.get('id', 'r')}-nlu{i}", "source": f"{record.get('source', '?')}>nlu",
                    "split": record.get("split", "train"), "lang": record.get("lang"), "text": text, "nlu": nlu})
    return out


def make_nlu(text: str, intent: str, sentiment: str, emotion: str, *, source: str, rid: str,
             split: str = "train", slots: list[dict] | None = None) -> dict:
    nlu = {"intent": intent, "act": _act_for(text, intent), "slots": slots or [],
           "keywords": keywords(text, [s["v"] for s in slots or []]), "lang": lang_label(text),
           "sentiment": sentiment, "emotion": emotion}
    return {"task": "nlu", "id": rid, "source": source, "split": split, "text": text, "nlu": nlu}


def validate_nlu(rec: dict, known_intents: set[str]) -> list[str]:
    n, text = rec.get("nlu") or {}, rec.get("text") or ""
    errs = []
    if n.get("intent") not in known_intents:
        errs.append(f"unknown intent {n.get('intent')!r}")
    if n.get("act") not in ACTS:
        errs.append("bad act")
    if n.get("sentiment") not in SENTIMENTS:
        errs.append("bad sentiment")
    if n.get("emotion") not in EMOTIONS:
        errs.append("bad emotion")
    if n.get("lang") not in LANGS:
        errs.append("bad lang")
    for s in n.get("slots", []):
        if not isinstance(s, dict) or s.get("v", "").lower() not in text.lower():
            errs.append(f"slot not a span: {s}")
    for kw in n.get("keywords", []):
        if kw.lower() not in text.lower():
            errs.append(f"keyword not in text: {kw}")
    return errs


# ── memory extraction ─────────────────────────────────────────────────────
def make_memory(user_turns: list[str], facts: list[str], *, source: str, rid: str, split: str = "train") -> dict:
    return {"task": "memory", "id": rid, "source": source, "split": split, "turns": user_turns, "facts": facts}


def validate_memory(rec: dict) -> list[str]:
    joined = " ".join(rec.get("turns", [])).lower()
    return [f"fact not in user's words: {f}" for f in rec.get("facts", []) if f.lower() not in joined]


# ── prompts for the two analysis heads (phone must render identically) ────
def nlu_system(tools: dict | None = None) -> str:
    return ("You are AERIS's understanding module. Analyse the user's message (English, Hinglish or Hindi).\n"
            "Answer with ONE JSON object: "
            '{"intent":INTENT,"act":"command|question|statement|social","slots":[{"k":ARG,"v":EXACT_WORDS}],'
            '"keywords":[WORDS],"lang":"english|hinglish|hindi_roman|devanagari",'
            '"sentiment":"positive|neutral|negative","emotion":"' + "|".join(EMOTIONS) + '"}\n'
            "Copy slot values and keywords exactly from the message.\n"
            "Intents: " + ", ".join(intents(tools)))


MEMORY_SYSTEM = ("You are AERIS's memory module. Read what the user said and list lasting personal facts worth "
                 "remembering (names, places, dates, preferences, where things are kept, routines). Copy each fact "
                 "exactly from the user's words. Ignore small talk and one-off commands.\n"
                 'Answer with ONE JSON object: {"facts":[FACT,...]} — use [] if there is nothing to remember.')


def chat_messages(rec: dict, tools: dict | None = None) -> list[dict]:
    """System/user/assistant messages for an NLU or MEMORY record (render.py uses this)."""
    if rec["task"] == "nlu":
        return [{"role": "system", "content": nlu_system(tools)},
                {"role": "user", "content": rec["text"]},
                {"role": "assistant", "content": canonical(rec["nlu"])}]
    transcript = "\n".join(f"User: {t}" for t in rec["turns"])
    return [{"role": "system", "content": MEMORY_SYSTEM},
            {"role": "user", "content": transcript},
            {"role": "assistant", "content": json.dumps({"facts": rec["facts"]}, ensure_ascii=False,
                                                        separators=(",", ":"))}]
