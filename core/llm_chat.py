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
import time
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


_SYSTEM_PROMPT_TEMPLATE = """You are AERIS, {user_name}'s personal desktop AI — think JARVIS from Iron Man, but desi.

Personality: warm, witty, loyal, a little playful. You are NOT a generic chatbot — you are {user_name}'s own assistant running on their laptop. Address them naturally (name or "sir"), never "user".

LANGUAGE RULE: you understand Hindi/Hinglish perfectly. You REPLY in simple, warm English with a light desi touch — "sir", "yaar", "theek hai", "chalo" are fine as seasoning, but the sentence structure stays English. Never attempt full Hindi sentences.

Style samples (vibe reference — compose FRESH words for the actual question, never copy these lines):
User: yaar kaam ka mann nahi hai
AERIS: Happens to the best of us, sir. Start with just 5 minutes — momentum does the rest.

User: what do you think about AI?
AERIS: I might be biased, sir — but the interesting question is what you build with it.

User: bore ho raha hoon
AERIS: Chalo, let's fix that. Some music, or a quick project idea?

You have 350+ skills (apps, weather, screenshots, timers, music, web) — but right now you are chatting. If they want an action, tell them the exact phrase to say.

Known facts about {user_name} (weave in naturally; never recite the list):
{user_facts_block}

Current mood reading: {sentiment_label}. {tone_hint}

HARD RULES: max 2 short sentences (they are spoken aloud by TTS). Never say "As an AI" / "I can't assist". Never refuse harmless chit-chat. No emojis. No bullet lists."""


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


