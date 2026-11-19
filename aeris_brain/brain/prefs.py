"""Preference pairs for DPO (plan §7, stage S2).

Each pair = same prompt, chosen = the gold answer, rejected = a NEAR MISS
that targets one failure mode we care about:

  guess_instead_of_ask   gold asks for a missing detail → rejected invents it
  ask_instead_of_act     gold acts with everything given → rejected asks anyway
  sibling_tool           right family, wrong tool (alarm ↔ timer, call ↔ message)
  corrupt_span           right tool, a copied name/number/message altered
  answer_live_info       gold escalates live info → rejected makes up an answer
  extra_arg              adds an optional arg the user never said

Near misses teach far more than random wrong answers: the model already
avoids nonsense; DPO is for the decisions it gets almost right.
"""
from __future__ import annotations

import copy
import random

from .contract import canonical, load_tools, validate

SIBLINGS = {
    "set_alarm": "set_timer", "set_timer": "set_alarm", "set_reminder": "set_alarm",
    "call": "send_message", "send_message": "open_chat", "open_chat": "send_message",
    "read_screen": "summarize_screen", "summarize_screen": "read_screen",
    "open_app": "web_search", "play_music": "web_search", "remember": "create_note",
    "create_note": "remember", "recall": "remember", "flashlight": "brightness",
    "end_conversation": "cancel_task", "cancel_task": "end_conversation",
}
INVENTED = {"message": "I'll call you later", "contact": "Rahul", "time": "7 am",
            "duration": "5 minutes", "app": "Chrome", "query": "latest songs",
            "destination": "home", "text": "something important"}
LIVE_ANSWERS = ["It's sunny and 28 degrees today.", "India won by 5 wickets.",
                "Gold is at 62,000 rupees per 10 grams.", "Aaj mausam saaf rahega."]


def _corrupt(v: str, rng: random.Random) -> str:
    digits = [i for i, c in enumerate(v) if c.isdigit()]
    if digits:
        i = rng.choice(digits)
        return v[:i] + str((int(v[i]) + rng.randint(1, 8)) % 10) + v[i + 1:]
    words = v.split()
    if len(words) > 1:
        words.pop(rng.randrange(len(words)))
        return " ".join(words)
    return v[:-1] if len(v) > 2 else v + "a"


def rejected_for(gold: dict, tools: dict, rng: random.Random) -> tuple[str, dict] | None:
    t = gold["type"]
    if t == "ask" and gold.get("pending") in tools:
        spec = tools[gold["pending"]]
        args = {}
        for k in list(spec.get("required", [])) + spec.get("one_of", [])[:1]:
            if spec["params"][k]["type"] == "string":
                args[k] = INVENTED.get(k, "something")
            elif spec["params"][k]["type"] == "enum":
                args[k] = spec["params"][k]["values"][0]
        return "guess_instead_of_ask", {"type": "tool_call", "calls": [{"name": spec["name"], "args": args}]}
    if t == "escalate" and gold.get("reason") == "live_info":
        return "answer_live_info", {"type": "reply", "text": rng.choice(LIVE_ANSWERS)}
    if t != "tool_call":
        return None
    call = gold["calls"][0]
    name, args = call["name"], call["args"]
    spec = tools.get(name, {"params": {}})
    options = ["ask_instead_of_act"]
    if name in SIBLINGS:
        options.append("sibling_tool")
    if any(isinstance(v, str) and len(v) > 1 for k, v in args.items()
           if spec["params"].get(k, {}).get("type") == "string"):
        options.append("corrupt_span")
    if [k for k in spec["params"] if k not in args and spec["params"][k]["type"] == "enum"]:
        options.append("extra_arg")
    kind = rng.choice(options)
    bad = copy.deepcopy(gold)
    if kind == "ask_instead_of_act":
        return kind, {"type": "ask", "text": "Could you tell me more?", "pending": name}
    if kind == "sibling_tool":
        sib = SIBLINGS[name]
        sp = tools[sib]
        new_args = {k: v for k, v in args.items() if k in sp["params"]}
        for k in sp.get("required", []):
            if k not in new_args:
                p = sp["params"][k]
                new_args[k] = p["values"][0] if p["type"] == "enum" else next(
                    (v for v in args.values() if isinstance(v, str)), "it")
        bad["calls"][0] = {"name": sib, "args": new_args}
        return kind, bad
    if kind == "corrupt_span":
        keys = [k for k, v in args.items() if isinstance(v, str) and len(v) > 1
                and spec["params"].get(k, {}).get("type") == "string"]
        k = rng.choice(keys)
        bad["calls"][0]["args"][k] = _corrupt(args[k], rng)
        return kind, bad
    k = rng.choice([k for k in spec["params"] if k not in args and spec["params"][k]["type"] == "enum"])
    bad["calls"][0]["args"][k] = rng.choice(spec["params"][k]["values"])
    return kind, bad


def pairs(records, tools=None, seed: int = 1):
    """→ list of {"record", "turn", "chosen", "rejected", "kind"}: the
    notebook renders `record` up to `turn` as the prompt."""
    tools = tools or load_tools()
    rng = random.Random(seed)
    out = []
    for r in records:
        turn = 0
        for m in r["messages"]:
            if m["role"] != "assistant":
                continue
            got = rejected_for(m["content"], tools, rng)
            if got:
                kind, bad = got
                if canonical(bad) != canonical(m["content"]) and \
                        not validate(bad, tools):  # rejected is well-formed, just WRONG
                    out.append({"record": r, "turn": turn, "chosen": canonical(m["content"]),
                                "rejected": canonical(bad), "kind": kind})
            turn += 1
    return out
