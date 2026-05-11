"""LLM-backed code generator (foundation skill).

Voice triggers:
    "jarvis write a python script that ..."
    "code likho jo ... kare"
    "ek script banao ..."

Pipeline:
  1. Detect language hint (python / javascript / html / sql / bash). Default python.
  2. Call LLMChat with a code-focused system prompt (no prose, just code).
  3. Save to data/generated_code/<slug>_<timestamp>.<ext>.
  4. Open in VS Code if available, else Notepad.
  5. If no LLM is up, write a stub file with the prompt so the user can iterate manually.

Sandboxed: no execution. We only generate + open. Future expansions can
add a sandbox runner.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)

_OUT_DIR = Path(_ROOT) / "data" / "generated_code"
_OUT_DIR.mkdir(parents=True, exist_ok=True)


_LANGUAGE_HINTS = {
    "python":     [".py",   ["python", "py script", "py file", "django", "flask", "fastapi", "pandas", "numpy"]],
    "javascript": [".js",   ["javascript", "js", "node", "nodejs", "react", "vue"]],
    "typescript": [".ts",   ["typescript", "ts script"]],
    "html":       [".html", ["html", "webpage", "web page", "landing page"]],
    "css":        [".css",  ["css", "stylesheet"]],
    "sql":        [".sql",  ["sql", "query", "database query"]],
    "bash":       [".sh",   ["bash", "shell script", "shell"]],
    "powershell": [".ps1",  ["powershell", "ps1"]],
}


def _detect_language(text: str) -> tuple[str, str]:
    """Return (language_name, extension)."""
    t = (text or "").lower()
    for lang, (ext, keys) in _LANGUAGE_HINTS.items():
        if any(k in t for k in keys):
            return lang, ext
    return "python", ".py"


def _slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return (s[:max_len] or "snippet")


_CODE_FENCE_RE = re.compile(r"```(?:[\w+-]+)?\s*\n?(.*?)```", re.DOTALL)


def _strip_fences(code: str) -> str:
    """Pull code out of ``` fences if present; else return as-is."""
    if not code:
        return ""
    m = _CODE_FENCE_RE.search(code)
    if m:
        return m.group(1).strip()
    return code.strip()


_CODE_SYSTEM_PROMPT = """You are a senior software engineer. The user wants
clean, working code. Output ONLY the raw code — no prose, no explanations,
no markdown fences. Include minimal but useful inline comments where the
intent is non-obvious. If the user's spec is ambiguous, pick reasonable
defaults silently. Target language: {language}.

Spec:
{spec}
"""


def _call_llm_for_code(spec: str, language: str) -> Optional[str]:
    try:
        from core.llm_chat import LLMChat
    except Exception:
        return None
    chat = LLMChat()
    try:
        if not chat.is_available():
            return None
    except Exception:
        return None
    prompt = _CODE_SYSTEM_PROMPT.format(language=language, spec=spec)
    try:
        reply = chat.reply(
            user_text=prompt,
            sentiment_label="neutral",
            memory_facts={},
            history=[],
        )
    except Exception as e:
        log.info("[code_writer] LLM call failed: %s", e)
        return None
    if not reply:
        return None
    return _strip_fences(reply)


def _open_in_editor(path: Path) -> None:
    """Try VS Code first, then Notepad. Failure is silent."""
    import shutil
    if shutil.which("code"):
        try:
            subprocess.Popen(["code", str(path)], shell=True)
            return
        except Exception:
            pass
    try:
        os.startfile(str(path))
    except Exception:
        pass


_TRIGGER_STRIPS = (
    "jarvis write me a", "jarvis write a", "jarvis likho",
    "write a", "write me a", "code likho jo", "code likho",
    "ek script banao jo", "ek script banao", "script banao jo",
    "script banao", "generate code for", "generate code",
    "code generate karo", "ek code likho",
)


def _extract_spec(raw: str) -> str:
    t = (raw or "").strip()
    low = t.lower()
    for p in sorted(_TRIGGER_STRIPS, key=len, reverse=True):
        if low.startswith(p + " "):
            t = t[len(p) + 1:].strip()
            break
        if low == p:
            return ""
    return t


@skill(
    name="write_code",
    description=("Generate a code snippet/script from a natural-language spec, "
                 "save it under data/generated_code/, and open it in an editor."),
    patterns=[
        "write me a python script that scrapes a website",
        "code likho jo ek list ko sort kare",
        "ek script banao jo file rename kare",
        "generate code for a fibonacci function",
        "jarvis write code", "write a python script",
        "write a javascript function", "write me an html landing page",
        "code generate karo for csv parsing",
        "python script likho",
        "write a function in python",
    ],
    required_entities=["spec"],
    prompts={"spec": "Kya code chahiye? Spec batao."},
)
def write_code(slots: dict) -> str:
    raw = (slots.get("spec") or slots.get("query") or
           slots.get("description") or "").strip()
    spec = _extract_spec(raw)
    if not spec:
        return "Code spec nahi mila — batao kya banana hai."

    language, ext = _detect_language(raw)
    code = _call_llm_for_code(spec, language)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{_slugify(spec)}_{ts}{ext}"
    out_path = _OUT_DIR / fname

    if not code:
        # No LLM available — drop a stub with the spec as a comment so the
        # user has something to iterate on manually.
        comment_prefix = "#" if ext != ".js" and ext != ".ts" else "//"
        code = (f"{comment_prefix} TODO ({language}): {spec}\n"
                f"{comment_prefix} (Generated stub — Ollama not running. Install Ollama "
                f"to get a real implementation.)\n")
        out_path.write_text(code, encoding="utf-8")
        _open_in_editor(out_path)
        return (f"LLM offline tha — stub bana diya {language} mein: {fname}. "
                f"Ollama chalao to real code aayega.")

    out_path.write_text(code + ("\n" if not code.endswith("\n") else ""),
                        encoding="utf-8")
    _open_in_editor(out_path)
    return f"{language.title()} code generate kar diya: {fname}"


@skill(
    name="list_generated_code",
    description="List recently generated code snippets.",
    patterns=[
        "show generated code", "konsa code generate kiya hai",
        "list my code snippets", "kya kya code likha hai",
    ],
    required_entities=[],
)
def list_generated_code(slots: dict) -> str:
    files = sorted(_OUT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = [f for f in files if f.is_file()][:10]
    if not files:
        return "Abhi tak koi code generate nahi kiya, sir."
    lines = ["Recent generated code:"]
    for f in files:
        ts = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %I:%M %p")
        lines.append(f"  - {f.name}   [{ts}]")
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(write_code({"spec": "write me a python script that prints fibonacci up to n"}))
    print(list_generated_code({}))
