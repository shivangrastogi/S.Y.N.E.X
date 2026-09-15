"""Voice-driven local LLM access — chat OR delegate to a registered skill.

Two skills:
  * ``ask_jarvis`` — free-form LLM chat with full skill-as-tool routing
    via ``LLMChat.reply_with_tools``. The LLM can:
      - reply in natural language
      - call one registered skill via JSON: {"tool":"<name>","args":{...}}
      - emit a multi-step plan via JSON: {"tool":"plan","steps":[...]}
  * ``llm_status`` — quick health report (model + reachable + tool count)

Auto-builds the tool manifest from the global ``skill_registry`` so every
voice skill (200+ of them) is reachable through the LLM. Skills whose
patterns are sentinel/internal (clear_chat sentinel, etc.) are filtered
out so the LLM doesn't accidentally pick them.

Falls back to plain reply when ``reply_with_tools`` returns None /
"unavailable" so users always get *some* response.
"""
from __future__ import annotations

import logging
from typing import Optional

from core.skill_registry import skill, all_skills

log = logging.getLogger(__name__)


# Skills that exist only for sentinel/internal use — exclude from the
# LLM tool manifest so the model doesn't try to call them directly.
_LLM_TOOL_BLOCKLIST = {
    "clear_chat",          # sentinel-returning, handled in the UI layer
    "repeat_last",         # sentinel-returning
    "open_settings_panel", # spawns GUI on worker; LLM shouldn't fire
    "start_calibration_wizard",
}


def _build_tool_manifest(max_tools: int = 80) -> list[dict]:
    """Build the LLM tool list from the registered skills.

    Caps at ``max_tools`` to keep the system prompt under control —
    sorted alphabetically (deterministic) so the same N skills are
    surfaced run-to-run. The brain still routes everything through the
    fast-path anyway; tool-use is just for free-form queries that don't
    hit a verbatim pattern.
    """
    tools: list[dict] = []
    for name in sorted(all_skills().keys()):
        if name in _LLM_TOOL_BLOCKLIST:
            continue
        sk = all_skills()[name]
        # Build the args list from required_entities.
        args = list(sk.required_entities or [])
        tools.append({
            "name": name,
            "description": (sk.description or "")[:160],
            "args": args,
        })
        if len(tools) >= max_tools:
            break
    return tools


def _get_llm():
    """Return an LLMChat instance + tool router, or (None, None) if Ollama
    is unreachable / model not pulled. Lazy-imported so an offline machine
    doesn't pay the requests overhead at module-import time."""
    try:
        from core.llm_chat import LLMChat
        from core.tool_router import ToolRouter, parse_tool_response
    except Exception as e:
        log.info("[llm_chat_skill] llm/router import failed: %s", e)
        return None, None, None
    llm = LLMChat()
    if not llm.is_available():
        return None, None, None
    # Build an executor-shaped object for ToolRouter.
    # The tool router only calls `.execute(name, args)` — we can wrap the
    # skill registry directly without dragging the full executor.
    class _SkillExecutor:
        def execute(self, name: str, args: dict) -> str:
            sk = all_skills().get(name)
            if sk is None:
                return f"Skill '{name}' nahi mila."
            try:
                # Inject raw_text so handlers that look for it still work.
                slots = dict(args or {})
                slots.setdefault("raw_text",
                                 " ".join(str(v) for v in args.values())
                                 if isinstance(args, dict) else "")
                return sk.run(slots) or ""
            except Exception as e:
                return f"Skill '{name}' fail: {e}"
    return llm, ToolRouter(_SkillExecutor()), parse_tool_response


def _strip_verb(text: str) -> str:
    import re
    if not text:
        return ""
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:ask\s+jarvis|ask\s+aeris|jarvis\s+poocho|aeris\s+poocho|"
        r"jarvis\s+se\s+pucho|jarvis|aeris|llm|ai|"
        r"chat\s+with\s+jarvis|chat\s+with\s+ai|talk\s+to\s+jarvis)\s*[,:]?\s*",
        "", text.strip(), flags=re.IGNORECASE,
    ).strip(" .?,\"'")


# ── ask_jarvis ─────────────────────────────────────────────────────


@skill(
    name="ask_jarvis",
    description="Free-form chat with the local LLM — model may auto-fire "
                "any registered AERIS skill to satisfy the request.",
    patterns=[
        "ask jarvis", "ask aeris", "ask ai", "ask llm",
        "jarvis poocho", "jarvis se pucho", "aeris se pucho",
        "chat with jarvis", "chat with ai", "talk to jarvis",
        "jarvis ai", "ai se baat",
        "ask the llm", "llm se pucho",
    ],
    required_entities=[],
)
def ask_jarvis(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    question = _strip_verb(text)
    if not question:
        return "Kya pucho? e.g. 'ask jarvis what's on my calendar tomorrow?'."

    llm, router, parse = _get_llm()
    if llm is None:
        return ("Local LLM unreachable — Ollama running hai? Run "
                "'ollama serve' + 'ollama pull llama3.2'.")

    tools = _build_tool_manifest()
    try:
        # Pull conversation history if the engine has set it.
        from core.conversation import get_active
        hist = (get_active().as_messages() if get_active() else []) or []
    except Exception:
        hist = []

    raw = llm.reply_with_tools(
        user_text=question,
        sentiment_label="neutral",
        memory_facts={},
        history=hist,
        tools=tools,
    )
    if not raw:
        return "LLM ne reply nahi diya."

    call = parse(raw)
    result = router.execute(call)
    if call.kind == "tool" and call.name:
        # Tag the tool call so the user knows what fired.
        return f"[{call.name}] {result or '(no output)'}"
    if call.kind == "plan":
        return f"[plan] {result or '(no output)'}"
    return result or raw


# ── llm_status ────────────────────────────────────────────────────


@skill(
    name="llm_status",
    description="Report local-LLM health — model, reachable state, tool count.",
    patterns=[
        "llm status", "ai status", "ollama status",
        "is llm working", "llm health",
        "local llm health", "jarvis llm status",
    ],
    required_entities=[],
)
def llm_status(_slots: dict) -> str:
    try:
        from core.llm_chat import LLMChat
        llm = LLMChat()
        p = llm.probe()
    except Exception as e:
        return f"LLMChat import fail: {e}"
    n_tools = len(_build_tool_manifest())
    status = p.get("status")
    if status == "ok":
        return (f"LLM: OK · model={p.get('model')} · "
                f"{p.get('host')} · {n_tools} tools exposed.")
    if status == "disabled":
        return "LLM: OFF (llm_enabled=false) — skills-only mode."
    # no_model / unreachable / error — the probe message says what to do.
    return f"LLM: {str(status).upper()} — {p.get('message')}"
