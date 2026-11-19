"""Safe arithmetic evaluator — handles natural-language math.

Examples that work:
    "calculate 25 * 4"
    "what is 100 divided by 5"
    "kya hai 3 plus 7"
    "20 percent of 480"
    "square root of 144"

Distinct from existing executor ``calculate`` intent — that one expects a
clean math expression in slots["expression"]. This skill takes the full raw
text, translates spoken-math words to operators, then evaluates safely
with a whitelisted AST walker (no eval()).
"""
from __future__ import annotations

import ast
import logging
import math
import operator as op
import re
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_WORD_TO_OP = {
    r"\bplus\b":      "+",
    r"\bminus\b":     "-",
    r"\btimes\b":     "*",
    r"\bmultiplied\s+by\b": "*",
    r"\bx\b":         "*",        # "25 x 4"
    r"\bby\b(?=\s*\d)":     "*",  # "divided by" handled separately first
    r"\bdivided\s+by\b": "/",
    r"\bdivide\s+by\b":  "/",
    r"\bover\b":      "/",
    r"\bmod\b":       "%",
    r"\bmodulo\b":    "%",
    r"\bpower\b":     "**",
    r"\bto\s+the\s+power\s+of\b": "**",
    r"\braised\s+to\b": "**",
    r"\bjod\b":       "+",     # Hinglish "jod" = plus
    r"\bguna\b":      "*",
    r"\bbhag\b":      "/",
    r"\bghata\b":     "-",
    r"\bka\s+\b(?=\d)": "*",   # "5 ka 4" → 5*4 (informal)
}


_PCT_OF_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage)\s+(?:of|ka)\s+(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SQRT_RE = re.compile(
    r"(?:sq(?:uare)?\s*root(?:\s+of)?|\broot(?:\s+of)?|sqrt\s*\(?)\s*(\d+(?:\.\d+)?)\)?",
    re.IGNORECASE,
)


_VERB_STRIP = re.compile(
    r"^(?:please\s+)?"
    r"(?:calculate|calc|compute|evaluate|solve|what\s+is|what's|"
    r"kya\s+hai|batao|find|tell\s+me)\s*",
    re.IGNORECASE,
)


def _natural_to_expr(text: str) -> str:
    s = text.strip()
    s = _VERB_STRIP.sub("", s)
    s = s.rstrip(" ?.,").strip()
    # Translate spoken-math words FIRST (before filler strip) — otherwise
    # the filler regex would gut "the" out of "to the power of" and break
    # the multi-token operator match.
    for pat, sym in sorted(_WORD_TO_OP.items(), key=lambda kv: -len(kv[0])):
        s = re.sub(pat, sym, s, flags=re.IGNORECASE)
    # Drop residual Hinglish/English filler that doesn't carry arithmetic
    # meaning. "me se" / "se" / "ko" frequently appear between operand
    # and operator; "the" / "to" are stranded after operator substitution.
    s = re.sub(r"\b(?:me\s+se|se|ko|the|to|of)\b", "", s, flags=re.IGNORECASE)
    # Collapse runs of whitespace.
    s = re.sub(r"\s+", " ", s).strip()
    return s


# AST whitelist — only these node types are accepted by ``_eval``.
_BINOP = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod, ast.Pow: op.pow,
}
_UNARYOP = {ast.UAdd: op.pos, ast.USub: op.neg}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"non-numeric constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        fn = _BINOP.get(type(node.op))
        if fn is None:
            raise ValueError("operator not allowed")
        return fn(_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        fn = _UNARYOP.get(type(node.op))
        if fn is None:
            raise ValueError("unary op not allowed")
        return fn(_eval(node.operand))
    raise ValueError(f"node type not allowed: {type(node).__name__}")


def _safe_eval(expr: str) -> float | int:
    tree = ast.parse(expr, mode="eval")
    return _eval(tree)


def _format(n: float | int) -> str:
    if isinstance(n, int) or (isinstance(n, float) and n.is_integer()):
        return str(int(n))
    return f"{n:.6g}"


# ── quick_calc ─────────────────────────────────────────────────────


@skill(
    name="quick_calc",
    description="Evaluate a math expression spoken in English / Hinglish.",
    patterns=[
        "kya hai",
        "what's 25 times 4", "calculate 100 divided by 5",
        "kya hai 3 plus 7", "20 percent of 480",
        "square root of 144", "sqrt of 81",
        "25 x 4", "5 ka 4 guna", "100 me se 30 ghata",
        "what's 2 to the power of 10",
    ],
    required_entities=[],
)
def quick_calc(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or slots.get("expression") or ""
    if not text.strip():
        return "Math expression do — e.g. 'calculate 25 * 4'."

    # Special pattern: "X percent of Y"
    m_pct = _PCT_OF_RE.search(text)
    if m_pct:
        x = float(m_pct.group(1))
        y = float(m_pct.group(2))
        return f"{_format(x)}% of {_format(y)} = {_format(x * y / 100)}"

    # Special pattern: square root
    m_sqrt = _SQRT_RE.search(text)
    if m_sqrt:
        n = float(m_sqrt.group(1))
        if n < 0:
            return "Square root of a negative number — not a real number."
        return f"√{_format(n)} = {_format(math.sqrt(n))}"

    expr = _natural_to_expr(text)
    if not expr:
        return "Expression nahi mila."
    if not re.search(r"\d", expr):
        return f"Numbers nahi mile in {text!r}."
    try:
        result = _safe_eval(expr)
    except ZeroDivisionError:
        return "Zero se divide nahi kar sakte."
    except Exception:
        # Don't leak a raw Python SyntaxError ("invalid syntax (<unknown>...)")
        # to the user — give a friendly hint instead. (Fires when a non-simple
        # phrase like "5 factorial" / "hcf of 24 36" mis-routes here.)
        return (f"'{text.strip()}' ko simple calculation ki tarah samajh nahi paya — "
                "ek saaf math expression do, jaise '12 + 37', '15% of 200' ya "
                "'square root of 144'.")
    return f"{expr.strip()} = {_format(result)}"
