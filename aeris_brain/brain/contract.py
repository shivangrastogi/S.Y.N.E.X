"""The brain's output contract and its validator.

Every assistant turn the brain produces is ONE JSON object of one of five
types (docs/AERIS_MOBILE_BRAIN_PLAN.md §3):

  {"type":"tool_call","calls":[{"name":"set_alarm","args":{"time":"7 am"}}]}
  {"type":"ask","text":"What should I tell Ravi?","pending":"send_message"}
  {"type":"reply","text":"I'm good, thanks for asking!"}
  {"type":"plan","goal":"...","steps":["...","..."]}
  {"type":"escalate","reason":"live_info","query":"aaj ka weather kaisa hai"}

`calls` is a list so one utterance can do several things ("alarm 7 baje ka
lagao aur torch band karo"). `plan` is for work that needs the phone agent to
operate apps (generate an image in Gemini and send it on WhatsApp).

Stdlib only — the same rules are ported to Dart for the phone.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

TYPES = ("tool_call", "ask", "reply", "plan", "escalate")
ESCALATE_REASONS = ("knowledge", "live_info", "complex", "no_tool")

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TOOLS_PATH = os.path.join(_HERE, os.pardir, "schema", "tools.json")


def load_tools(path: str = DEFAULT_TOOLS_PATH) -> dict[str, dict]:
    """name → tool spec, from schema/tools.json."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {t["name"]: t for t in data["tools"]}


def tools_for(record: dict, tools: dict[str, dict]) -> dict[str, dict]:
    """The registry plus any tool specs a converted record brings inline
    (When2Call / xLAM examples use their own tools)."""
    inline = record.get("tool_specs")
    return {**tools, **{t["name"]: t for t in inline}} if inline else tools


def canonical(obj: dict) -> str:
    """Stable, compact JSON — the exact training target string.

    `type` first, then the remaining keys in contract order; args keep the
    tool schema's parameter order so targets never vary by dict ordering.
    """
    order = ["type", "calls", "reason", "query", "goal", "steps", "text", "pending"]
    out = {k: obj[k] for k in order if k in obj}
    out.update({k: v for k, v in obj.items() if k not in out})
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def order_args(call: dict, tools: dict[str, dict]) -> dict:
    """Return `call` with args in the tool's declared parameter order."""
    spec = tools.get(call["name"])
    if not spec:
        return call
    args = call.get("args", {})
    ordered = {k: args[k] for k in spec["params"] if k in args}
    ordered.update({k: v for k, v in args.items() if k not in ordered})
    return {"name": call["name"], "args": ordered}


def make_call(tools: dict[str, dict], *calls: tuple[str, dict]) -> dict:
    return {"type": "tool_call",
            "calls": [order_args({"name": n, "args": a}, tools) for n, a in calls]}


_WS = re.compile(r"\s+")


def norm_text(s: str) -> str:
    """Lowercase, strip punctuation at the edges, collapse spaces."""
    return _WS.sub(" ", s.lower()).strip(" .,!?;:'\"")


def validate(out: Any, tools: dict[str, dict], *, allowed: set[str] | None = None,
             user_text: str | None = None, grounded: bool = False) -> list[str]:
    """Return a list of problems (empty = valid).

    allowed:   tool names that were offered in this prompt (None = all).
    grounded:  string (span) args must appear verbatim in user_text — used
               on training data so labels never invent words.
    """
    errs: list[str] = []
    if not isinstance(out, dict):
        return ["output is not an object"]
    t = out.get("type")
    if t not in TYPES:
        return [f"unknown type {t!r}"]

    def need_str(key: str) -> None:
        v = out.get(key)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{t}: '{key}' must be a non-empty string")

    if t == "tool_call":
        calls = out.get("calls")
        if not isinstance(calls, list) or not calls:
            return ["tool_call: 'calls' must be a non-empty list"]
        for c in calls:
            errs += _validate_call(c, tools, allowed, user_text, grounded)
    elif t == "ask":
        need_str("text")
        p = out.get("pending")
        if p is not None and p not in tools:
            errs.append(f"ask: unknown pending tool {p!r}")
    elif t == "reply":
        need_str("text")
    elif t == "plan":
        need_str("goal")
        steps = out.get("steps")
        if not isinstance(steps, list) or len(steps) < 2 or \
                not all(isinstance(s, str) and s.strip() for s in steps):
            errs.append("plan: 'steps' must be a list of 2+ non-empty strings")
    elif t == "escalate":
        need_str("query")
        if out.get("reason") not in ESCALATE_REASONS:
            errs.append(f"escalate: reason must be one of {ESCALATE_REASONS}")
    return errs


def _validate_call(c: Any, tools, allowed, user_text, grounded) -> list[str]:
    if not isinstance(c, dict) or not isinstance(c.get("name"), str):
        return ["call: needs a string 'name'"]
    name = c["name"]
    spec = tools.get(name)
    if spec is None:
        return [f"call: unknown tool {name!r}"]
    if allowed is not None and name not in allowed:
        return [f"call: tool {name!r} was not offered"]
    args = c.get("args", {})
    if not isinstance(args, dict):
        return [f"{name}: 'args' must be an object"]
    errs = []
    params = spec["params"]
    for k, v in args.items():
        p = params.get(k)
        if p is None:
            errs.append(f"{name}: unknown arg {k!r}")
            continue
        typ = p["type"]
        if typ == "enum":
            if v not in p["values"]:
                errs.append(f"{name}.{k}: {v!r} not in {p['values']}")
        elif typ == "integer":
            if not isinstance(v, int) or isinstance(v, bool):
                errs.append(f"{name}.{k}: must be an integer")
            elif not (p.get("min", v) <= v <= p.get("max", v)):
                errs.append(f"{name}.{k}: {v} out of range")
        elif typ == "boolean":
            if not isinstance(v, bool):
                errs.append(f"{name}.{k}: must be true/false")
        elif typ == "number":
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errs.append(f"{name}.{k}: must be a number")
        elif typ == "any":
            pass  # foreign (converted) schemas with list/dict/float params
        elif typ == "string":
            if not isinstance(v, str) or not v.strip():
                errs.append(f"{name}.{k}: must be a non-empty string")
            elif grounded and user_text is not None and \
                    norm_text(v) not in norm_text(user_text):
                errs.append(f"{name}.{k}: {v!r} is not in the user's words")
    for k in spec.get("required", []):
        if k not in args:
            errs.append(f"{name}: missing required {k!r}")
    one_of = spec.get("one_of")
    if one_of and not any(k in args for k in one_of):
        errs.append(f"{name}: needs one of {one_of}")
    return errs


def parse(text: str) -> dict | None:
    """Parse a model output string into a contract object (None if invalid
    JSON). Tolerates surrounding whitespace/code fences."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.find("{"):]
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        v = json.loads(s[a:b + 1])
    except json.JSONDecodeError:
        return None
    return v if isinstance(v, dict) else None
