"""Teacher-model jobs (run in Colab with an OPEN-WEIGHT model, e.g. Qwen3-14B
or Gemma 3/4 27B via vLLM — never Gemini/GPT outputs, see plan §6.5).

Three jobs, each = prompt builder + strict verifier. The teacher only adds
variety; nothing it writes is trusted until the verifier passes it.

  paraphrase      more natural ways to say a command, KEEPING every labelled
                  span verbatim (names, numbers, message text, times)
  hinglish_chat   turn an English small-talk conversation into natural
                  romanised Hinglish with short, spoken AERIS replies
  judge           1-5 score for "a real Indian user would say this" +
                  "the label is right"; keep ≥ 4

    jobs = paraphrase_jobs(records, per_record=3, rng=rng)
    outs = generate([j.prompt for j in jobs])         # vLLM, batched
    new  = [r for j, o in zip(jobs, outs) for r in j.accept(o)]
"""
from __future__ import annotations

import copy
import json
import random
import re
from dataclasses import dataclass
from typing import Callable

from .contract import norm_text

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_JSON_LIST = re.compile(r"\[.*\]", re.S)


def _json_list(text: str):
    m = _JSON_LIST.search(text or "")
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return v if isinstance(v, list) else None


@dataclass
class Job:
    prompt: str
    accept: Callable[[str], list[dict]]


# ── paraphrase ─────────────────────────────────────────────────────────────
PARAPHRASE = """You help build training data for a voice assistant used in India.
Rewrite the user's voice command {n} different ways, the way a real person would SAY it out loud to their phone.
Style: {style}
Hard rules:
- Keep EVERY one of these phrases EXACTLY as written (same spelling, same words): {spans}
- Same request, same meaning — do not add or remove details.
- Spoken style: casual, may include fillers ("yaar", "please", "can you"), no emojis.
Command: "{text}"
Answer with ONLY a JSON list of {n} strings."""

STYLE = {"en": "Indian English (casual, may be slightly ungrammatical)",
         "hi": "Hinglish — Hindi written in English letters, mixed with English words. NEVER Devanagari."}


def spans_of(record: dict) -> list[str]:
    out = []
    for m in record["messages"]:
        if m["role"] == "assistant":
            for c in m["content"].get("calls", []):
                out += [v for v in c["args"].values() if isinstance(v, str)]
    return out


def paraphrase_jobs(records, per_record: int = 3, rng: random.Random | None = None) -> list[Job]:
    """Single-turn tool_call records only (multi-turn context is fragile)."""
    rng = rng or random.Random(1)
    jobs = []
    for r in records:
        msgs = r["messages"]
        if len(msgs) != 2 or msgs[1]["content"].get("type") != "tool_call":
            continue
        text, spans = msgs[0]["content"], spans_of(r)
        lang = r.get("lang") or "en"
        prompt = PARAPHRASE.format(n=per_record, style=STYLE.get(lang, STYLE["en"]),
                                   spans=json.dumps(spans, ensure_ascii=False) if spans else "(none)",
                                   text=text)

        def accept(out, r=r, text=text, spans=spans):
            lst = _json_list(out) or []
            seen, keep = {norm_text(text)}, []
            for i, p in enumerate(lst):
                if not isinstance(p, str) or not (3 <= len(p) <= 220):
                    continue
                n = norm_text(p)
                if n in seen or _DEVANAGARI.search(p):
                    continue
                if any(norm_text(s) not in n for s in spans):
                    continue  # a label span changed → the target would be wrong
                seen.add(n)
                new = copy.deepcopy(r)
                new["id"] = f"{r['id']}-para{i}"
                new["source"] = f"{r.get('source', 'template')}+paraphrase"
                new["messages"][0]["content"] = p.strip()
                new.setdefault("meta", {})["paraphrase_of"] = r["id"]
                keep.append(new)
            return keep
        jobs.append(Job(prompt, accept))
    return jobs


# ── Hinglish small talk from English conversations ─────────────────────────
HINGLISH_CHAT = """Rewrite this chat between a user and a voice assistant called AERIS into natural romanised Hinglish
(Hindi in English letters mixed with English, like Indians text — e.g. "kya plan hai aaj?", "haan yaar, chalo").
Rules:
- Keep the same number of turns, same speakers, same meaning.
- AERIS replies are SPOKEN aloud: at most 2 short sentences, friendly, no lists, no markdown, no emojis.
- Never use Devanagari script.
Chat (JSON list of [speaker, text]):
{turns}
Answer with ONLY the rewritten JSON list of [speaker, text] pairs."""