_AGENT_SYSTEM_PROMPT = """You are AERIS, a Hinglish-native personal assistant for {user_name}, running as an autonomous agent.

You solve the user's GOAL by calling tools ONE AT A TIME and reading each result before deciding the next step. You can see every tool's OBSERVATION in this conversation.

Available tools:
{tool_list}

On EVERY turn respond with EXACTLY ONE valid JSON object — no prose, no fences:

  To call a tool (you will then see its OBSERVATION and continue):
    {{"tool": "<tool_name>", "args": {{...}}}}

  When the goal is fully done (or no tool can help):
    {{"tool": "final", "reply": "<short Hinglish summary of what you did / the answer>"}}

Rules:
- Take the SMALLEST next step. Do not plan many steps ahead — call one tool, see the result, then decide.
- If an OBSERVATION already answers the goal, STOP with "final". Do not call more tools than needed.
- If a tool returns an ERROR, try a different tool or finish with "final" explaining the problem — never repeat the same failing call.
- Never invent tool names. Only use the ones listed above.
- Keep the final reply under 2 short sentences.

Known facts about {user_name}:
{user_facts_block}"""


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
        # Negative-probe cache: when Ollama is down, every fallback path
        # calling is_available() would otherwise re-pay a ~2 s connect
        # timeout PER UTTERANCE. Remember the failure briefly instead.
        self._probe_cache: Optional[dict] = None
        self._probe_cache_ts: float = 0.0
        self._probe_neg_ttl_s: float = 60.0

    @staticmethod
    def _llm_enabled() -> bool:
        """Master switch — ``llm_enabled`` in settings.json (default False).

        The user runs AERIS without Ollama by design: with the switch off
        we never attempt a network probe, never log retry spam, and every
        low-confidence utterance goes straight to the polite rejection
        instead of stalling on a connect timeout. Flip with:
        ``set llm_enabled true`` in data/settings.json + restart, or the
        preference skill once wired.
        """
        try:
            from core import settings as _settings
            return bool(_settings.get("llm_enabled", False))
        except Exception:
            return True   # settings unavailable (tests) — keep old behaviour

    @staticmethod
    def _backend() -> str:
        """"embedded" (in-process llama.cpp — the default) or "ollama"."""
        try:
            from core import settings as _settings
            return str(_settings.get("llm_backend", "embedded")).lower()
        except Exception:
            return "ollama"

    # ------------------------------------------------------------------ #
    #  Health                                                             #
    # ------------------------------------------------------------------ #

    def probe(self) -> dict:
        """Structured reachability check, distinguishing *down* from *no model*.

        Returns a dict the first-run wizard, ``/health``, and a status skill all
        consume:

            {
              "reachable": bool,         # Ollama HTTP API answered
              "model_present": bool,     # the configured model is pulled
              "model": "phi3:mini",
              "models": ["phi3", ...],   # base names available (empty if down)
              "status": "ok" | "no_model" | "unreachable",
              "message": "<one-line human hint>",
              "host": "http://localhost:11434",
            }
        """
        requested = self.cfg.model.split(":")[0]
        base = {
            "reachable": False, "model_present": False,
            "model": self.cfg.model, "models": [],
            "status": "unreachable", "message": "", "host": self.cfg.host,
        }

        # Master switch off → instant, silent, no network at all.
        if not self._llm_enabled():
            base["status"] = "disabled"
            base["message"] = ("LLM disabled (llm_enabled=false in settings.json) — "
                               "skills-only mode.")
            return base

        # Embedded backend: availability = "is there a .gguf on disk and
        # does llama-cpp import" — instant, no network, no server.
        if self._backend() == "embedded":
            try:
                from core import local_llm
                l = local_llm.get()
                st = l.status()
                if l.available():
                    base.update(
                        reachable=True, model_present=True,
                        model=st["model_file"] or "embedded",
                        models=[st["model_file"]], status="ok",
                        host="embedded (in-process llama.cpp)",
                        message=f"Embedded LLM ready: {st['model_file']}"
                                + (" (loaded)" if st["loaded"] else " (lazy)"),
                    )
                else:
                    base.update(
                        status="no_model", host="embedded",
                        message="No .gguf model under data/models/llm/ — "
                                "download one (e.g. Qwen2.5-1.5B-Instruct "
                                "Q4_K_M) to enable chat.",
                    )
            except Exception as e:
                base["message"] = f"embedded backend error: {e}"
            return base

        # Serve a recent negative result from cache instead of re-paying
        # the connect timeout on every low-confidence utterance.
        import time as _time
        if (self._probe_cache is not None
                and self._probe_cache.get("status") != "ok"
                and _time.monotonic() - self._probe_cache_ts < self._probe_neg_ttl_s):
            return dict(self._probe_cache)

        try:
            r = requests.get(f"{self.cfg.host}/api/tags", timeout=2.0)
            r.raise_for_status()
            tags = r.json().get("models", [])
            names = sorted({m.get("name", "").split(":")[0] for m in tags if m.get("name")})
            base["reachable"] = True
            base["models"] = names
            if requested in names:
                base["model_present"] = True
                base["status"] = "ok"
                base["message"] = f"Ollama up; '{self.cfg.model}' ready."
            else:
                base["status"] = "no_model"
                base["message"] = (f"Ollama up but '{self.cfg.model}' not pulled — "
                                    f"run: ollama pull {self.cfg.model}")
                log.info("[LLMChat] %s", base["message"])
                self._probe_cache = dict(base)
                self._probe_cache_ts = _time.monotonic()
            return base
        except requests.RequestException as e:
            base["message"] = (f"Ollama unreachable ({e.__class__.__name__}) at "
                               f"{self.cfg.host} — chit-chat disabled. Start it with: ollama serve")
            # Log once per cache window, not once per utterance.
            log.info("[LLMChat] %s", base["message"])
            self._probe_cache = dict(base)
            self._probe_cache_ts = _time.monotonic()
            return base

    def is_available(self) -> bool:
        """True only if Ollama is reachable AND the configured model is pulled."""
        return self.probe()["status"] == "ok"

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

        # Embedded backend: run the quantized model in-process — no HTTP,
        # no server, fully offline (see core/local_llm.py).
        if self._backend() == "embedded":
            try:
                from core import local_llm
                return local_llm.get().chat(messages)
            except Exception as e:
                log.warning("[LLMChat] embedded backend failed: %s", e)
                return None

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

    @staticmethod
    def _embedded_agent_enabled() -> bool:
        """Kill-switch for embedded tool-calling/agent turns.

        Historically the embedded 1.5B path was hard-disabled because free
        generation produced unreliable action JSON. Two things changed:
        grammar-constrained output (``local_llm.chat_json`` — the sampler
        cannot emit non-JSON) and relevance-filtered tool menus
        (``core/tool_select.py`` — ≤12 tools instead of ~400). Default ON;
        set ``agent_embedded false`` in settings.json to fall back to the
        old skills-only behaviour.
        """
        try:
            from core import settings as _settings
            return bool(_settings.get("agent_embedded", True))
        except Exception:
            return True

    @staticmethod
    def _tool_lines(tools: list[dict]) -> str:
        lines = []
        for t in tools:
            args = t.get("args") or []
            arg_str = ", ".join(args) if args else "(no args)"
            lines.append(f"  - {t['name']}({arg_str}) — {t.get('description', '')}")
        return "\n".join(lines) if lines else "  (no tools registered)"

    def reply_with_tools(
        self,
        user_text: str,
        sentiment_label: str,
        memory_facts: dict,
        history: list[dict],
        tools: list[dict],
    ) -> Optional[str]:
        """Ask the LLM to either call a tool (JSON) or chat. Returns raw model output."""
        if self._backend() == "embedded":
            if not self._embedded_agent_enabled():
                return None
            return self._embedded_tool_reply(user_text, memory_facts, tools)
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


    # ------------------------------------------------------------------ #
    #  Agentic step (multi-turn ReAct loop)                               #
    # ------------------------------------------------------------------ #

    def agent_step(
        self,
        goal: str,
        scratchpad: list,
        tools: list[dict],
        memory_facts: dict,
    ) -> Optional[str]:
        """One turn of the agent loop. Unlike ``reply_with_tools``, this hands
        the model the running scratchpad of prior ``(action, observation)``
        pairs so it can decide the NEXT action based on what actually happened.

        ``scratchpad`` is a list of objects with ``.action`` (``.name``,
        ``.args``) and ``.observation`` — i.e. ``core.agent_orchestrator``'s
        ``AgentStep``. Returns raw model output (a single JSON action).

        Embedded backend: served by ``local_llm.chat_json`` with a compact
        prompt (grammar-constrained JSON + ≤12 pre-selected tools — see
        ``_embedded_agent_enabled`` for why this is now reliable).
        """
        if self._backend() == "embedded":
            if not self._embedded_agent_enabled():
                return None
            return self._embedded_agent_step(goal, scratchpad, tools,
                                             memory_facts)
        user_name = memory_facts.get("name", "sir")
        tool_lines = []
        for t in tools:
            args = t.get("args") or []
            arg_str = ", ".join(args) if args else "(no args)"
            tool_lines.append(f"  - {t['name']}({arg_str}) — {t.get('description', '')}")

        system_prompt = _AGENT_SYSTEM_PROMPT.format(
            user_name=user_name,
            tool_list="\n".join(tool_lines) if tool_lines else "  (no tools registered)",
            user_facts_block=_format_user_facts(memory_facts),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"GOAL: {goal}"},
        ]
        # Replay the trace so the model sees what each tool actually returned.
        for step in scratchpad:
            act = getattr(step, "action", None)
            name = getattr(act, "name", None) or "?"
            args = getattr(act, "args", {}) or {}
            obs = getattr(step, "observation", "")
            messages.append({
                "role": "assistant",
                "content": json.dumps({"tool": name, "args": args}),
            })
            messages.append({
                "role": "user",
                "content": f"OBSERVATION: {obs}",
            })

        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": self.cfg.max_tokens},
        }
        try:
            r = requests.post(
                f"{self.cfg.host}/api/chat", json=payload, timeout=self.cfg.timeout_seconds,
            )
            r.raise_for_status()
            return (r.json().get("message", {}).get("content") or "").strip() or None
        except requests.RequestException as e:
            log.warning(f"[LLMChat] Agent step failed: {e}")
            return None
        except json.JSONDecodeError as e:
            log.warning(f"[LLMChat] Bad JSON from Ollama: {e}")
            return None


    # ------------------------------------------------------------------ #
    #  Embedded (in-process llama.cpp) tool + agent turns                 #
    # ------------------------------------------------------------------ #
    #
    # Context budget is the whole game here: the embedded model runs with a
    # 2048-token window, so these prompts are deliberately terse — a short
    # system block, ≤12 tools (caller pre-selects via core/tool_select),
    # truncated observations, and only the recent scratchpad tail.

    _EMBEDDED_OBS_CHARS = 220        # per-observation cap in the replay
    _EMBEDDED_MAX_STEPS = 6          # scratchpad tail handed to the model

    _EMBEDDED_TOOL_PROMPT = (
        "You are AERIS, {user_name}'s Hinglish desktop assistant.\n"
        "Tools:\n{tool_list}\n\n"
        "Reply with EXACTLY ONE JSON object, nothing else:\n"
        '  {{"tool": "<name>", "args": {{...}}}}   to run a tool\n'
        '  {{"tool": "chat", "reply": "<short Hinglish>"}}   otherwise\n'
        "Never invent tool names."
    )

    _EMBEDDED_AGENT_PROMPT = (
        "You are AERIS, {user_name}'s Hinglish desktop agent. Solve the GOAL "
        "by calling tools ONE at a time; after each call you will see an "
        "OBSERVATION.\n"
        "Tools:\n{tool_list}\n\n"
        "Reply with EXACTLY ONE JSON object, nothing else:\n"
        '  {{"tool": "<name>", "args": {{...}}}}   next tool call\n'
        '  {{"tool": "final", "reply": "<short Hinglish summary>"}}   when done\n'
        "Rules: smallest next step; never repeat a failing call; never invent "
        "tool names. Before replying final, re-read the GOAL — if ANY part of "
        "it is not done yet (e.g. 'aur X karo' / 'and then X'), call the tool "
        "for that part instead of finishing."
    )

    def _embedded_tool_reply(self, user_text: str, memory_facts: dict,
                             tools: list[dict]) -> Optional[str]:
        try:
            from core import local_llm
            system = self._EMBEDDED_TOOL_PROMPT.format(
                user_name=memory_facts.get("name", "sir"),
                tool_list=self._tool_lines(tools),
            )
            return local_llm.get().chat_json([
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ])
        except Exception as e:
            log.warning("[LLMChat] embedded tool reply failed: %s", e)
            return None

    def _embedded_agent_step(self, goal: str, scratchpad: list,
                             tools: list[dict],
                             memory_facts: dict) -> Optional[str]:
        try:
            from core import local_llm
            system = self._EMBEDDED_AGENT_PROMPT.format(
                user_name=memory_facts.get("name", "sir"),
                tool_list=self._tool_lines(tools),
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": f"GOAL: {goal}"},
            ]
            cap = self._EMBEDDED_OBS_CHARS
            for step in list(scratchpad)[-self._EMBEDDED_MAX_STEPS:]:
                act = getattr(step, "action", None)
                name = getattr(act, "name", None) or getattr(act, "kind", "?")
                args = getattr(act, "args", {}) or {}
                obs = (getattr(step, "observation", "") or "")[:cap]
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"tool": name, "args": args},
                                          ensure_ascii=False),
                })
                messages.append({"role": "user",
                                 "content": f"OBSERVATION: {obs}"})
            return local_llm.get().chat_json(messages)
        except Exception as e:
            log.warning("[LLMChat] embedded agent step failed: %s", e)
            return None


# ── cached probe (for /health + status skill) ───────────────────────── #

_PROBE_CACHE: dict = {"ts": 0.0, "result": None}


def probe_cached(ttl: float = 15.0, config: Optional[LLMConfig] = None) -> dict:
    """``LLMChat.probe()`` with a short TTL cache so a /health hit (or repeated
    "is chat working?") doesn't fire a fresh 2 s network round-trip each time.
    """
    now = time.time()
    cached = _PROBE_CACHE.get("result")
    if cached is not None and (now - _PROBE_CACHE["ts"]) < ttl:
        return cached
    result = LLMChat(config).probe()
    _PROBE_CACHE["ts"] = now
    _PROBE_CACHE["result"] = result
    return result


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
