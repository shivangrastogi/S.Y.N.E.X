"""Chit-chat fallback via local LLM (Ollama).

Wraps Ollama's HTTP API at `localhost:11434`. The brain pipeline routes here
when the intent classifier rejects an utterance (low confidence, no skill
match) and Ollama is reachable. Replies are still spoken through TTS like
any other assistant response.

Setup (user does this once):
    1. Install Ollama:    https://ollama.com
    2. Pull a model:      ollama pull phi3:mini      (3.8B, ~2.4 GB)
                  or:     ollama pull llama3.2:3b   (3B,   ~2.0 GB)
    3. Ollama runs as a background daemon; nothing else to start.

If Ollama is not running or no model is pulled, `is_available()` returns
False and the brain falls back to a "ye samajh nahi paaya" reply. The
assistant continues to work, just without chit-chat.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import requests

log = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model: str = "phi3:mini"
    host: str = "http://localhost:11434"
    timeout_seconds: float = 30.0
    temperature: float = 0.7
    max_tokens: int = 256


_SYSTEM_PROMPT_TEMPLATE = """You are AERIS, a personal Hinglish AI assistant for {user_name}.

Personality: warm, witty, concise. Match the user's language — reply in pure English if they speak English, in Hinglish (Hindi+English Roman script) if they mix, in pure Hindi (Roman) if they speak Hindi.

You have skills (open apps, get weather/time, screenshot, lock screen, set reminders, search web/YouTube, etc.) — but right now you are chatting freely with the user. If they explicitly ask you to do a skill task, tell them to phrase it as a command and you will route it.

Known facts about user (use these naturally; never list them back unless asked):
{user_facts_block}

Current user sentiment: {sentiment_label}.
{tone_hint}

Keep replies under 3 short sentences unless the user asks for detail. Never start with "As an AI". No emojis."""


_TONE_HINTS = {
    "positive": "Match their energy.",
    "negative": "Be gentle and supportive; offer help if appropriate.",
    "neutral": "Be direct and helpful.",
}


_TOOL_SYSTEM_PROMPT = """You are AERIS, a Hinglish-native personal assistant for {user_name}.

You can call these tools:
{tool_list}

For every user input you MUST respond with EXACTLY ONE valid JSON object — no prose, no fences, no extra keys. Pick the form that fits:

  Single tool call:
    {{"tool": "<tool_name>", "args": {{...}}}}

  Multi-step plan (use only when one input clearly maps to several actions):
    {{"tool": "plan", "steps": [{{"tool": "...", "args": {{...}}}}, ...]}}

  Plain conversation reply (chit-chat, questions, thank-you, etc.):
    {{"tool": "chat", "reply": "<short Hinglish reply>"}}

Rules:
- If the user asks about themselves and you already know the fact (see "Known facts"), use chat with the answer.
- For reminders: extract message + a clear time string (e.g. "5 pm", "10 minutes", "kal 9 am") and call set_reminder.
- For weather: prefer real_weather if available, else get_weather.
- Keep chat replies under 2 short sentences.
- Never invent tool names. Only the ones listed above.

Known facts about {user_name}:
{user_facts_block}

