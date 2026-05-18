"""Compute + crypto + utility skills — pure-Python, no external services.

* ``quick_math``         — safe arithmetic + math.* (sin/cos/sqrt/log/...)
* ``password_generate``  — secrets.SystemRandom, configurable length/sets
* ``qr_code``            — local QR PNG via qrcode lib, fallback to URL
* ``base64_encode`` / ``base64_decode``  — clipboard-based round trip
* ``hash_text``          — sha256 of clipboard or an explicit string
"""
from __future__ import annotations

import ast
import base64
import hashlib
import logging
import math
import operator
import os
import re
import secrets
import string
import sys
import time
import webbrowser
from typing import Any

from core.skill_registry import skill

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Safe expression evaluator ──────────────────────────────────────── #

_SAFE_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_SAFE_NAMES = {
    "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf,
}
_SAFE_FUNCS = {
    name: getattr(math, name)
    for name in ("sin", "cos", "tan", "asin", "acos", "atan",
                 "sqrt", "log", "log2", "log10", "exp",
                 "floor", "ceil", "fabs", "factorial", "degrees", "radians",
                 "gcd")
    if hasattr(math, name)
}
_SAFE_FUNCS.update({"abs": abs, "round": round, "min": min, "max": max,
                    "int": int, "float": float})


def _safe_eval(node: ast.AST) -> Any:
    """Walk an AST and evaluate ONLY whitelisted nodes. Anything else
    raises — no attribute access, no calls outside _SAFE_FUNCS, no
    comprehensions. Means 'eval(input)' equivalent for arithmetic with
    none of the usual eval() horror.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):  # Py<3.8 fallback
        return node.n  # type: ignore
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BIN:
        return _SAFE_BIN[type(node.op)](_safe_eval(node.left),
                                        _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY:
        return _SAFE_UNARY[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        raise ValueError(f"unknown name: {node.id}")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        if name not in _SAFE_FUNCS:
            raise ValueError(f"unknown function: {name}")
        args = [_safe_eval(a) for a in node.args]
        return _SAFE_FUNCS[name](*args)
    raise ValueError(f"disallowed expression: {ast.dump(node)}")


@skill(
    name="quick_math",
    description="Evaluate a math expression (+ - * / ** sqrt sin pi etc.)",
    patterns=[
        "math", "calculate", "compute", "evaluate",
        "math karo", "calculate karo", "compute karo",
        "what is", "kitna hai", "what's",
    ],
    required_entities=["content"],
    prompts={"content": "Kya calculate karna hai?"},
)
def quick_math(slots: dict) -> str:
    expr = (slots.get("content") or "").strip()
    # Strip leading "is" / "=" so "what is 2+2" works after entity extraction.
    expr = re.sub(r"^(is|=|equals?|kitna)\s+", "", expr, flags=re.I).rstrip("?")
    if not expr:
        return "Expression batao."
    try:
        tree = ast.parse(expr, mode="eval")
        val = _safe_eval(tree)
    except Exception as e:
        return f"Could not evaluate '{expr}': {e}"
    if isinstance(val, float):
        # Trim trailing zeros for cleaner display.
        rendered = f"{val:.10g}"
    else:
        rendered = str(val)
    return f"{expr} = {rendered}"


# ── Password generator ─────────────────────────────────────────────── #

@skill(
    name="password_generate",
    description="Generate a strong random password (default 20 chars, mixed)",
    patterns=[
        "generate password", "new password", "password banao",
        "random password", "password generate", "strong password",
        "16 char password", "20 char password", "32 char password",
    ],
    required_entities=["content"],
    prompts={"content": "Length and complexity? (e.g. '20', '24 with symbols', '16 alphanumeric')"},
)
def password_generate(slots: dict) -> str:
    raw = (slots.get("content") or "").strip().lower()
    m = re.search(r"(\d+)", raw)
    length = max(8, min(128, int(m.group(1)) if m else 20))

    use_symbols = ("symbol" in raw or "special" in raw or
                   ("alpha" not in raw and "letter" not in raw))
    pool = string.ascii_letters + string.digits
    if use_symbols:
        pool += "!@#$%^&*()-_=+[]{};:,.?/"
    # SystemRandom = cryptographic — backed by os.urandom on every platform.
    rng = secrets.SystemRandom()
    pw = "".join(rng.choice(pool) for _ in range(length))
    # Best-effort copy to clipboard.
    copied = ""
    try:
        import pyperclip
        pyperclip.copy(pw)
        copied = " (copied to clipboard)"
    except Exception:
        pass
    return (f"Generated {length}-char {'symbolic' if use_symbols else 'alphanumeric'} "
            f"password{copied}: {pw}")


# ── QR code ────────────────────────────────────────────────────────── #

@skill(
    name="qr_code",
    description="Generate a QR code for a URL or text (saves PNG + opens it)",
    patterns=[
        "qr code", "qr", "qr code banao", "make qr",
        "qr for", "generate qr", "qr code generate karo",
    ],
    required_entities=["content"],
    prompts={"content": "Kya text/URL chahiye QR me?"},
)
def qr_code(slots: dict) -> str:
    text = (slots.get("content") or "").strip()
    if not text:
        return "QR me kya encode karna hai?"
    out_path = os.path.join(_ROOT, "data", f"qr_{int(time.time())}.png")
    # Local generation if qrcode is installed (preferred — no network).
    try:
        import qrcode
        img = qrcode.make(text)
        img.save(out_path)
        try:
            os.startfile(out_path)  # Windows-only convenience
        except Exception:
            pass
        return f"QR saved: {out_path}"
    except ImportError:
        pass
    # Fallback: a public QR-rendering URL opened in the browser. No data
    # uploaded beyond the URL itself; user is informed.
    import urllib.parse as _u
    url = ("https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
           + _u.quote(text))
    try:
        webbrowser.open(url, new=2)
    except Exception:
        return f"QR URL: {url}"
    return (f"QR via api.qrserver.com (no local 'qrcode' lib installed). "
            f"'pip install qrcode[pil]' for offline QR.")


# ── Base64 ─────────────────────────────────────────────────────────── #

def _clip_text() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""


def _clip_write(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


@skill(
    name="base64_encode",
    description="Base64-encode the clipboard (or given text)",
    patterns=[
        "base64 encode", "encode base64", "b64 encode", "base64 kar do",
    ],
)
def base64_encode(slots: dict) -> str:
    text = (slots.get("content") or "").strip() or _clip_text()
    if not text:
        return "Clipboard khaali aur koi text bhi nahi diya."
    enc = base64.b64encode(text.encode("utf-8")).decode("ascii")
    _clip_write(enc)
    return f"Base64 encoded ({len(enc)} chars), copied to clipboard."


@skill(
    name="base64_decode",
    description="Base64-decode the clipboard (or given text)",
    patterns=[
        "base64 decode", "decode base64", "b64 decode", "base64 decode karo",
    ],
)
def base64_decode(slots: dict) -> str:
    text = (slots.get("content") or "").strip() or _clip_text()
    if not text:
        return "Clipboard khaali aur koi text bhi nahi diya."
    try:
        dec = base64.b64decode(text, validate=True).decode("utf-8", errors="replace")
    except Exception as e:
        return f"Decode fail ho gaya: {e}"
    _clip_write(dec)
    return f"Decoded ({len(dec)} chars), copied to clipboard."


# ── Hash ───────────────────────────────────────────────────────────── #

@skill(
    name="hash_text",
    description="SHA-256 hash of clipboard (or given text)",
    patterns=[
        "hash", "sha256", "sha 256", "hash this", "hash text",
        "sha256 karo", "hash karo",
    ],
)
def hash_text(slots: dict) -> str:
    text = (slots.get("content") or "").strip() or _clip_text()
    if not text:
        return "Clipboard khaali aur koi text bhi nahi diya."
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    _clip_write(h)
    return f"SHA-256: {h}"
