"""Sync the brain contract into the phone app and write golden fixtures.

    py -3.10 -m scripts.sync_app

1. Copies schema/tools.json → aeris_remote/assets/brain/tools.json, so the
   app offers exactly the tools the model was trained on.
2. Writes aeris_remote/test/fixtures/brain_golden.json. The Dart tests
   (test/brain_contract_test.dart) re-render every case and must produce
   byte-identical text, so a drift between training and inference fails a
   test instead of silently costing accuracy on the phone:
     - system prompts (all tools / subsets, each language rule, now, memory)
     - full Qwen3 chat prompts, rendered with the real Unsloth chat template
       (schema/qwen3_chat_template.jinja, enable_thinking=False)
     - canonical() of contract objects
     - validate() errors for valid and broken outputs
"""
from __future__ import annotations

import json
import os
import shutil

from brain.contract import canonical, load_tools, validate
from brain.prompt import system_prompt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
# The app that runs the brain: aeris_assistant (2026-11-17). aeris_remote keeps
# its older fixture; `--app aeris_remote` regenerates that one instead.
import sys as _sys
_APP_NAME = _sys.argv[_sys.argv.index("--app") + 1] if "--app" in _sys.argv else "aeris_assistant"
APP = os.path.normpath(os.path.join(ROOT, os.pardir, _APP_NAME))
TEMPLATE = os.path.join(ROOT, "schema", "qwen3_chat_template.jinja")


def qwen_render(messages: list[dict]) -> str | None:
    """Render with the real chat template (None if jinja2 is missing)."""
    try:
        import jinja2
    except ImportError:
        return None
    env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True)

    def _raise(msg):
        raise ValueError(msg)

    env.globals["raise_exception"] = _raise
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = env.from_string(f.read())
    return tpl.render(messages=messages, add_generation_prompt=True, enable_thinking=False)


def main() -> None:
    tools = load_tools()
    specs = list(tools.values())
    names = list(tools)

    os.makedirs(os.path.join(APP, "assets", "brain"), exist_ok=True)
    shutil.copyfile(os.path.join(ROOT, "schema", "tools.json"),
                    os.path.join(APP, "assets", "brain", "tools.json"))

    prompts = []
    for tool_names, lang, now, memory in [
        (names, "english", None, None),
        (names, "match", None, None),
        (names, "hinglish", "Friday 17 October 2026, 18:40", None),
        (["flashlight", "send_message", "call", "set_alarm"], "match", None,
         ["Ravi is my brother", "my office is in Noida"]),
        (["date_time"], "english", "Saturday 18 October 2026, 07:05", None),
    ]:
        sel = [tools[n] for n in tool_names]
        prompts.append({"tools": tool_names, "lang": lang, "now": now, "memory": memory,
                        "text": system_prompt(sel, lang=lang, now=now, memory=memory)})

    sys_text = system_prompt(specs, lang="english")
    chats = []
    for turns in [
        [("user", "turn on the torch")],
        [("user", "Ravi ko message bhejo"),
         ("assistant", canonical({"type": "ask", "text": "Kya bolna hai Ravi ko?", "pending": "send_message"})),
         ("user", "bolo main 10 minute mein aa raha hoon")],
    ]:
        msgs = [{"role": "system", "content": sys_text}] + [{"role": r, "content": c} for r, c in turns]
        rendered = qwen_render(msgs)
        if rendered is not None:
            chats.append({"system": sys_text, "turns": [list(t) for t in turns], "prompt": rendered})

    objects = [
        {"type": "tool_call", "calls": [{"name": "set_alarm", "args": {"label": "gym", "time": "7 am"}}]},
        {"text": "What should I tell Ravi?", "pending": "send_message", "type": "ask"},
        {"type": "reply", "text": "Main badhiya hoon — aap batao? \"quotes\" and \\ slash"},
        {"steps": ["open Gemini", "make the image", "send it to Ravi"], "goal": "image to Ravi", "type": "plan"},
        {"query": "aaj ka weather", "reason": "live_info", "type": "escalate"},
        {"type": "tool_call", "calls": [{"name": "volume", "args": {"level": 40, "action": "set"}},
                                        {"name": "flashlight", "args": {"state": "off"}}]},
    ]
    canon = []
    for o in objects:
        c = o
        if o.get("type") == "tool_call":  # args in schema order, like make_call
            c = dict(o, calls=[{"name": k["name"],
                                "args": {p: k["args"][p] for p in tools[k["name"]]["params"] if p in k["args"]}}
                               for k in o["calls"]])
        canon.append({"input": o, "canonical": canonical(c)})

    cases = [
        ({"type": "tool_call", "calls": [{"name": "flashlight", "args": {"state": "on"}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "flashlight", "args": {"state": "dim"}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "send_message", "args": {"message": "hi"}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "volume", "args": {"action": "set", "level": 140}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "volume", "args": {"action": "set", "level": 4.0}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "nope", "args": {}}]}, None),
        ({"type": "tool_call", "calls": [{"name": "call", "args": {"contact": "Ravi", "foo": 1}}]}, None),
        ({"type": "tool_call", "calls": []}, None),
        ({"type": "ask", "text": "Which app?", "pending": "open_app"}, None),
        ({"type": "ask", "text": " "}, None),
        ({"type": "plan", "goal": "x", "steps": ["one"]}, None),
        ({"type": "escalate", "reason": "bored", "query": "q"}, None),
        ({"type": "dance"}, None),
        ({"type": "tool_call", "calls": [{"name": "call", "args": {"contact": "Ravi"}}]}, "call ravi please"),
        ({"type": "tool_call", "calls": [{"name": "call", "args": {"contact": "Mohan"}}]}, "call ravi please"),
        ({"type": "tool_call", "calls": [{"name": "open_app", "args": {"app": "YouTube!"}}]}, "youtube kholo"),
    ]
    validations = []
    for obj, user in cases:
        errs = validate(obj, tools, user_text=user, grounded=user is not None)
        validations.append({"output": obj, "user_text": user, "errors": errs})

    os.makedirs(os.path.join(APP, "test", "fixtures"), exist_ok=True)
    out = os.path.join(APP, "test", "fixtures", "brain_golden.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"prompts": prompts, "chats": chats, "canonical": canon,
                   "validate": validations}, f, ensure_ascii=False, indent=1)
    print(f"tools.json -> {APP}/assets/brain/ | golden: {len(prompts)} prompts, "
          f"{len(chats)} chats, {len(canon)} canonical, {len(validations)} validations -> {out}")


if __name__ == "__main__":
    main()