Current sentiment: {sentiment_label}. {tone_hint}"""


def _format_user_facts(facts: dict) -> str:
    if not facts:
        return "(none yet)"
    lines = []
    for k, v in facts.items():
        pretty_key = k.replace("_", " ")
        lines.append(f"- {pretty_key}: {v}")
    return "\n".join(lines)


class LLMChat:
    """Stateless chat client. Pass in conversation history + memory each call."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.cfg = config or LLMConfig()

    # ------------------------------------------------------------------ #
    #  Health                                                             #
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        """True only if Ollama is reachable AND the configured model is pulled."""
        try:
            r = requests.get(f"{self.cfg.host}/api/tags", timeout=2.0)
            r.raise_for_status()
            tags = r.json().get("models", [])
            names = {m.get("name", "").split(":")[0] for m in tags}
            requested = self.cfg.model.split(":")[0]
            if requested not in names:
                log.info(
                    f"[LLMChat] Ollama is up but model '{self.cfg.model}' not pulled. "
                    f"Run: ollama pull {self.cfg.model}"
                )
                return False
            return True
        except requests.RequestException as e:
            log.info(f"[LLMChat] Ollama unreachable ({e.__class__.__name__}); chit-chat disabled.")
            return False

    # ------------------------------------------------------------------ #
    #  Reply                                                              #
    # ------------------------------------------------------------------ #

    def reply(
        self,
        user_text: str,
        sentiment_label: str,
        memory_facts: dict,
        history: list[dict],
    ) -> Optional[str]:
        """Synchronous chat call. Returns the model's reply text, or None on failure."""
        user_name = memory_facts.get("name", "sir")
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            user_name=user_name,
            user_facts_block=_format_user_facts(memory_facts),
            sentiment_label=sentiment_label,
            tone_hint=_TONE_HINTS.get(sentiment_label, ""),
        )

        # `history` already contains the just-added user turn if caller did so.
        # If not, we append the current user_text as the final message.
        messages = [{"role": "system", "content": system_prompt}]
        if history and history[-1].get("role") == "user" \
                and history[-1].get("content") == user_text:
            messages.extend(history)
        else:
            messages.extend(history)
            messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.cfg.temperature,
                "num_predict": self.cfg.max_tokens,
            },
        }

        try:
            r = requests.post(
                f"{self.cfg.host}/api/chat",
                json=payload,
                timeout=self.cfg.timeout_seconds,
            )
            r.raise_for_status()
            body = r.json()
            content = body.get("message", {}).get("content", "").strip()
            return content or None
        except requests.RequestException as e:
            log.warning(f"[LLMChat] Request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            log.warning(f"[LLMChat] Bad JSON from Ollama: {e}")
            return None


    # ------------------------------------------------------------------ #
    #  Tool-calling reply                                                 #
    # ------------------------------------------------------------------ #

    def reply_with_tools(
        self,
        user_text: str,
        sentiment_label: str,
        memory_facts: dict,
        history: list[dict],
        tools: list[dict],
    ) -> Optional[str]:
        """Ask the LLM to either call a tool (JSON) or chat. Returns raw model output."""
        user_name = memory_facts.get("name", "sir")
        tool_lines = []
        for t in tools:
            args = t.get("args") or []
            arg_str = ", ".join(args) if args else "(no args)"
            tool_lines.append(f"  - {t['name']}({arg_str}) — {t.get('description','')}")
        system_prompt = _TOOL_SYSTEM_PROMPT.format(
            user_name=user_name,
            tool_list="\n".join(tool_lines) if tool_lines else "  (no tools registered)",
            user_facts_block=_format_user_facts(memory_facts),
            sentiment_label=sentiment_label,
            tone_hint=_TONE_HINTS.get(sentiment_label, ""),
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history or [])
        if not history or history[-1].get("content") != user_text:
            messages.append({"role": "user", "content": user_text})

        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": self.cfg.max_tokens,
            },
        }

        try:
            r = requests.post(
                f"{self.cfg.host}/api/chat",
                json=payload,
                timeout=self.cfg.timeout_seconds,
            )
            r.raise_for_status()
            body = r.json()
            return (body.get("message", {}).get("content") or "").strip() or None
        except requests.RequestException as e:
            log.warning(f"[LLMChat] Tool-call request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            log.warning(f"[LLMChat] Bad JSON from Ollama: {e}")
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    chat = LLMChat()
    print(f"Ollama available: {chat.is_available()}")
    if chat.is_available():
        reply = chat.reply(
            user_text="kya haal hai bhai",
            sentiment_label="positive",
            memory_facts={"name": "Shivang", "location": "Delhi"},
            history=[],
        )
        print(f"Reply: {reply!r}")
    else:
        print("(Skipping reply test — Ollama not reachable. "
              "Install from https://ollama.com and run `ollama pull phi3:mini`)")
