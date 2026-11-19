"""System prompt for the brain — identical at training time and on the phone.

Tools are rendered as one-line signatures instead of full JSON Schema:

    send_message(message: str, contact?: str, number?: str, app?: whatsapp|sms|telegram)  [one of: contact, number] — Send a text message …

That's roughly a third of the tokens of JSON Schema, which matters twice on
a phone: a small model reads short prompts more accurately, and every prompt
token costs prefill time before the first output token.

The phone (Dart) must render byte-identical text — test_prompt.py pins it.
"""
from __future__ import annotations

PERSONA = (
    "You are AERIS, a voice assistant living on the user's Android phone. "
    "You understand English, Hindi written in English letters (Hinglish), and any mix."
)

CONTRACT = """Answer with exactly ONE JSON object, nothing else:
- {"type":"tool_call","calls":[{"name":TOOL,"args":{...}}]} to act. Use only the tools listed. Several calls are allowed if the user asked for several things.
- {"type":"ask","text":QUESTION,"pending":TOOL} when a required detail is missing. Never guess names, numbers, times or message text.
- {"type":"reply","text":TEXT} for small talk and simple answers you are sure of.
- {"type":"plan","goal":GOAL,"steps":[STEP,...]} when the task needs operating other apps step by step (e.g. make an image in Gemini, then send it on WhatsApp).
- {"type":"escalate","reason":"knowledge"|"live_info"|"complex"|"no_tool","query":TEXT} for facts you may not know, live information (weather, news, scores, prices), long reasoning, or requests no tool can do.
Rules: copy names, numbers, times, places and message text exactly as the user said them. Set optional args only when the user said them. Replies are spoken aloud: 1-2 short sentences, no lists, no markdown."""

LANG_RULE = {
    "english": "Language: reply in simple English only, never Hindi words.",
    "hinglish": "Language: reply in natural Hinglish (Hindi in English letters, mixed with English).",
    "match": "Language: reply in the same language style the user used.",
}


def signature(tool: dict) -> str:
    """One-line signature, required params first, then optional (`?`)."""
    req = list(tool.get("required", []))
    parts = []
    for name in req + [p for p in tool["params"] if p not in req]:
        p = tool["params"][name]
        if p["type"] == "enum":
            typ = "|".join(p["values"])
        elif p["type"] == "integer":
            typ = "int"
        elif p["type"] == "boolean":
            typ = "bool"
        elif p["type"] == "number":
            typ = "number"
        elif p["type"] == "any":
            typ = p.get("hint", "any")
        else:
            typ = "str"
        parts.append(f"{name}{'' if name in req else '?'}: {typ}")
    sig = f"{tool['name']}({', '.join(parts)})"
    if tool.get("one_of"):
        sig += f"  [one of: {', '.join(tool['one_of'])}]"
    return f"{sig} — {tool['description']}"


def system_prompt(tools: list[dict], *, lang: str = "match",
                  now: str | None = None, memory: list[str] | None = None) -> str:
    """Render the full system prompt.

    tools:  the tool specs offered this turn (already retrieved / sampled).
    lang:   'english' | 'hinglish' | 'match' (the app's Language setting).
    now:    e.g. 'Friday 17 October 2026, 18:40' — lets date/time questions
            and relative times make sense.
    memory: retrieved personal facts (RAG), one per line.
    """
    # Fixed parts first, per-turn parts (now, memory) LAST: the phone caches
    # the KV state of everything up to CONTRACT once and reuses it every turn,
    # so the time and retrieved memories cost only a few dozen tokens each.
    lines = [PERSONA, LANG_RULE[lang],
             "Tools:\n" + "\n".join(f"- {signature(t)}" for t in tools),
             CONTRACT]
    if now:
        lines.append(f"Now: {now}.")
    if memory:
        lines.append("Things the user told you to remember:\n" +
                     "\n".join(f"- {m}" for m in memory))
    return "\n\n".join(lines)