def hinglish_chat_jobs(records) -> list[Job]:
    jobs = []
    for r in records:
        turns = [["user" if m["role"] == "user" else "aeris",
                  m["content"] if m["role"] == "user" else m["content"]["text"]]
                 for m in r["messages"]]
        if any(m["role"] == "assistant" and m["content"].get("type") != "reply" for m in r["messages"]):
            continue

        def accept(out, r=r, turns=turns):
            lst = _json_list(out)
            if not lst or len(lst) != len(turns):
                return []
            msgs = []
            for (spk, _), item in zip(turns, lst):
                if not (isinstance(item, list) and len(item) == 2 and isinstance(item[1], str)):
                    return []
                t = item[1].strip()
                if not t or _DEVANAGARI.search(t) or "*" in t or "\n" in t:
                    return []
                if spk == "aeris" and (len(t) > 260 or t.count(".") > 3):
                    return []
                msgs.append({"role": "user", "content": t} if spk == "user"
                            else {"role": "assistant", "content": {"type": "reply", "text": t}})
            new = copy.deepcopy(r)
            new.update(id=f"{r['id']}-hing", source=f"{r.get('source')}+hinglish", lang="hi",
                       prompt_lang="hinglish", messages=msgs)
            return [new]
        jobs.append(Job(HINGLISH_CHAT.format(turns=json.dumps(turns, ensure_ascii=False)), accept))
    return jobs


# ── judge ──────────────────────────────────────────────────────────────────
JUDGE = """You check training data for an Indian voice assistant.
User said: "{text}"
The assistant's decision: {target}
Score 1-5:
 naturalness — would a real Indian user plausibly say this to their phone (English or Hinglish)?
 correctness — is the decision exactly right (right tool, right details copied from the user's words; or right to ask/answer/escalate)?
Answer with ONLY JSON: {{"naturalness": n, "correctness": n}}"""


def judge_jobs(records, threshold: int = 4) -> list[Job]:
    jobs = []
    for r in records:
        if len(r["messages"]) != 2:
            continue
        prompt = JUDGE.format(text=r["messages"][0]["content"],
                              target=json.dumps(r["messages"][1]["content"], ensure_ascii=False))

        def accept(out, r=r):
            m = re.search(r"\{.*\}", out or "", re.S)
            try:
                s = json.loads(m.group(0)) if m else {}
            except json.JSONDecodeError:
                s = {}
            nat, cor = s.get("naturalness", 0), s.get("correctness", 0)
            if isinstance(nat, (int, float)) and isinstance(cor, (int, float)) and min(nat, cor) >= threshold:
                kept = copy.deepcopy(r)
                kept.setdefault("meta", {})["judge"] = {"naturalness": nat, "correctness": cor}
                return [kept]
            return []
        jobs.append(Job(prompt, accept))
    return jobs


# ── chat from scratch: one diversity grid cell → one conversation ──────────
# Brain v2 (docs/AERIS_BRAIN_V2.md). The cell fixes persona / topic / register /
# code-mix / mood / length / turns, so the teacher can't collapse onto one style.
# One response yields three kinds of records: a TURN conversation, an NLU record
# per user turn (teacher's intent/sentiment/emotion, checked against fixed sets;
# keywords + lang computed locally) and a MEMORY-extraction record.
from .diversity import Cell  # noqa: E402
from .langmix import lang_label, mix_bucket  # noqa: E402
from .nlu import CHAT_INTENTS, EMOTIONS, SENTIMENTS, make_memory, make_nlu  # noqa: E402

# First-person feminine forms — AERIS's voice is male, its words must agree.
FEMININE_SELF = re.compile(
    r"\b(rahi|sakti|karti|chalti|jaati|aati|deti|leti|samajhti|sochti|janti|jaanti) (hoon|hu|hun)\b"
    r"|\b(karungi|jaungi|dungi|lungi|bataungi|sunaungi|rahungi|sakungi|chahungi|bolungi)\b", re.I)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_LIVE = ("weather", "score", "news", "price", "status")

CHAT_GRID = """You write realistic chat data for AERIS — a MALE voice assistant on an Indian user's phone.
User: {persona}. Mood right now: {mood}. Topic: {topic}.
How the user writes: {register}; language: {mix_desc}; {length}.
Write {turns} user turn(s), each followed by AERIS's reply.{escalate_rule}
AERIS rules:
- Male: in Hindi always "raha hoon", "sakta hoon", "karunga" — never "rahi", "sakti", "karungi".
- Replies are SPOKEN aloud: 1-2 short sentences, warm and natural, matching the user's language mix and register.
- No lists, no markdown, no emojis. No invented facts, numbers or prices — if unsure, say so briefly.
- Hindi words in English letters only. Never Devanagari.
For EACH user turn also label:
  intent: one of {intents}
  sentiment: positive | neutral | negative
  emotion: one of {emotions}
If the user states a lasting personal fact (a name, date, place, preference, routine), copy it word for word into "facts".
Answer with ONLY JSON:
{{"turns":[{{"user":"...","intent":"...","sentiment":"...","emotion":"...","aeris":"..."}}],"facts":[]}}"""

ESCALATE_RULE = ("\nThe LAST user turn must ask about the topic itself (it needs live or expert information AERIS "
                 "can't know offline) — set that turn's \"aeris\" to null; AERIS's other replies are normal.")


def _reason(topic: str) -> str:
    t = topic.lower()
    return "live_info" if any(k in t for k in _LIVE) else "knowledge"


def _bad_aeris(t: str) -> bool:
    return (not t or len(t) > 230 or "\n" in t or "*" in t or "#" in t or _DEVANAGARI.search(t)
            or _EMOJI.search(t) or FEMININE_SELF.search(t) or t.count(".") + t.count("?") + t.count("!") > 3)


def _mix_ok(user: str, mix: str) -> bool:
    b = mix_bucket(user)
    if b == "deva":
        return False
    if mix == "english":
        return b in ("en", "en_heavy")
    if mix == "hi_heavy":
        return b in ("balanced", "hi_heavy")
    return True  # en_heavy / balanced: short messages wobble between neighbours


def chat_grid_jobs(cells: list[Cell], *, start_id: int = 0, split: str = "train") -> list[Job]:
    jobs = []
    for k, cell in enumerate(cells):
        rid = f"chat-{split}-{start_id + k:07d}"
        prompt = CHAT_GRID.format(
            persona=cell.persona, mood=cell.mood, topic=cell.topic, register=cell.register,
            mix_desc=cell.mix_desc, length=cell.length, turns=cell.turns,
            escalate_rule=ESCALATE_RULE if cell.expect == "escalate" else "",
            intents=" | ".join(i for i in CHAT_INTENTS if i not in ("task.multi_app",)),
            emotions=" | ".join(EMOTIONS))

        def accept(out, cell=cell, rid=rid):
            m = re.search(r"\{.*\}", out or "", re.S)
            try:
                d = json.loads(m.group(0)) if m else None
            except json.JSONDecodeError:
                d = None
            if not isinstance(d, dict) or not isinstance(d.get("turns"), list) or len(d["turns"]) != cell.turns:
                return []
            msgs, nlus, users = [], [], []
            for j, t in enumerate(d["turns"]):
                if not isinstance(t, dict):
                    return []
                user, aeris = (t.get("user") or "").strip(), t.get("aeris")
                last = j == len(d["turns"]) - 1
                if not (2 <= len(user) <= 180) or not _mix_ok(user, cell.mix):
                    return []
                if t.get("intent") not in CHAT_INTENTS or t.get("sentiment") not in SENTIMENTS \
                        or t.get("emotion") not in EMOTIONS:
                    return []
                msgs.append({"role": "user", "content": user})
                users.append(user)
                if cell.expect == "escalate" and last:
                    msgs.append({"role": "assistant", "content": {"type": "escalate", "reason": _reason(cell.topic),
                                                                  "query": user}})
                    intent = "question.live_info" if _reason(cell.topic) == "live_info" else "question.knowledge"
                else:
                    a = (aeris or "").strip()
                    if _bad_aeris(a):
                        return []
                    msgs.append({"role": "assistant", "content": {"type": "reply", "text": a}})
                    intent = t["intent"]
                nlus.append(make_nlu(user, intent, t["sentiment"], t["emotion"], source="teacher_chat",
                                     rid=f"{rid}-nlu{j}", split=cell_split(rid)))
            facts = [f.strip() for f in d.get("facts") or [] if isinstance(f, str) and f.strip()]
            joined = " ".join(users).lower()
            if any(f.lower() not in joined for f in facts):
                facts = []  # a rephrased "fact" would teach the memory head to invent — drop, don't trust
            turn = {"split": cell_split(rid), "source": "teacher_chat", "family": f"chat_{cell.expect}",
                    "lang": "en" if cell.mix == "english" else "hi", "prompt_lang": "match", "now": None,
                    "messages": msgs, "id": rid,
                    "meta": {"topic": cell.topic, "register": cell.register, "mix": cell.mix, "mood": cell.mood,
                             "persona": cell.persona, "lang_detected": lang_label(users[0])}}
            mem = make_memory(users, facts, source="teacher_chat", rid=f"{rid}-mem", split=cell_split(rid))
            return [turn, *nlus, mem]
        jobs.append(Job(prompt, accept))
    return jobs


def cell_split(rid: str) -> str:
    return rid.split("-")[1] if rid.count("-") >= 2 else "train"
